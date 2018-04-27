from loggo import logme, Loggo

@Loggo.logme
def test(first, other, kwargs=None):
    """
    docstring
    """
    if not kwargs:
        raise ValueError('no good')
    else:
        return [first, other, kwargs]

test('string', 2466, kwargs=1)

test('astadh', 1331)
