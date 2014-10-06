import os
from threading import Thread, Lock
import time
import traceback
from tools.batch_control import batch_control
from tools.installer import installer
from tools.locker import semaphore_thread_number
from tools.logger import logfactory
from tools.request_to_wma import request_to_wmcontrol
from tools.ssh_executor import ssh_executor
from tools.locator import locator
from tools.locker import locker, semaphore_events
from tools.settings import settings
from couchdb_layer.mcm_database import database
from json_layer.request import request
from json_layer.chained_request import chained_request
from json_layer.batch import batch
from rest_api.BatchPrepId import BatchPrepId
from itertools import izip


class PoolOfHandlers(Thread):
    """
    Class used for instantiating and taking care of running a number of handlers in parallel. It provides them
    with lock for protection of concurrently-vulnerable parts of program (e.g. database access).
    """

    logger = logfactory

    def __init__(self, handler_class, arguments):
        """
        handler_class is used to instantiate the objects.

        arguments parameter is a list of arguments (dictionnaries) passed to the handler_class' constructor method.
        """
        Thread.__init__(self)
        try:
            self._handlers_list = []
            self._lock = Lock()
            for arg in arguments:
                if not isinstance(arg, dict):  # if arg is e.g. list
                    raise TypeError("Arguments should be a list of dictionaries")
                arg['lock'] = self._lock
                self._handlers_list.append(handler_class(**arg))
            self.logger.log("Instantiated %s handlers %s in pool" % (len(arguments), handler_class.__name__))
        except:
            self.logger.error('Failed to instantiate handlers \n %s' % (traceback.format_exc()))

    def run(self):
        """
        Starts the handlers from pool.
        """
        self.logger.log("Starting %s handlers" % (len(self._handlers_list)))
        for handler_object in self._handlers_list:
            handler_object.start()
        for handler_object in self._handlers_list:
            handler_object.join()


class Handler(Thread):
    """
    A class which threads a list of operations. Override internal_run for main processing and rollback if you want to
    have a rollback option in case of process failure.
    """
    logger = logfactory
    hname = '' # handler's name
    lock = None
    thread_semaphore = semaphore_thread_number

    def __init__(self, **kwargs):
        Thread.__init__(self)
        self.res = []
        if 'lock' not in kwargs:
            self.lock = Lock()
        else:
            self.lock = kwargs['lock']

    def run(self):
        """
        Should not be overridden! Use internal_run instead.
        """
        with semaphore_thread_number:
            try:
                self.internal_run()
                # set the status, save the request, notify ...
                pass
            except:
                ## catch anything that comes this way and handle it
                # logging, rolling back the request, notifying, ...
                self.rollback()
                pass

    def internal_run(self):
        pass

    def rollback(self):
        pass

    def status(self):
        return self.res


class ConfigMakerAndUploader(Handler):
    """
    Class preparing and uploading (if needed) the configuration and adding it for the given request
    """

    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.prepid = kwargs["prepid"]
        self.request_db = database("requests")

    def internal_run(self):
        if not self.lock.acquire(blocking=False):
            return False
        try:
            req = request(self.request_db.get(self.prepid))
            ret = req.prepare_and_upload_config()
            return True if ret else False
        finally:
            self.lock.release()


class RuntestGenvalid(Handler):
    """
    operate the run test, operate the gen_valid, upload to the gui and toggles the status to validation
    """

    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.rid = kwargs['rid']
        self.db = database('requests')

    def internal_run(self):
        location = installer(self.rid, care_on_existing=False, clean_on_exit=True)
        try:
            test_script = location.location() + 'validation_run_test.sh'
            timeout=None
            with open(test_script, 'w') as there:
                ## one has to wait just a bit, so that the approval change operates, and the get retrieves the latest greatest _rev number
                #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
                time.sleep(10)
                mcm_r = request(self.db.get(self.rid))
                #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
                ## the following does change something on the request object, to be propagated in case of success
                there.write(mcm_r.get_setup_file(location.location(), run=True, do_valid=True))
                timeout = mcm_r.get_timeout()

            batch_test = batch_control(self.rid, test_script, timeout=timeout)
            try:
                success = batch_test.test()
            except:
                batch_test.log_err = traceback.format_exc()
                success = False

            if success:
                self.logger.log("batch_test result is %s" % success)
                (success,batch_test.log_err) = mcm_r.pickup_all_performance(location.location())

            self.logger.error('I came all the way to here and %s (request %s)' % ( success, self.rid ))
            if not success:
                mcm_r = request(self.db.get(self.rid))
                ## need to provide all the information back
                if settings().get_value('check_term_runlimit') and "TERM_RUNLIMIT" in batch_test.log_out:
                    no_success_message = "LSF job was terminated after reaching run time limit.\n\n"
                    no_success_message += "Average CPU time per event specified for request was {0} seconds. \n\n".format(
                        mcm_r.get_attribute("time_event"))
                    additiona_message = "Time report not found in LSF job."
                    split_log = batch_test.log_err.split('\n')
                    for l_id, line in izip(reversed(xrange(len(split_log))), reversed(split_log)):
                        if "TimeReport>" in line:
                            additiona_message = "\n".join(split_log[l_id:l_id + 12])
                    no_success_message += additiona_message
                else:
                    no_success_message = '\t .out \n%s\n\t .err \n%s\n ' % ( batch_test.log_out, batch_test.log_err)
                    #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
                # reset the content of the request
                mcm_r.test_failure(message=no_success_message, what='Validation run test', rewind=True)
                #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
            else:
                #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
                ## change the status with notification
                mcm_current = request(self.db.get(self.rid))
                if mcm_current.json()['_rev'] == mcm_r.json()['_rev']:
                    ## it's fine to push it through
                    mcm_r.set_status(with_notification=True)
                    saved = self.db.update(mcm_r.json())
                    if not saved:
                        mcm_current.test_failure(message='The request could not be saved after the run test procedure',
                                                 what='Validation run test', rewind=True)
                else:
                    mcm_current.test_failure(
                        message='The request has changed during the run test procedure, preventing from being saved',
                        what='Validation run test', rewind=True)
                    #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
        except:
            mess = 'We have been taken out of run_safe of runtest_genvalid for %s because \n %s \n During an un-excepted exception. Please contact support.' % (
                self.rid, traceback.format_exc())
            self.logger.error(mess)
            mcm_r = request(self.db.get(self.rid))
            mcm_r.test_failure(message=mess, what='Validation run test', rewind=True)
        finally:
            location.close()



class RunChainValid(Handler):
    """
    Operate the full testing of a chained request
    """
    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.crid = kwargs['crid']
        self.scratch = False
        if 'scratch' in kwargs:
            self.scratch = kwargs['scratch']

    def reset_all(self, message, what = 'Chained validation run test', notify_one=None):
        crdb = database('chained_requests')
        rdb = database('requests')
        mcm_cr = chained_request(crdb.get(self.crid))
        if self.scratch:
            chain = mcm_cr.get_attribute('chain')
        else:
            chain=mcm_cr.get_attribute('chain')[mcm_cr.get_attribute('step'):]

        for rid in chain:
            mcm_r = request( rdb.get( rid ) )

            ## do not reset anything that does not look ok already
            # this might leave things half-way inconsistent in terms of status
            if mcm_r.get_attribute('status') != 'new': continue

            notify = True
            if notify_one and notify_one != rid:
                notify = False
            mcm_r.test_failure( message, 
                                what = what,
                                rewind=True,
                                with_notification=notify)


    def internal_run(self):
        if not self.lock.acquire(blocking=False):
            return False
        from tools.installer import installer
        from tools.batch_control import batch_control 
        location = installer( self.crid, care_on_existing=False, clean_on_exit=True)
        try:

            crdb = database('chained_requests')
            rdb = database('requests')
            mcm_cr = chained_request(crdb.get(self.crid))
            mcm_rs = []
            if self.scratch:
                chain=mcm_cr.get_attribute('chain')
            else:
                chain=mcm_cr.get_attribute('chain')[mcm_cr.get_attribute('step'):]
                
            for rid in chain:
                mcm_rs.append( request( rdb.get( rid ) ))

            test_script = location.location() + 'validation_run_test.sh'
            timeout=None
            with open(test_script, 'w') as there:
                there.write(mcm_cr.get_setup(directory=location.location(), run=True, validation=True,scratch=self.scratch))
                timeout = mcm_cr.get_timeout(scratch=self.scratch)
            batch_test = batch_control( self.crid, test_script, timeout=timeout)
            
            try:
                success = batch_test.test()
            except:
                self.logger.error('exception in chain batch_control.test()\n'+ traceback.format_exc() )
                self.reset_all( traceback.format_exc() )
                return

            if not success:
                self.reset_all( '\t .out \n%s\n\t .err \n%s\n ' % ( batch_test.log_out, batch_test.log_err) )
                return

            last_fail=mcm_rs[0]
            trace=""
            for mcm_r in mcm_rs:
                ### if not mcm_r.is_root: continue ##disable for dr request
                if mcm_r.get_attribute('status') != 'new': continue ## should not change things to request already in validation status, or more
                (success,trace) = mcm_r.pickup_all_performance(location.location())
                if not success: 
                    last_fail = mcm_r
                    break

            self.logger.error('I came all the way to here and %s (request %s)' % ( success, self.crid ))

            if success:
                for (i_r,mcm_r) in enumerate(mcm_rs):
                    mcm_current = request( rdb.get(mcm_r.get_attribute('prepid')))
                    if mcm_current.json()['_rev'] == mcm_r.json()['_rev']:
                        if mcm_current.get_attribute('status') != 'new': continue ## should not toggle to the next status for things that are not 'new'
                        mcm_r.set_status(with_notification=True)
                        if not mcm_r.reload():
                            self.reset_all( 'The request %s could not be saved after the runtest procedure' % (mcm_r.get_attribute('prepid')))
                            return
                    else:
                        self.reset_all( 'The request %s has changed during the run test procedure'%(mcm_r.get_attribute('prepid')), notify_one = mcm_r.get_attribute('prepid'))
                        return        
            else:
                self.reset_all( trace , notify_one = last_fail.get_attribute('prepid') )
                return

        except:
            mess = 'We have been taken out of run_safe of runtest_genvalid for %s because \n %s \n During an un-excepted exception. Please contact support.' % (
                self.crid, traceback.format_exc())
            self.logger.error(mess)    
        finally:
            self.lock.release()
            location.close() 


class RequestSubmitter(Handler):
    """
    Class injecting the request
    """

    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.prepid = kwargs["prepid"]
        self.check_approval = kwargs["check_approval"] if "check_approval" in kwargs else True
        self.request_db = database('requests')

    def injection_error(self, message, req):
        self.logger.inject(message, handler=self.prepid)
        if req:
            req.test_failure(message, what='Request injection')

    def check_request(self):
        if not self.request_db.document_exists(self.prepid):
            self.logger.inject("The request {0} does not exist".format(self.prepid), level='error', handler=self.prepid)
            return False, None
        req = request(self.request_db.get(self.prepid))
        if self.check_approval and req.get_attribute('approval') != 'submit':
            self.injection_error(
                "The request is in approval {0}, while submit is required".format(req.get_attribute('approval')), req)
            return False, None

        if req.get_attribute('status') != 'approved':
            self.injection_error(
                "The request is in status {0}, while approved is required".format(req.get_attribute('status')), req)
            return False, None

        return True, req

    def internal_run(self):
        try:
            if not self.lock.acquire(blocking=False):
                return False
            try:
                okay, req = self.check_request()
                if not okay: return False
                batch_name = BatchPrepId().next_id(req.json())
                semaphore_events.increment(batch_name) # so it's not possible to announce while still injecting
                executor = ssh_executor(server='pdmvserv-test.cern.ch')
                try:
                    cmd = req.prepare_submit_command(batch_name)
                    self.logger.inject("Command being used for injecting request {0}: {1}".format(self.prepid, cmd),
                                       handler=self.prepid)
                    _, stdout, stderr = executor.execute(cmd)
                    if not stdout and not stderr:
                        self.injection_error('ssh error for request {0} injection'.format(self.prepid), req)
                        return False
                    output = stdout.read()
                    error = stderr.read()
                    if error and not output: # money on the table that it will break as well?
                        self.injection_error('Error in wmcontrol: {0}'.format(error), req)
                        return False
                    injected_requests = [l.split()[-1] for l in output.split('\n') if
                                         l.startswith('Injected workflow:')]
                    approved_requests = [l.split()[-1] for l in output.split('\n') if
                                         l.startswith('Approved workflow:')]
                    if not approved_requests:
                        self.injection_error(
                            'Injection has succeeded but no request manager names were registered. Check with administrators. \nOutput: \n{0}\n\nError: \n{1}'.format(
                                output, error), req)
                        return False
                    objects_to_invalidate = [
                        {"_id": inv_req, "object": inv_req, "type": "request", "status": "new", "prepid": self.prepid}
                        for inv_req in injected_requests if inv_req not in approved_requests]
                    if objects_to_invalidate:
                        self.logger.inject(
                            "Some of the workflows had to be invalidated: {0}".format(objects_to_invalidate),
                            handler=self.prepid)
                        invalidation = database('invalidation')
                        saved = invalidation.save_all(objects_to_invalidate)
                        if not saved:
                            self.injection_error('Could not save the invalidations {0}'.format(objects_to_invalidate),
                                                 req)

                    added_requests = [{'name': app_req, 'content': {'pdmv_prep_id': self.prepid}} for app_req in
                                      approved_requests]
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
                            'There was a problem with registering request in the batch {0}'.format(batch_name), req)
                        return False

                    #and in the end update request in database
                    req.update_history({'action': 'inject', 'step' : batch_name})
                    req.set_status(with_notification=True)
                    saved = self.request_db.update(req.json())
                    if not saved:
                        self.injection_error('Could not update request {0} in database'.format(self.prepid), req)
                        return False

                    for added_req in added_requests:
                        self.logger.inject('Request {0} sent to {1}'.format(added_req['name'], batch_name),
                                           handler=self.prepid)
                    return True
                finally:
                    semaphore_events.decrement(batch_name)

            finally:
                self.lock.release()
                executor.close_executor()

        except Exception as e:
            self.injection_error(
                'Error with injecting the {0} request:\n{1}'.format(self.prepid, traceback.format_exc()), req)


class RequestInjector(Handler):
    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.lock = kwargs["lock"]
        self.prepid = kwargs["prepid"]
        self.uploader = ConfigMakerAndUploader(**kwargs)
        self.submitter = RequestSubmitter(**kwargs)

    def internal_run(self):
        self.logger.inject('## Logger instance retrieved', level='info', handler=self.prepid)
        with locker.lock('{0}-wait-for-approval'.format(self.prepid)):
            if not self.lock.acquire(blocking=False):
                return {"prepid": self.prepid, "results": False,
                        "message": "The request with name {0} is being handled already".format(self.prepid)}
            try:
                if not self.uploader.internal_run():
                    return {"prepid": self.prepid, "results": False,
                            "message": "Problem with uploading the configuration for request {0}".format(self.prepid)}
                self.submitter.internal_run()
            finally:
                self.lock.release()

class ChainRequestInjector(Handler):
    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.lock = kwargs["lock"]
        self.prepid = kwargs["prepid"] 
        self.check_approval = kwargs["check_approval"] if "check_approval" in kwargs else True


    def make_command(self,mcm_r=None):
        l_type = locator()
        cmd='cd %s \n' % ( l_type.workLocation())
        if mcm_r:
            cmd+=mcm_r.make_release()
        cmd+='export X509_USER_PROXY=/afs/cern.ch/user/p/pdmvserv/private/$HOST/voms_proxy.cert\n'
        cmd+='export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n'
        there=''
        if l_type.isDev():
            there='--wmtest --wmtesturl cmsweb-testbed.cern.ch'
        cmd+='wmcontrol.py --url-dict %s/public/restapi/chained_requests/get_dict/%s %s \n'%(l_type.baseurl(), self.prepid, there)
        return cmd

    def internal_run(self):
        if not self.lock.acquire(blocking=False):
            return False
        try:
            crdb = database('chained_requests')
            rdb = database('requests')
            if not crdb.document_exists( self.prepid ):
                ## it's a request actually, pick up all chains containing it
                mcm_r = rdb.get( self.prepid )
                #mcm_crs = crdb.query(query="root_request==%s"% self.prepid) ## not only when its the root of
                mcm_crs = crdb.query(query="contains==%s"% self.prepid)
                task_name = 'task_'+self.prepid
                batch_type = 'Task_'+mcm_r['member_of_campaign']
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
                for rn in chain:
                    mcm_rs.append( request( rdb.get( rn )))
                
                    if self.check_approval and mcm_rs[-1].get_attribute('approval')!='submit':
                        self.logger.error('requests %s in in "%s"/"%s" status/approval, requires "approved"/"submit"'%(
                                rn,
                                mcm_rs[-1].get_attribute('status'),
                                mcm_rs[-1].get_attribute('approval'),
                                ))
                        return False
                    if mcm_rs[-1].get_attribute('status') != 'approved':
                        ## change the return format to percolate the error message
                        self.logger.error('requests %s in in "%s"/"%s" status/approval, requires "approved"/"submit"'%(
                                rn,
                                mcm_rs[-1].get_attribute('status'),
                                mcm_rs[-1].get_attribute('approval'),
                                ))
                        return False
                    uploader = ConfigMakerAndUploader(prepid=rn, lock = locker.lock(rn))
                    uploader.run()
            
            mcm_r = mcm_rs[-1]
            batch_name = BatchPrepId().next_batch_id( batch_type , create_batch=True)
            semaphore_events.increment(batch_name)

            self.logger.error('found batch %s'% batch_name)
            with ssh_executor(server = 'cms-pdmv-op.cern.ch') as ssh:
                cmd = self.make_command(mcm_r)
                self.logger.error('prepared command %s'%cmd)
                ## modify here to have the command to be executed
                _, stdout, stderr = ssh.execute(cmd)
                output = stdout.read()
                error = stderr.read()
                self.logger.log(output)
                self.logger.log(error)

                injected_requests = [l.split()[-1] for l in output.split('\n') if
                                     l.startswith('Injected workflow:')]
                approved_requests = [l.split()[-1] for l in output.split('\n') if
                                     l.startswith('Approved workflow:')]

                if not injected_requests:
                    self.logger.error("no request was injected ")
                    return False

                if injected_requests and not approved_requests:
                    self.logger.error("Request %s was injected but could not be approved" % ( injected_requests ))
                    return False
                    #return dumps({"results" : False, "message" : "Request %s was injected but could not be approved" % ( injected_requests )})

                objects_to_invalidate = [
                    {"_id": inv_req, "object": inv_req, "type": "request", "status": "new", "prepid": self.prepid}
                    for inv_req in injected_requests if inv_req not in approved_requests]
                if objects_to_invalidate:
                    self.logger.error("Some requests %s need to be invalidated" % objects_to_invalidate)
                    return False

                
                # what gets printed into the batch object
                added_requests = []
                for mcm_r in mcm_rs:
                    added = [{'name': app_req, 'content': {'pdmv_prep_id': mcm_r.get_attribute('prepid')}} for app_req in approved_requests]
                    added_requests.extend( added )

                ##edit the batch object
                with locker.lock(batch_name):
                    bdb = database('batches') 
                    bat = batch(bdb.get(batch_name))      
                    bat.add_requests(added_requests)
                    bat.update_history({'action': 'updated', 'step': task_name })
                    bat.reload()
                    ## must be wrong for mcm_r in mcm_rs:
                    ## must be wrong   mcm_r.set_attribute('reqmgr_name',  added_requests) ## this must be a mistake !!!

                mcm_rs=[]
                ## reload the content of all requests as they might have changed already
                for cr in mcm_crs:
                    mcm_cr = chained_request(cr)
                    chain = mcm_cr.get_attribute('chain')[mcm_cr.get_attribute('step'):]
                    for rn in chain:
                        mcm_rs.append( request( rdb.get( rn )))
                ## edit each request with the request name and toggle status
                for mcm_r in mcm_rs:
                    added = [{'name': app_req, 'content': {'pdmv_prep_id': task_name }} for app_req in approved_requests]
                    mcm_r.set_attribute('reqmgr_name', added )
                    mcm_r.update_history({'action': 'inject','step' : batch_name})
                    if not self.check_approval:
                        mcm_r.set_attribute('approval', 'submit') 
                    mcm_r.set_status(with_notification=False)
                    mcm_r.reload()

                #now modify the chain request to move it all along
                mcm_cr.update_history({'action' : 'inject','step': batch_name})
                mcm_cr.set_attribute('step', len(mcm_rs)-1)
                mcm_cr.set_attribute('status','processing')
                mcm_cr.set_attribute('last_status', mcm_rs[-1].get_attribute('status'))

                message=""
                for mcm_r in mcm_rs:
                    message+=mcm_r.textified()
                    message+="\n\n"
                mcm_cr.notify('Injection succeeded for %s'% task_name,
                              message)

                mcm_cr.reload()
                
                return True
        finally:
            self.lock.release()
