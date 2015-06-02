from threading import RLock, Event, Lock
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
    ## we also have a dict of Lock which can be release from different threads
    thread_lock_dictionary = defaultdict(Lock)
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

    ### Thread sharable lock methods: can be released by different threads
    ### mostly needed for submission time locks before putting to Queue
    def thread_lock(self, lock_id):
        """
        Create and return Lock object to be shared between threads
        """
        with self.internal_lock:
            lock = self.thread_lock_dictionary[lock_id]
        return lock

    def thread_acquire(self, lock_id, blocking=True):
        """
        Acquire a Lock in our  global locks dictionary
        """
        with self.internal_lock:
            lock = self.thread_lock_dictionary[lock_id]
            self.logger.log("Acquiring simple lock %s for lock_id %s" % (lock, lock_id))
        return lock.acquire(blocking)

    def thread_release(self, lock_id):
        """
        Releasing a lock but also keeping lock object in dict.
        ???? maybe this should be fixed to not save unneeded not used lock objects
        """
        with self.internal_lock:
            lock = self.thread_lock_dictionary[lock_id]
            self.logger.log("Releasing simple lock %s for lock_id %s" % (lock, lock_id))
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

    def count(self, lock_id):
        with locker.lock(lock_id):
            return self.count_dictionary[lock_id]

    def increment(self, lock_id):
        with locker.lock(lock_id):
            self.count_dictionary[lock_id] += 1
            self.event_dictionary[lock_id].clear()
            self.logger.log("Semaphore {0} incremented -> {1}".format(lock_id, self.count_dictionary[lock_id]))

    def decrement(self, lock_id):
        with locker.lock(lock_id):
            self.count_dictionary[lock_id] = max(0, self.count_dictionary[lock_id]-1) ## floor to 0
            self.logger.log("Semaphore {0} decremented -> {1}".format(lock_id, self.count_dictionary[lock_id]))
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