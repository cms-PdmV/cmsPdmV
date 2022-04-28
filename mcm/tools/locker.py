"""
Module that contains Locker class
"""
import logging
from threading import _RLock as SystemReentrantLock
from threading import Lock as SystemNonReentrantLock
from contextlib import contextmanager


class RemovableLock():
    def __init__(self, lock_class, lock_id, delegate):
        self.__lock = lock_class()
        self.lock_id = lock_id
        self.count = 0
        self.delegate = delegate

    def acquire(self, *args, **kwargs):
        acquired = self.__lock.acquire(*args, **kwargs)
        if acquired:
            self.count += 1

        return acquired

    def release(self):
        if self.count <= 0:
            raise Exception('Not locked')

        self.__lock.release()
        self.count -= 1
        if self.count == 0:
            self.delegate.is_released(self)

    def acquired(self):
        return self.count > 0

    def __enter__(self):
        self.acquire()

    def __exit__(self, type, value, traceback):
        self.release()

    def __str__(self):
        class_name = self.__class__.__name__
        return f'{class_name} addr={hex(id(self))} id={self.lock_id} count={self.count}'

    def __repr__(self):
        return str(self)


class ReentrantLock(RemovableLock):
    """
    An reentrant lock that also keeps a count and informs a delegate when count
    gets down to 0
    Must be released by the same thread that acquired it
    """
    def __init__(self, lock_id, delegate):
        super().__init__(SystemReentrantLock, lock_id, delegate)


class NotReentrantLock(RemovableLock):
    """
    A non-reentrant lock that also keeps a count and informs a delegate when
    count gets down to 0
    Created specifically for submission as it happens in different threads and
    only simple lock can be released by any threads
    """
    def __init__(self, lock_id, delegate):
        super().__init__(SystemNonReentrantLock, lock_id, delegate)


class Locker():
    """
    Locker objects has a shared dictionary with locks in it
    Dictionary keys are strings
    """

    __locks = {}
    __locker_lock = SystemNonReentrantLock()
    logger = logging.getLogger()

    @classmethod
    def is_released(cls, lock):
        """
        A callback that is called by a lock when its count is down to 0
        Lock is then removed from the global locks dictionary
        """
        with Locker.__locker_lock:
            cls.logger.debug('Popping %s lock', lock.lock_id)
            # cls.__locks.pop(lock.lock_id)

    @classmethod
    def get_lock(cls, lock_id):
        """
        Return a reentrant lock for a given lock id
        It can be either existing one or a new one will be created
        """
        with Locker.__locker_lock:
            lock = cls.__locks.get(lock_id, ReentrantLock(lock_id, cls))
            cls.__locks[lock_id] = lock

        return lock

    @classmethod
    @contextmanager
    def get_nonblocking_lock(cls, lock_id):
        """
        Return a non blocking reentrant lock or throw LockedException
        """
        with Locker.__locker_lock:
            lock = cls.__locks.get(lock_id, ReentrantLock(lock_id, cls))
            cls.__locks[lock_id] = lock

        # Test by trying to lock
        if not lock.acquire(blocking=False):
            raise LockedException(f'"{lock_id}" is locked')
        try:
            yield lock
        finally:
            # Test does +1 to the lock
            lock.release()

    @classmethod
    def get_status(cls):
        """
        Return current status of locks in the system
        """
        return {lock_id: lock.count for lock_id, lock in cls.__locks.items()}


class LockedException(Exception):
    """
    Exception that should be thrown if nonblocking lock could not be acquired
    """
