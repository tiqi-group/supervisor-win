from functools import wraps


def raise_not_implemented(fn):
    """Raise NotImplementedError"""
    @wraps(fn)
    def __inner(*args, **kwargs):
        raise NotImplementedError("function '{0.__name__}' not implemented!".format(fn))
    return __inner
