import os
import time
import traceback
import logging

from random import randint
from itertools import izip
from threading import Thread, Lock
from Queue import Queue

from tools.installer import installer
from tools.ssh_executor import ssh_executor
from tools.locator import locator
from tools.locker import locker, semaphore_events
from tools.settings import settings
from couchdb_layer.mcm_database import database
from tools.communicator import communicator
from json_layer.request import request
from json_layer.chained_request import chained_request
from json_layer.batch import batch
from rest_api.BatchPrepId import BatchPrepId
from tools.logger import InjectionLogAdapter

###SETTING THREAD POOL###
class Worker(Thread):
    """Thread executing tasks from a given queue"""
    def __init__(self, tasks, name):
        Thread.__init__(self)
        self.tasks = tasks
        self.daemon = True
        self.worker_name = name
        self.logger = logging.getLogger("mcm_error")
        self.start()

    def run(self):
        while True:
            self.logger.info("Worker %s trying to get work" % (self.worker_name))
            func, args, kargs = self.tasks.get()
            try:
                self.logger.info("Worker %s acquired task: %s" % (self.worker_name, func))
                func(*args, **kargs)
            except Exception, e:
                self.logger.error("Exception in '%s' thread: %s Traceback:\n%s" % (
                        self.worker_name, str(e), traceback.format_exc()))

            finally:
                self.tasks.task_done() ## do we want to mark task_done if it crashed?

class ThreadPool:
    """Pool of threads consuming tasks from a queue"""
    def __init__(self, name, max_workers):
        self.tasks = Queue(0)
        self.name = name
        self.worker_number = max_workers
        self.logger = logging.getLogger("mcm_error")
        worker_name_pool = ["Antanas", "Adrian", "Giovanni", "Gaelle", "Phat"]

        for i in range(self.worker_number): #number should be taken from DB
            _name = "%s-%s" % (worker_name_pool[randint(0,4)], i)
            Worker(self.tasks, _name) ##number of concurrent worker threads

    def add_task(self, func, *args, **kargs):
        """Add a task to the queue"""
        self.logger.info("Adding a task: %s to the Queue %s. Currently in Queue: %s" % (
                func, id(self.tasks), self.get_queue_length()))

        self.tasks.put((func, args, kargs))

    def wait_completion(self):
        """Wait for completion of all the tasks in the queue"""
        self.tasks.join()

    def get_queue_length(self):
        """Return the number of tasks waiting in the Queue"""
        return self.tasks.qsize()

###END OF THREAD POOL##

submit_pool = ThreadPool("submission", settings().get_value('threads_num_submission'))

class Handler():
    """
    A class which manages locks for the resources.
    """
    logger = logging.getLogger("mcm_error")
    hname = '' # handler's name
    lock = None

    def __init__(self, **kwargs):
        if 'lock' not in kwargs:
            self.lock = Lock()
        else:
            self.lock = kwargs['lock']

class ConfigMakerAndUploader(Handler):
    """
    Class preparing and uploading (if needed) the configuration
    and adding it for the given request
    """

    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.prepid = kwargs["prepid"]
        self.request_db = database("requests")

    def internal_run(self):
        if not self.lock.acquire(blocking=False):
            self.logger.error("Could not acquire lock for ConfigMakerAndUploader. prepid %s" % (
                    self.prepid))
            return False
        try:
            self.logger.info("Acquired lock for ConfigMakerAndUploader. prepid %s" % (
                    self.prepid))
            req = request(self.request_db.get(self.prepid))
            ret = req.prepare_and_upload_config()
            return True if ret else False
        finally:
            self.logger.info("Releasing a lock for ConfigMakerAndUploader. prepid %s" % (
                    self.prepid))

            self.lock.release()

class RequestSubmitter(Handler):
    """
    Class injecting the request
    """

    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.prepid = kwargs["prepid"]
        self.check_approval = kwargs["check_approval"] if "check_approval" in kwargs else True
        self.request_db = database('requests')
        self.inject_logger = InjectionLogAdapter(logging.getLogger("mcm_inject"),
                {'handle': self.prepid})

    def injection_error(self, message, req):
        self.inject_logger.info(message)
        if req:
            req.test_failure(message, what='Request injection')

    def check_request(self):
        if not self.request_db.document_exists(self.prepid):
            self.inject_logger.error("The request {0} does not exist".format(self.prepid))

            return False, None
        req = request(self.request_db.get(self.prepid))
        if self.check_approval and req.get_attribute('approval') != 'submit':
            self.injection_error(
                "The request is in approval {0}, while submit is required".format(
                        req.get_attribute('approval')), req)

            return False, None
        if req.get_attribute('status') != 'approved':
            self.injection_error(
                "The request is in status {0}, while approved is required".format(
                        req.get_attribute('status')), req)

            return False, None
        return True, req

    def internal_run(self):
        try:
            if not self.lock.acquire(blocking=False):
                self.injection_error('Couldnt acquire lock', None)
                return False
            try:
                okay, req = self.check_request()
                if not okay: return False
                batch_name = BatchPrepId().next_id(req.json())
                semaphore_events.increment(batch_name) # so it's not possible to announce while still injecting
                executor = ssh_executor(server='vocms081.cern.ch')
                try:
                    cmd = req.prepare_submit_command()
                    self.inject_logger.info("Command being used for injecting request {0}: {1}".format(
                            self.prepid, cmd))

                    _, stdout, stderr = executor.execute(cmd)
                    if not stdout and not stderr:
                        self.injection_error('ssh error for request {0} injection'.format(
                                self.prepid), req)

                        return False
                    output = stdout.read()
                    error = stderr.read()
                    self.injection_error(output, None)
                    self.injection_error(error, None)

                    if error and not output: # money on the table that it will break as well?
                        self.injection_error('Error in wmcontrol: {0}'.format(error), req)
                        return False

                    injected_requests = [l.split()[-1] for l in output.split('\n') if
                            l.startswith('Injected workflow:')]

                    if not injected_requests:
                        self.injection_error('Injection has succeeded but no request manager names were registered. Check with administrators. \nOutput: \n%s\n\nError: \n%s'%(
                                output, error), req)

                        return False

                    ## another great structure
                    added_requests = [
                            {'name': app_req, 'content': {'pdmv_prep_id': self.prepid}}
                            for app_req in injected_requests]

                    requests = req.get_attribute('reqmgr_name')
                    requests.extend(added_requests)
                    req.set_attribute('reqmgr_name', requests)

                    #inject to batch
                    with locker.lock(batch_name):
                        bdb = database('batches')
                        bat = batch(bdb.get(batch_name))
                        bat.add_requests(added_requests)
                        bat.update_history({'action': 'updated', 'step': self.prepid})
                        saved = bdb.update(bat.json())
                    if not saved:
                        self.injection_error(
                            'There was a problem with registering request in the batch {0}'.format(
                                    batch_name), req)

                        return False
                    #and in the end update request in database
                    req.update_history({'action': 'inject', 'step' : batch_name})
                    req.set_status(step=req._json_base__status.index('submitted'),
                            with_notification=True)

                    saved = self.request_db.update(req.json())
                    if not saved:
                        self.injection_error('Could not update request {0} in database'.format(
                                self.prepid), req)

                        return False
                    for added_req in added_requests:
                        self.inject_logger.info('Request {0} sent to {1}'.format(
                            added_req['name'], batch_name))

                    return True
                finally: ##lover batch semahore, created on submission time
                    semaphore_events.decrement(batch_name)

            finally: ##finally release Sumbitter lock
                self.lock.release()
                try:
                    executor.close_executor()
                except UnboundLocalError:
                    pass
        except Exception as e:
            self.injection_error(
                'Error with injecting the {0} request:\n{1}'.format(
                        self.prepid, traceback.format_exc()), None)

class RequestInjector(Handler):
    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.lock = kwargs["lock"] ##internal process lock for recources
        self.prepid = kwargs["prepid"]
        self.uploader = ConfigMakerAndUploader(**kwargs)
        self.submitter = RequestSubmitter(**kwargs)
        self.queue_lock = kwargs["queue_lock"] ##lock if request is put in processing POOL
        self.inject_logger = InjectionLogAdapter(logging.getLogger("mcm_inject"),
                {'handle': self.prepid})

    def internal_run(self):
        self.inject_logger.info('## Logger instance retrieved')

        with locker.lock('{0}-wait-for-approval'.format(self.prepid)):
            self.logger.info("Acquire lock for RequestInjector. prepid %s" % (self.prepid))
            if not self.lock.acquire(blocking=False):
                return {
                    "prepid": self.prepid,
                    "results": False,
                    "message": "The request with name {0} is being handled already".format(self.prepid)
                }
            try:
                if not self.uploader.internal_run():
                    return {
                        "prepid": self.prepid,
                        "results": False,
                        "message": "Problem with uploading the configuration for request {0}".format(self.prepid)
                    }
                __ret = self.submitter.internal_run()
                self.inject_logger.info('Request submitter returned: %s' % (__ret))

            finally:
                self.lock.release()
                self.queue_lock.release()

class RequestApprover(Handler):
    def __init__(self, batch_id, workflows):
        self.workflows = workflows
        self.batch_id = batch_id

    def make_command(self):
        l_type = locator()
        command = 'export X509_USER_PROXY=/afs/cern.ch/user/p/pdmvserv/private/$HOSTNAME/voms_proxy.cert\n'
        command += 'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh\n'
        test_path = ''
        test_params = ''
        if l_type.isDev():
            test_path = '_testful'
            test_params = '--wmtest --wmtesturl cmsweb-testbed.cern.ch'
        command += 'python /afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol%s/wmapprove.py --workflows %s %s\n' % (test_path, self.workflows, test_params)
        return command

    def send_email_failure(self, output, error):
        com = communicator()
        users_db = database('users')
        query = users_db.construct_lucene_query({'role' : 'production_manager'})
        production_managers = users_db.full_text_search('search', query, page=-1)
        subject = "There was an error while trying to approve workflows"
        text = "Workflows: %s\nOutput:\n%s\nError output: \n%s" % (self.workflows, output, error)
        com.sendMail(
            map(lambda u: u['email'], production_managers),
            subject,
            text
        )

    def internal_run(self):
        command = self.make_command()
        executor = ssh_executor(server='vocms081.cern.ch')
        try:
            self.logger.info("Command being used for approve requests: " + command)
            trails = 1
            while trails < 3:
                self.logger.info("Wmapprove trail number: %s" % trails)
                _, stdout, stderr = executor.execute(command)
                if not stdout and not stderr:
                    self.logger.error('ssh error for request approvals, batch id: ' + self.batch_id)
                    return
                output = stdout.read()
                error = stderr.read()
                self.logger.info('Wmapprove output: %s' % output)
                if not error and 'Something went wrong' not in output:
                    break
                time.sleep(3)
                trails += 1
            if error or 'Something went wrong' in output:
                message = 'Error in wmapprove: %s' % (output if 'Something went wrong' in output else error)
                self.logger.error(message)
                self.send_email_failure(output, error)
                return {
                    'results': False,
                    'message': message
                }
        except Exception as e:
            message = 'Error while approving requests, batch id: %s, message: %s' % (self.batch_id, str(e))
            self.logger.error(message)
            self.send_email_failure('', message)
            return {
                'results': False,
                'message': message
            }
        return {'results': True}

class ChainRequestInjector(Handler):
    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.lock = kwargs["lock"]
        self.prepid = kwargs["prepid"]
        self.check_approval = kwargs["check_approval"] if "check_approval" in kwargs else True
        self.queue_lock = kwargs["queue_lock"] ##lock if request is put in processing POOL

    def injection_error(self, message, rs):
        self.logger.error(message)
        for r in rs:
            r.test_failure(message, what='Request injection in chain')
            pass

    def make_command(self,mcm_r=None):
        l_type = locator()
        cmd = 'cd %s \n' % ( l_type.workLocation())
        if mcm_r:
            cmd += mcm_r.make_release()
        cmd += 'export X509_USER_PROXY=/afs/cern.ch/user/p/pdmvserv/private/$HOSTNAME/voms_proxy.cert\n'
        there = ''
        if l_type.isDev():
            there = '--wmtest --wmtesturl cmsweb-testbed.cern.ch'
        cmd += 'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n'
        cmd += 'wmcontrol.py --dont_approve --url-dict %s/public/restapi/chained_requests/get_dict/%s %s \n'%(l_type.baseurl(), self.prepid, there)
        return cmd

    def internal_run(self):
        if not self.lock.acquire(blocking=False):
            self.logger.error("Could not acquire lock for ChainRequestInjector. prepid %s" % (
                    self.prepid))

            return False
        try:
            crdb = database('chained_requests')
            rdb = database('requests')
            batch_name = None
            if not crdb.document_exists( self.prepid ):
                ## it's a request actually, pick up all chains containing it
                mcm_r = rdb.get( self.prepid )
                #mcm_crs = crdb.query(query="root_request==%s"% self.prepid) ## not only when its the root of
                mcm_crs = crdb.query(query="contains==%s" % self.prepid)
                task_name = 'task_' + self.prepid
                batch_type = 'Task_' + mcm_r['member_of_campaign']
            else:
                mcm_crs = [crdb.get( self.prepid )]
                task_name = self.prepid
                batch_type = mcm_crs[-1]['member_of_campaign']

            if len(mcm_crs)==0:
                return False
            mcm_rs=[]
            ## upload all config files to config cache, with "configuration economy" already implemented
            for cr in mcm_crs:
                mcm_cr = chained_request(cr)
                chain = mcm_cr.get_attribute('chain')[mcm_cr.get_attribute('step'):]
                for request_prepid in chain:
                    mcm_rs.append(request(rdb.get(request_prepid)))
                    if self.check_approval and mcm_rs[-1].get_attribute('approval') != 'submit':
                        self.logger.error('requests %s is in "%s"/"%s" status/approval, requires "approved"/"submit"'%(
                                request_prepid, mcm_rs[-1].get_attribute('status'),
                                mcm_rs[-1].get_attribute('approval')))

                        return False

                    if mcm_rs[-1].get_attribute('status') != 'approved':
                        ## change the return format to percolate the error message
                        self.logger.error('requests %s in in "%s"/"%s" status/approval, requires "approved"/"submit"'%(
                                request_prepid, mcm_rs[-1].get_attribute('status'),
                                mcm_rs[-1].get_attribute('approval')))

                        return False

                    uploader = ConfigMakerAndUploader(prepid=request_prepid, lock=locker.lock(request_prepid))
                    if not uploader.internal_run():
                        mcm_cr.notify(
                            'Configuration upload failed',
                            "There was a problem uploading the configuration for request %s"  % (request_prepid)
                        )
                        self.logger.error('Problem with uploading the configuration for request %s' % (request_prepid))
                        return False

            mcm_r = mcm_rs[-1]
            batch_name = BatchPrepId().next_batch_id(batch_type, create_batch=True)
            semaphore_events.increment(batch_name)
            self.logger.error('found batch %s'% batch_name)

            with ssh_executor(server = 'vocms081.cern.ch') as ssh:
                cmd = self.make_command(mcm_r)
                self.logger.error('prepared command %s' % cmd)
                ## modify here to have the command to be executed
                _, stdout, stderr = ssh.execute(cmd)
                output = stdout.read()
                error = stderr.read()
                self.logger.info(output)
                self.logger.info(error)
                injected_requests = [l.split()[-1] for l in output.split('\n') if
                                     l.startswith('Injected workflow:')]

                if not injected_requests:
                    self.injection_error('Injection has succeeded but no request manager names were registered. Check with administrators. \nOutput: \n%s\n\nError: \n%s'%(
                            output, error), mcm_rs)

                    return False

                # what gets printed into the batch object
                added_requests = []
                once=set()
                for mcm_r in mcm_rs:
                    if mcm_r.get_attribute('prepid') in once: continue
                    once.add(mcm_r.get_attribute('prepid'))
                    added = [{'name': app_req,
                        'content': {'pdmv_prep_id': mcm_r.get_attribute('prepid')}}
                        for app_req in injected_requests]

                    added_requests.extend(added)

                ##edit the batch object
                with locker.lock(batch_name):
                    bdb = database('batches')
                    bat = batch(bdb.get(batch_name))
                    bat.add_requests(added_requests)
                    bat.update_history({'action': 'updated', 'step': task_name })
                    bat.reload()

                ## reload the content of all requests as they might have changed already
                added = [{'name': app_req, 'content': {'pdmv_prep_id': task_name }}
                    for app_req in injected_requests]

                seen = set()
                for cr in mcm_crs:
                    mcm_cr = chained_request(cr)
                    chain = mcm_cr.get_attribute('chain')[mcm_cr.get_attribute('step'):]
                    message = ""
                    for rn in chain:
                        if rn in seen: continue # don't do it twice
                        seen.add(rn)
                        mcm_r = request(rdb.get(rn))
                        message += mcm_r.textified()
                        message += "\n\n"
                        mcm_r.set_attribute('reqmgr_name', added)
                        mcm_r.update_history({'action': 'inject','step' : batch_name})
                        if not self.check_approval:
                            mcm_r.set_attribute('approval', 'submit')
                        ##set the status to submitted
                        mcm_r.set_status(step=mcm_r._json_base__status.index('submitted'),
                            with_notification=False)

                        mcm_r.reload()
                        mcm_cr.set_attribute('last_status', mcm_r.get_attribute('status'))
                    ## re-get the object
                    mcm_cr = chained_request(crdb.get(cr['prepid']))
                    #take care of changes to the chain
                    mcm_cr.update_history({'action' : 'inject','step': batch_name})
                    mcm_cr.set_attribute('step', len(mcm_cr.get_attribute('chain'))-1)
                    mcm_cr.set_attribute('status','processing')
                    mcm_cr.notify('Injection succeeded for %s' % mcm_cr.get_attribute('prepid'),
                                  message)

                    mcm_cr.reload()

                return True
        except Exception as e:
            self.injection_error("Error with injecting chains for %s :\n %s" % (
                self.prepid, traceback.format_exc()),[])

        finally: ##we decrement batch id and release lock on prepid+lower semaphore
            if batch_name: ##ditry thing for now. Because batch name can be None for certain use-cases in code above
                semaphore_events.decrement(batch_name)
            self.lock.release()
            self.queue_lock.release()