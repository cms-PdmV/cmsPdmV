"""
Module that has all classes used for request submission to computing
"""
import logging
import time
import traceback
import json
from threading import Thread
from queue import Queue, Empty


class Worker(Thread):
    """
    A single worker thread that loops and submits requests from the queue
    """

    def __init__(self, name, worker_pool):
        Thread.__init__(self)
        self.name = name
        self.worker_pool = worker_pool
        self.queue = self.worker_pool.task_queue
        self.logger = logging.getLogger('mcm_error')
        self.logger.debug('Worker "%s" is being created', self.name)
        self.job_name = None
        self.job_start_time = None
        self.running = True
        self.start()

    def run(self):
        self.logger.debug('Worker "%s" is starting', self.name)
        while self.running:
            try:
                job_name, function, args, kwargs = self.queue.get(timeout=1)
                self.job_name = job_name
                self.job_start_time = time.time()
                self.logger.debug('Worker "%s" got a task "%s". Queue size %s',
                                  self.name,
                                  job_name,
                                  self.queue.qsize())
                try:
                    function(*args, **kwargs)
                except Exception as ex:
                    self.logger.error('Exception in "%s" during task "%s"',
                                      self.name,
                                      job_name)
                    self.logger.error(traceback.format_exc())
                    self.logger.error(ex)
                finally:
                    self.logger.debug('Worker "%s" has finished a task "%s". Queue size %s',
                                      self.name,
                                      job_name,
                                      self.queue.qsize())
                    self.job_name = None
                    self.job_start_time = 0
            except Empty:
                # If there is nothing in the queue, stop running
                self.running = False
                # Stop existing
                self.worker_pool.remove_worker(self)

    def join(self, timeout=None):
        self.running = False
        self.logger.debug('Joining the "%s" worker', self.name)
        Thread.join(self, timeout)


class WorkerPool:
    """
    Pool that contains all worker threads
    """

    def __init__(self, max_workers, task_queue):
        self.logger = logging.getLogger('mcm_error')
        self.workers = []
        self.max_workers = max_workers
        self.task_queue = task_queue
        self.worker_counter = 0

    def add_task(self, name, function, *args, **kwargs):
        """
        Add a task to a queue
        """
        self.logger.info('Adding a task "%s". Queue size %s', name, self.get_queue_size())
        self.task_queue.put((name, function, args, kwargs))
        if len(self.workers) < self.max_workers:
            worker = Worker(f'worker-{self.worker_counter}', self)
            self.workers.append(worker)
            self.worker_counter += 1

    def get_queue_size(self):
        """
        Return queue size
        """
        return self.task_queue.qsize()

    def remove_worker(self, worker):
        """
        Remove worker from worker pool
        """
        self.logger.debug('Worker %s will be removed', worker.name)
        self.workers.remove(worker)
        if not self.workers:
            # If last worker is removed, reset IDs to 0
            self.worker_counter = 0

    def get_worker_status(self):
        """
        Return a dictionary where keys are worker names and values are dictionaries
        of job names and time in seconds that job has been running for (if any)
        """
        status = {}
        now = time.time()
        for worker in self.workers:
            job_time = int(now - worker.job_start_time if worker.job_name else 0)
            status[worker.name] = {'job_name': worker.job_name,
                                   'job_time': job_time}

        return status


class Submitter:
    """
    Request submitter has a reference to the whole worker pool as well as job queue
    """

    # A FIFO queue. maxsize is an integer that sets the upperbound
    # limit on the number of items that can be placed in the queue.
    # If maxsize is less than or equal to zero, the queue size is infinite.
    __task_queue = Queue(maxsize=0)
    # All worker threads
    __max_workers = 15
    __worker_pool = WorkerPool(max_workers=__max_workers,
                               task_queue=__task_queue)

    def __init__(self):
        self.logger = logging.getLogger('mcm_error')

    def add_task(self, name, function, *args, **kwargs):
        """
        Add a job to do to submission queue
        Name must be unique in the queue
        """
        for task in list(Submitter.__task_queue.queue):
            if task[0] == name:
                raise Exception(f'Task "{name}" is already in the queue')

        for worker, worker_info in Submitter.__worker_pool.get_worker_status().items():
            if worker_info['job_name'] == name:
                raise Exception(f'Task "{name}" is being worked on by "{worker}"')

        self.__worker_pool.add_task(name, function, *args, **kwargs)

    def get_queue_size(self):
        """
        Return size of submission queue
        """
        return self.__worker_pool.get_queue_size()

    def get_worker_status(self):
        """
        Return dictionary of all worker statuses
        """
        return self.__worker_pool.get_worker_status()

    def get_names_in_queue(self):
        """
        Return a list of task names that are waiting in the queue
        """
        return [x[0] for x in self.__task_queue.queue]

    def submit_job_dict(self, job_dict, connection):
        """
        Submit job dictionary to ReqMgr2
        """
        headers = {'Content-type': 'application/json',
                   'Accept': 'application/json'}

        reqmgr_response = None
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                # Submit job dictionary (ReqMgr2 JSON)
                reqmgr_response = connection.api('POST',
                                                '/reqmgr2/data/request',
                                                job_dict,
                                                headers)
                self.logger.debug(reqmgr_response)
                workflow_name = json.loads(reqmgr_response).get('result', [])[0].get('request')
                break
            except Exception as ex:
                if reqmgr_response:
                    error_message = str(reqmgr_response).replace('\\n', '\n')
                else:
                    error_message = str(ex)

                prepid = job_dict.get('PrepID')
                if attempt < max_attempts:
                    # Ugly hacks because WMCore has a bug
                    if ('Invalid spec parameter value: int()' in error_message
                        or 'a number is required, not NoneType' in error_message):
                        sleep = (attempt + 1)**3
                        self.logger.warning('Response with "Invalid spec parameter value: int()", '
                                            'sleep for %ss and try %s again...', sleep, prepid)
                        time.sleep(sleep)
                        self.logger.info('Trying to submit %s job dict again', prepid)
                        continue

                raise Exception(f'Error submitting {prepid} to ReqMgr2:\n{error_message}')

        return workflow_name

    def approve_workflow(self, workflow_name, connection):
        """
        Approve workflow in ReqMgr2
        """
        headers = {'Content-type': 'application/json',
                   'Accept': 'application/json'}

        try:
            # Try to approve workflow (move to assignment-approved)
            # If it does not succeed, ignore failure
            connection.api('PUT',
                           f'/reqmgr2/data/request/{workflow_name}',
                           {'RequestStatus': 'assignment-approved'},
                           headers)
        except Exception as ex:
            self.logger.error('Error approving %s: %s', workflow_name, str(ex))
            return False

        return True


class RequestSumbmitter(Submitter):


    def add(self, request):
        pass