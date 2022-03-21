"""
Module that contains Locker class
"""
import logging
import time
from threading import _RLock, Lock
from contextlib import contextmanager


class RemarkableLock(_RLock):
    """
    An reentrant lock that also keeps a count and informs a delegate when count
    gets down to 0
    """

    def __init__(self, lock_id, delegate):
        super().__init__()
        self.lock_id = lock_id
        self.lock_count = 0
        self.delegate = delegate
        self.acquired_time = 0

    def acquire(self, *args, **kwargs):
        acquired = super().acquire(*args, **kwargs)
        if acquired:
            self.lock_count += 1
            if self.lock_count == 1:
                self.acquired_time = int(time.time())

        return acquired

    __enter__ = acquire

    def release(self):
        super().release()
        self.lock_count -= 1
        if self.lock_count == 0:
            self.delegate.is_released(self)
            self.acquired_time = 0


class Locker():
    """
    Locker objects has a shared dictionary with locks in it
    Dictionary keys are strings
    """

    __locks = {}
    __locker_lock = Lock()
    logger = logging.getLogger()

    @classmethod
    def is_released(cls, lock):
        """
        A callback that is called by a lock when its count is down to 0
        Lock is then removed from the global locks dictionary
        """
        cls.__locks.pop(lock.lock_id)

    @classmethod
    def get_lock(cls, lock_id):
        """
        Return a lock for a given lock id
        It can be either existing one or a new one will be created
        """
        with Locker.__locker_lock:
            lock = cls.__locks.get(lock_id, RemarkableLock(lock_id, cls))
            cls.__locks[lock_id] = lock

        return lock

    @classmethod
    @contextmanager
    def get_nonblocking_lock(cls, lock_id):
        """
        Return a non blocking lock or throw LockedException
        """
        lock = cls.get_lock(lock_id)
        if not lock.acquire(blocking=False):
            raise LockedException(f'Object "{lock_id}" is curretly locker by other process')
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
        return {lock_id: lock.lock_count for lock_id, lock in cls.__locks.items()}


class LockedException(Exception):
    """
    Exception that should be thrown if nonblocking lock could not be acquired
    """
