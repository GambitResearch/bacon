"""Decorators to synchronize objects access in multithread environment."""
from functools import wraps


def synchro(lock):
    """Synchronize access to a function."""

    def synchro_(f):
        @wraps(f)
        def synchro__(*args, **kwargs):
            with lock:
                return f(*args, **kwargs)

        return synchro__

    return synchro_


def synchro_method(lock_name):
    """Synchronize access to a class methods.

    Use an instance object as lock. The attribute name for the lock should be
    passed to the decorator::

            class Foo:
                    def __init__(self):
                            self._lock = RLock()

                    @synchro_method('_lock')
                    def my_expensive_call(self, foo, bar):
                            pass # [...]
    """

    def synchro_method_(f):
        @wraps(f)
        def synchro_method__(self, *args, **kwargs):
            lock = getattr(self, lock_name)
            with lock:
                return f(self, *args, **kwargs)

        return synchro_method__

    return synchro_method_
