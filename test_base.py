import calldict

def test_shared_value():
    shared_data = {'a': {'b': 1}}
    assert calldict.eval({
        'func': dict.__getitem__,
        'args': [calldict.shared.a, 'b'],
    }, shared_data=shared_data) == 1


def test_callable():
    assert calldict.is_callable(dict(func=getattr))
    assert not calldict.is_callable(getattr)
