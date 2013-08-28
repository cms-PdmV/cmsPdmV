from threading import RLock, Event
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


class SemaphoreEvents(object):
    """
    Class works like semaphore (counts number of threads) and uses events to call waiting threads when the counter
    reaches 0. Non-waiting threads should use increment/decrement statements.
    """

    logger = logger('mcm')
    event_dictionary = defaultdict(Event)
    count_dictionary = defaultdict()

    def increment(self, lock_id):
        with locker.lock(lock_id):
            self.count_dictionary[lock_id] += 1
            self.event_dictionary[lock_id].clear()
            self.logger.log("Semaphore {0} incremented".format(lock_id))

    def decrement(self, lock_id):
        with locker.lock(lock_id):
            self.count_dictionary[lock_id] -= 1
            self.logger.log("Semaphore {0} decremented".format(lock_id))
            if self.count_dictionary[lock_id] == 0:
                self.event_dictionary[lock_id].set()

    def wait(self, lock_id, timeout):
        with locker.lock(lock_id):
            event = self.event_dictionary[lock_id]
        return event.wait(timeout)

    def is_set(self, lock_id):
        with locker.lock(lock_id):
            return self.event_dictionary[lock_id].is_set()

semaphore_events = SemaphoreEvents()
