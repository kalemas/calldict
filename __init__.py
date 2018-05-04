
import os
import string
import sys


sys.path.append(os.path.dirname(__file__))


class SharedValue(object):
    def __init__(self, name=None):
            self.name = name

    def __getattr__(self, name):
        if self.name is None:
            return SharedValue(name)
        return SharedValue(self.name + '.' + name)

    def __repr__(self):
        v = super(SharedValue, self).__repr__()
        return v[:v.find(' object')] + '.' + self.name + '>'


# root shared value
shared = SharedValue()


def call(data, sharedData={}):
    if isinstance(data, dict) and 'func' in data:
        pass
    elif isinstance(data, dict):
        return dict([(k, call(v, sharedData=sharedData)) for k, v in data.iteritems()])
    elif isinstance(data, list):
        return [call(d, sharedData=sharedData) for d in data]
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
        data['args'] = [call(v, sharedData=sharedData) for v in data.get('args', [])]
        data['kwargs'] = dict([(k, call(v, sharedData=sharedData)) for k, v in
                               data.get('kwargs', {}).iteritems()])
        data['func'] = call(data['func'], sharedData=sharedData)

    # Call itself
    r = data['func'](*data['args'], **data['kwargs'])

    if 'return' in data:
        # support both, str and SharedValue instances
        if isinstance(data['return'], SharedValue):
            sharedData[data['return'].name] = r
        else:
            sharedData[data['return']] = r
    return r


if __name__ == '__main__':
    import yaml
    import textwrap
    import pprint
    import calldict

    def constructor(self, suffix, node):
        moduleName, objectPath = self.construct_scalar(node).split(' ')
        __import__(moduleName)
        obj = sys.modules[moduleName]
        for a in objectPath.split('.'):
            obj = getattr(obj, a)
        return obj

    yaml.add_multi_constructor('!runtime', constructor)

    # PyYAML with convenience tag added
    pprint.pprint(calldict.call(yaml.load(textwrap.dedent("""
        -   func: !runtime __builtin__ open
            args:
            -   func: !runtime tempfile mktemp
                kwargs:
                    suffix: .txt
                return: !runtime calldict shared.path
            -   w
            return: !runtime calldict shared.file
        -   func: !runtime __builtin__ list
            args:
            -   -   Hello
                -   world
                -   '!'
            return: !runtime calldict shared.list
        -   func: !runtime calldict shared.file.write
            args:
            -   func: !runtime __builtin__ str.format
                args:
                -   '{0} {1}{2}{2}{2}'
                -   !runtime calldict shared.list[0]
                -   !runtime calldict shared.list[1]
                -   !runtime calldict shared.list[2]
        -   &close
            func: !runtime calldict shared.file.close
        -   func: !runtime __builtin__ open
            args:
            -   !runtime calldict shared.path
            -   r
            return: !runtime calldict shared.file
        -   func: !runtime calldict shared.file.read
        -   *close
    """))))

    # out of the box PyYAML (simplified):
    pprint.pprint(calldict.call(yaml.load(textwrap.dedent("""
        -   func: !!python/name:tempfile.mktemp
            kwargs:
                suffix: .txt
            return: path
        -   func: !!python/name:__builtin__.open
            args:
            -   !!python/object/apply:__builtin__.getattr
                args:
                -   !!python/name:calldict.shared
                -   path
            -   w
            return: file
        -   func:
                func: !!python/name:calldict.call
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
                func: !!python/name:calldict.call
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
            return: *file
        -   func:
                func: !!python/name:calldict.call
                args:
                -   args:
                    -   *file
                    -   read
                    func: !!python/name:__builtin__.getattr
        -   *close
    """))))
