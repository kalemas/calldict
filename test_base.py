import datetime
import string
import sys
import textwrap

import calldict
import pytest
import yaml


def yaml_load(text):
    def compatibility(text):
        if sys.version_info < (3,):
            return text.replace('builtins', '__builtin__')
        return text

    return yaml.unsafe_load(compatibility(textwrap.dedent(text)))


def test_shared_value():
    shared_data = {'a': {'b': 1}}
    assert calldict.eval({
        'func': dict.__getitem__,
        'args': [calldict.shared['a'], 'b'],
    }, shared_data=shared_data) == 1


def test_shared_value_with_path():
    """Examples on how to define deep path in shared data."""

    assert calldict.eval(yaml_load("""
        !!python/object/new:calldict.SharedValue
        kwds: { name: '[a][b][c]' }
    """), shared_data={'a': {'b': {'c': 'ok'}}}) == 'ok'

    assert calldict.eval(yaml_load("""
        !!python/object/new:calldict.SharedValue ['[a][b][c]']
    """), shared_data={'a': {'b': {'c': 'ok'}}}) == 'ok'

    assert calldict.eval(yaml_load("""
        !!python/object/new:calldict.SharedValue ['[a][b].format']
    """), shared_data={'a': {'b': str}}) is str.format

    with pytest.raises(AttributeError):
        assert calldict.eval(yaml_load("""
            !!python/object/new:calldict.SharedValue ['[a][b].format']
        """), shared_data={'a': {'b': {}}}) is str.format


def test_safe_shared_value():
    assert isinstance(calldict.eval(yaml_load("""
        !!python/object/new:calldict.SafeSharedValue ['a[b].test']
    """), shared_data={'a': {'b': None}}), calldict.SafeSharedValue)


def test_safe_shared_walk():
    shared_value = calldict.SharedValue()
    assert shared_value['test'].name == '[test]'
    assert shared_value.test.name == 'test'
    assert shared_value['test'].test.name == '[test].test'
    assert shared_value.test['test'].name == 'test[test]'

    obj = type('Test', (), {'test': {'test': 'ok'}})()
    assert shared_value.resolve(obj) == obj
    assert shared_value.test.resolve(obj) == obj.test
    assert shared_value.test['test'].resolve(obj) == 'ok'


def test_shared_value_datetime():
    now = datetime.datetime.now()
    result = calldict.eval([
        # store current time in SharedValue("now")
        dict(func=datetime.datetime.now, returns=calldict.shared['now']),
        # do a long operation
        dict(func=range, args=[10000000]),
        # # evaluate substitution of saved time
        dict(
            func=calldict.shared['now'].__sub__,
            args=[
                # evaluate current time again
                dict(func=datetime.datetime.now)
            ]),
        # accessing shared value by field path (use class constructor as
        # `calldict.shared.var[0][key][2]` is incorrect Python syntax)
        dict(func=list,
             args=[[dict(key=[1, 2, datetime])]],
             returns=calldict.shared['var']),
        calldict.SharedValue("[var][0][key][2].datetime.now"),
    ])
    assert now <= result[-1]()
    assert type(result[2]) is datetime.timedelta


def test_callable():
    assert calldict.is_callable(dict(func=getattr))
    assert not calldict.is_callable(getattr)


def test_from_yaml():
    def constructor(self, suffix, node):
        """Simple YAML constructor to simplify definition."""
        moduleName, objectPath = self.construct_scalar(node).split(' ')
        __import__(moduleName)
        obj = sys.modules[moduleName]
        obj = string.Formatter().get_field('0.' + objectPath, [obj], {})[0]
        return obj

    yaml.add_multi_constructor('!runtime', constructor)

    # PyYAML with custom convenience constructor
    assert calldict.eval(yaml_load("""
        -   func: !runtime builtins open
            args:
            -   func: !runtime tempfile mktemp
                kwargs:
                    suffix: .txt
                returns: !runtime calldict shared[path]
            -   w
            returns: !runtime calldict shared[file]
        -   func: !runtime calldict shared[file].write
            args: [Hello world!!!]
        -   &close
            func: !runtime calldict shared[file].close
        -   func: !runtime builtins open
            args:
            -   !runtime calldict shared[path]
            -   r
            returns: !runtime calldict shared[file]
        -   func: !runtime calldict shared[file].read
        -   *close
    """))[-2] == 'Hello world!!!'

    # or pure PyYAML
    assert calldict.eval(yaml_load("""
        -   func: !!python/name:tempfile.mktemp
            kwargs:
                suffix: .txt
            returns: path
        -   func: !!python/name:builtins.open
            args:
            -   func: !!python/name:operator.getitem
                args:
                -   !!python/name:calldict.shared
                -   path
            -   w
            returns: file
        -   func:
                func: !!python/name:calldict.eval
                args:
                -   func: !!python/name:builtins.getattr
                    args:
                    -   &file
                        func: !!python/name:operator.getitem
                        args:
                        -   !!python/name:calldict.shared
                        -   file
                    -   write
            args: [Hello world!!!]
        -   &close
            func:
                func: !!python/name:calldict.eval
                args:
                -   func: !!python/name:builtins.getattr
                    args:
                    -   *file
                    -   close
        -   func: !!python/name:builtins.open
            args:
            -   func: !!python/name:operator.getitem
                args:
                -   !!python/name:calldict.shared
                -   path
            -   r
            returns: file
        -   func:
                func: !!python/name:calldict.eval
                args:
                -   func: !!python/name:builtins.getattr
                    args:
                    -   *file
                    -   read
        -   *close
    """))[-2] == 'Hello world!!!'


def test_pass_whole_shareddata():
    data = {'test': {'arg': 1}}

    def func(test=None, **kwargs):
        return kwargs.get('arg') or test['arg']

    assert calldict.eval({'func': func, 'kwargs': calldict.shared},
                         shared_data=data) == 1

    assert calldict.eval({'func': func, 'kwargs': calldict.shared['test']},
                         shared_data=data) == 1
