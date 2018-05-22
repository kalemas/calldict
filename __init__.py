"""
Call functions stored in a dictionaries.

- Hm, don't you want to programming in YAML or JSON?
- Nope, but to mix high level configuration with callable objects. Many programming approaches
  could be brought to setting up application configuration and to writing application engine.
  Configuration let you to oversee application logic and quickly change its behavior without
  digging into code. And using callable objects in it gives you maximum flexibility before magic
  parameters that wrap those callables.
"""
import string


class SharedValue(object):
    """Class to handle shared data identificators during evaluation."""
    def __init__(self, name=None):
            self.name = name

    def __getattr__(self, name):
        if self.name is None:
            return SharedValue(name)
        return SharedValue(self.name + '.' + name)

    def __repr__(self):
        v = super(SharedValue, self).__repr__()
        return v[:v.find(' object')] + '.' + self.name + '>'

    def __deepcopy__(self, memo):
        return SharedValue(self.name)


# Root shared value
shared = SharedValue()

# @todo add global data storage as necessary
# @todo add threading support as necessary


def _sortData(data, getter=lambda x: x):
    return sorted(
        data,
        # first we process dictionaries as they could be evaluations and return shared data
        # last we process primitive types as they could be shared data references
        key=lambda x:
            0 if isinstance(getter(x), dict) else
            1 if isinstance(getter(x), list) else 2
    )


def eval(data, sharedData={}):
    """
    Evaluate given :param data: and return result.

    :param data: dict with following optional structure:
        {
            "func": function object that will be called
            "args": list of arguments
            "kwargs": dict of keyworded arguments
            "returns": calldict.SharedValue instance or str of a name where the result of current
                       evaluation will be stored in :param sharedData:
            "evaluate": bool whether we need of prevent evaluation of sub structure
        }

    Only dictionaries with "func" keys are considered as a subject of evaluation, otherwise they
    are considered as regular dictionaries and only nested data is evaluated.

    Arguments may be data, another function evaluations or a SharedValue instances. SharedValue is
    constructed with a name and also supports `field_name` of `format string syntax
    <https://docs.python.org/2.7/library/string.html#format-string-syntax>`_ (PEP3101). Simplest
    way to access them is by attributes of `calldict.shared` global variable.

    You can pass :param sharedData: dictionary from outer stack into evaluation to pass a variable
    or get evaluated shared values after evaluation.

    If you need to do `eval` calls on several stages (with passing different :param sharedData: or
    modify :param data: before next `eval`) you can prevent arguments and function itself to be
    evaluated by passing `evaluate` key with value of `False` in :param data:.

    Following code is valid and demonstrates work with shared data:
    >>> import datetime
    >>> calldict.eval([
    >>>     # store current time in SharedValue("now")
    >>>     dict(func=datetime.datetime.now, returns=calldict.shared.now),
    >>>     # do a long operation
    >>>     dict(func=range, args=[10000000]),
    >>>     # evaluate substitution of saved time
    >>>     dict(func=calldict.shared.now.__sub__, args=[
    >>>         # evaluate current time again
    >>>         dict(func=datetime.datetime.now)
    >>>     ]),
    >>>     # accessing shared value by field path (use class constructor as
    >>>     `calldict.shared.var[0][key][2]` is incorrect Python syntax)
    >>>     dict(func=list, args=[[dict(key=[1, 2, datetime])]], returns=calldict.shared.var),
    >>>     calldict.SharedValue("var[0][key][2].datetime.now"),
    >>> ])
    """
    if isinstance(data, dict) and 'func' in data:
        pass
    elif isinstance(data, dict):
        return dict([(k, eval(v, sharedData=sharedData)) for k, v in
                     _sortData(data.iteritems(), lambda x: x[1])])
    elif isinstance(data, list):
        return [eval(d, sharedData=sharedData) for d in _sortData(data)]
    elif isinstance(data, SharedValue):
        try:
            # use well known format syntax to support attributes and indexes
            return string.Formatter().get_field(data.name, [], sharedData)[0]
        except KeyError:
            # value would not be populated if evaluation is in multiple stages/calls
            return data
    else:
        return data

    # @todo make following parameter as integer to allow multilevel precessing
    if data.get('evaluate', True):
        # Evaluate data in sub structure
        data = data.copy()
        data['args'] = [eval(v, sharedData=sharedData) for v in data.get('args', [])]
        data['kwargs'] = dict([(k, eval(v, sharedData=sharedData)) for k, v in
                               data.get('kwargs', {}).iteritems()])
        data['func'] = eval(data['func'], sharedData=sharedData)

    # Call itself
    r = data['func'](*data['args'], **data['kwargs'])

    if 'returns' in data:
        # support both, str and SharedValue instances
        if isinstance(data['returns'], SharedValue):
            sharedData[data['returns'].name] = r
        else:
            sharedData[data['returns']] = r
    return r


if __name__ == '__main__':
    import pprint
    import sys
    import textwrap

    import yaml
    import calldict

    def constructor(self, suffix, node):
        """Simple YAML constructor to simplify definition."""
        moduleName, objectPath = self.construct_scalar(node).split(' ')
        __import__(moduleName)
        obj = sys.modules[moduleName]
        for a in objectPath.split('.'):
            obj = getattr(obj, a)
        return obj

    yaml.add_multi_constructor('!runtime', constructor)

    # PyYAML with custom convenience constructor
    pprint.pprint(calldict.eval(yaml.load(textwrap.dedent("""
        -   func: !runtime __builtin__ open
            args:
            -   func: !runtime tempfile mktemp
                kwargs:
                    suffix: .txt
                returns: !runtime calldict shared.path
            -   w
            returns: !runtime calldict shared.file
        -   func: !runtime calldict shared.file.write
            args: [Hello world!!!]
        -   &close
            func: !runtime calldict shared.file.close
        -   func: !runtime __builtin__ open
            args:
            -   !runtime calldict shared.path
            -   r
            returns: !runtime calldict shared.file
        -   func: !runtime calldict shared.file.read
        -   *close
    """))))

    # out of the box PyYAML:
    pprint.pprint(calldict.eval(yaml.load(textwrap.dedent("""
        -   func: !!python/name:tempfile.mktemp
            kwargs:
                suffix: .txt
            returns: path
        -   func: !!python/name:__builtin__.open
            args:
            -   !!python/object/apply:__builtin__.getattr
                args:
                -   !!python/name:calldict.shared
                -   path
            -   w
            returns: file
        -   func:
                func: !!python/name:calldict.eval
                args:
                -   args:
                    -   &file
                        !!python/object/apply:__builtin__.getattr
                        args:
                        -   !!python/name:calldict.shared
                        -   file
                    -   write
                    func: !!python/name:__builtin__.getattr
            args: [Hello world!!!]
        -   &close
            func:
                func: !!python/name:calldict.eval
                args:
                -   args:
                    -   *file
                    -   close
                    func: !!python/name:__builtin__.getattr
        -   func: !!python/name:__builtin__.open
            args:
            -   !!python/object/apply:__builtin__.getattr
                args:
                -   !!python/name:calldict.shared
                -   path
            -   r
            returns: *file
        -   func:
                func: !!python/name:calldict.eval
                args:
                -   args:
                    -   *file
                    -   read
                    func: !!python/name:__builtin__.getattr
        -   *close
    """))))
