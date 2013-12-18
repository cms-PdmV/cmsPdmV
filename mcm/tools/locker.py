from threading import RLock, Event, BoundedSemaphore
from tools.logger import logfactory
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
    logger = logfactory

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

    logger = logfactory
    event_dictionary = defaultdict(Event)
    count_dictionary = defaultdict(int)

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
            #return self.event_dictionary[lock_id].is_set()
            if lock_id in self.event_dictionary:
                return self.event_dictionary[lock_id].is_set()
            else:
                ## because the default oonstructor is with is_set=False
                #in case the batch was created, sever cycled, and one tries to announce it on the "second" session
                return True

semaphore_events = SemaphoreEvents()


from tools.settings import settings
class BoundedSemaphoreChangeableMax(object):
    """
    Class works like bounded semaphore, but the max value can be changed - either directly or the max can be taken
    from function specified instead of max_val parameter (then the max property setter won't make difference).
    """

    def __init__(self, max_val = 1, max_func = None):
        self._max = max_val
        self._max_func = max_func
        self._current = 0
        self._lock = RLock()
        self._event = Event()
        self.logger = logfactory


    @property
    def max(self):
        with self._lock:
            return self._max_func() if self._max_func else self._max

    @max.setter
    def max(self, value):
        with self._lock:
            self._max = value

    def acquire(self, blocking = True):
        while True:
            with self._lock:
                current_max = self.max
                if self._current < current_max:
                    self._current += 1
                    self.logger.log("Bounded semaphore's value incremented to: {0} , maximum: {1}".format(self._current, current_max))
                    if self._current == current_max:
                        self._event.clear()
                    return True
                if not blocking:
                    return False
            self._event.wait()

    def release(self):
        with self._lock:
            self._current -= 1
            self.logger.log("Bounded semaphore's value decremented to: {0} , maximum: {1}".format(self._current, self.max))
            if self._current < 0:
                raise ValueError("Semaphore released too many times!")
            self._event.set()

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

semaphore_thread_number = BoundedSemaphoreChangeableMax(max_func = lambda : settings().get_value('max_number_of_threads'))