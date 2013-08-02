from threading import RLock
from tools.logger import logger
from collections import defaultdict


class Locker(object):
    """
    Class provides interface for locking mechanism using some kind of IDs passed as parameters in methods.

    By using the lock method it can be used as a context manager:
    locker = Locker()
    with locker.lock(id):
        do something locked
    after releasing lock
    """

    # using reentrant lock so other threads don't release it
    internal_lock = RLock()
    lock_dictionary = defaultdict(RLock)
    logger = logger('mcm')

    def lock(self, lock_id):
        # defaultdict and setdefault are not atomic in python 2,6, some manual locking needed
        with self.internal_lock:
            # obtaining the lock has to be inside internal_lock space, as we cannot both obtain a lock and
            # do something to it without risking race conditions
            lock = self.lock_dictionary[lock_id]
        return lock

    def acquire(self, lock_id, blocking=True):
        with self.internal_lock:
            lock = self.lock_dictionary[lock_id]
            self.logger.log("Acquiring lock %s for lock_id %s" % (lock, lock_id))
        return lock.acquire(blocking)

    def release(self, lock_id):
        with self.internal_lock:
            lock = self.lock_dictionary[lock_id]
            self.logger.log("Releasing lock %s for lock_id %s" % (lock, lock_id))
        return lock.release()


locker = Locker()