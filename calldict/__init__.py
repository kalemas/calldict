"""
Protocol to markup and evaluate functions in python dictionaries.

It helps with development of a domain model in Python data structure (the
configuration) with function objects defined where dynamic behavior is
required. So you could gain benefit from both functional and declarative
approaches in your development.

It is most powerful in conjunction with PyYAML as it allows to define
runtime objects.
"""
import string


__primitive_types__ = (bool, str, int, float, type(None))


class SharedValue(object):
    """
    Class to handle shared data identifiers during evaluation.

    `name` - string containing simple or compound field name according to
        PEP 3101, it will be used to resolve value from given shared data.
        For example `a[b]` will be resolved from `{'a': {'b': 'ok'}}` to `ok`.
    """

    def __new__(cls, *args, **kwargs):
        instance = object.__new__(cls)
        # PyYAML do not call initializer when constructing an instance that is
        # derived from `type` (classes as well)
        instance.__init__(*args, **kwargs)
        return instance

    def __init__(self, name=None):
        self.name = name

    def __getattr__(self, name):
        if name in {'__setstate__'}:
            raise AttributeError
        if self.name is not None:
            name = self.name + '.' + name
        return self.__class__(name)

    def __getitem__(self, key):
        key = '[' + key + ']'
        if self.name is not None:
            key = self.name + key
        return self.__class__(key)

    def __repr__(self):
        v = super(SharedValue, self).__repr__()
        return v[:v.find(' object')] + ('.' +
                                        self.name if self.name else '') + '>'

    def __deepcopy__(self, memo):
        return self

    def __bool__(self):
        """Raw SharedValue is not true data, it have to be resolved."""
        return False

    def resolve(self, data):
        if not self.name:
            return data
        # use PEP-3101 field names specification to support attributes and
        # indexes
        name = '0.' + self.name if self.name[0] != '[' else '0' + self.name
        return string.Formatter().get_field(name, [data], {})[0]


class SafeSharedValue(SharedValue):
    """
    Useful for multistage evaluation, when some values depends on other shared
    values and have to be resolved in several evaluations.
    """

    def resolve(self, data):
        try:
            return super(SafeSharedValue, self).resolve(data)
        except (AttributeError, KeyError):
            return self


# Root shared value
shared = SharedValue()
shared_safe = SafeSharedValue()

# TODO add global data storage as necessary
# TODO add threading support as necessary


def is_callable(data):
    # 'func' would be SharedValue or another calldict, filter primitives
    # for a while
    return isinstance(data, dict) and 'func' in data and not isinstance(
        data['func'], __primitive_types__)


def _put_return_value(value, key, data):
    for v in key if isinstance(key, list) else [key]:
        # support both, str and SharedValue instances
        path = [
            i for i in (v.name if isinstance(v, SharedValue) else v
                        ).replace(']', '').split('[') if i
        ]
        d = data
        for p in path[:-1]:
            d = d[p]
        d[path[-1]] = value


def eval(data, shared_data=None, skipper=None, memo=None):
    """
    Evaluate given :param data: and return result.

    :param data: dict with following optional structure:
        {
            "func": function object that will be called
            "args": list of arguments
            "kwargs": dict of keyword arguments
            "skipper": Callable(object: Union[Sequence, Mapping],
                key: Hashable) -> bool, return True if nested data should
                not be evaluated
            "returns": calldict.SharedValue instance or str of a name where
                the result of current evaluation will be stored in
                :param shared_data:
            "evaluate": bool whether we need of prevent evaluation of sub
                structure
        }
        This parameter is passed by copying.

    Only dictionaries with "func" keys are considered as a subject of
    evaluation, otherwise they are considered as regular dictionaries and
    only nested data is evaluated.

    Arguments may be data, another function evaluations or a SharedValue
    instances. SharedValue is constructed with a name and also supports
    `field_name` of `format string syntax
    <https://docs.python.org/2.7/library/string.html#format-string-syntax>`_
    (PEP3101). Simplest way to access them is by attributes of
    `calldict.shared` global variable.

    You can pass :param shared_data: dictionary from outer stack into
    evaluation to pass a variable or get evaluated shared values after
    evaluation.

    If you need to do `eval` calls on several stages (with passing different
    :param shared_data: or modify :param data: before next `eval`) you can
    prevent arguments and function itself to be evaluated by passing
    `evaluate` key with value of `False` in :param data:.

    For demonstration on how shared data work, see
    test_shared_value_datetime() in tests.
    """
    if memo is None:
        memo = dict()
    if shared_data is None:
        shared_data = dict()
    # calldict implement kind of deepcopy behavior, we do not support it
    # completely but use this way to handle recursive data and to skip
    # evaluation
    memo_id = id(data)
    if memo_id in memo:
        return memo[memo_id]
    if is_callable(data):
        pass
    elif isinstance(data, (dict, list)):
        if isinstance(data, dict):
            y = type(data)()
            items = data.items()
        else:
            y = data[:]
            items = enumerate(data)
        memo[memo_id] = y
        # first we process dictionaries as they could be evaluations and
        # return shared data last we process primitive types as they could
        # be shared data references
        for k, v in sorted(items,
                           key=lambda x: 0 if isinstance(x[1], dict) else 1
                           if isinstance(x[1], list) else 2):
            if skipper and skipper(data, k):
                y[k] = v
            else:
                y[k] = eval(v,
                            shared_data=shared_data,
                            skipper=skipper,
                            memo=memo)
        return y
    elif isinstance(data, SharedValue):
        return data.resolve(shared_data)
    else:
        return data

    if not data.get('evaluate', True):
        return dict((x, y) for x, y in data.items() if x != 'evaluate')

    # Evaluate call parameters
    data = data.copy()
    for k, v in data.items():
        if k in ('returns', ):
            continue
        if skipper and skipper(data, k):
            data[k] = v
        else:
            data[k] = eval(v,
                           shared_data=shared_data,
                           skipper=skipper,
                           memo=memo)

    # Call itself
    if 'kwargs' not in data:
        kwargs = {
            k: v
            for k, v in data.items()
            if k not in {'returns', 'args', 'func', 'skipper', 'evaluate'}
        }
    else:
        kwargs = data['kwargs']
    result = data['func'](*data.get('args', []), **kwargs)

    if isinstance(result, SharedValue):
        result = result.resolve(shared_data)

    if 'returns' in data:
        _put_return_value(result, data['returns'], shared_data)
    return result
