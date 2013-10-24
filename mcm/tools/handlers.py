import os
from threading import Thread, Lock
import time
import traceback
from tools.batch_control import batch_control
from tools.installer import installer
from tools.locker import semaphore_thread_number
from tools.logger import logger as logfactory
from tools.request_to_wma import request_to_wmcontrol
from tools.ssh_executor import ssh_executor
from tools.locator import locator
from tools.locker import locker, semaphore_events
from couchdb_layer.mcm_database import database
from json_layer.request import request
from json_layer.batch import batch
from rest_api.BatchPrepId import BatchPrepId


class PoolOfHandlers(Thread):
    """
    Class used for instantiating and taking care of running a number of handlers in parallel. It provides them
    with lock for protection of concurrently-vulnerable parts of program (e.g. database access).
    """

    logger = logfactory('mcm')

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
    logger = logfactory('mcm')
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
        self.config_db = database("configs")
        self.ssh_executor = ssh_executor(server='pdmvserv-test.cern.ch')

    @staticmethod
    def prepare_command(cfgs, directory, req, test_string):
        cmd = req.get_setup_file(directory)
        cmd += 'source /afs/cern.ch/cms/LCG/LCG-2/UI/cms_ui_env.sh ; source /afs/cern.ch/cms/ccs/wm/scripts/Crab/crab.sh\n'
        cmd += 'cat /afs/cern.ch/user/p/pdmvserv/private/PdmVService.txt | voms-proxy-init -voms cms --valid 240:00 -pwstdin --key /afs/cern.ch/user/p/pdmvserv/private/$HOST/userkey.pem --cert /afs/cern.ch/user/p/pdmvserv/private/$HOST/usercert.pem 2> /dev/null\n'
        cmd += 'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh\n'
        cmd += 'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n'
        cmd += "wmupload.py {1} -u pdmvserv -g ppd {0}".format(" ".join(cfgs), test_string)
        return cmd

    def internal_run(self):
        if not self.lock.acquire(blocking=False):
            return False
        try:
            req = request(self.request_db.get(self.prepid))
            additional_config_ids = {}
            cfgs_to_upload = {}
            l_type = locator()
            dev=''
            wmtest=''
            if l_type.isDev():
                wmtest = '--wmtest'
            if req.get_attribute('config_id'): # we already have configuration ids saved in our request
                return True
            for i in range(len(req.get_attribute('sequences'))):
                hash_id = req.configuration_identifier(i)
                if self.config_db.document_exists(hash_id): # cached in db
                    additional_config_ids[i] = self.config_db.get(hash_id)['docid']
                else: # has to be setup and uploaded to config cache
                    cfgs_to_upload[i] = "{0}{1}_{2}_cfg.py".format(req.get_attribute('prepid'), dev, i+1)
            if cfgs_to_upload:
                with installer(self.prepid, care_on_existing=False) as directory_manager:
                    command = self.prepare_command([cfgs_to_upload[i] for i in sorted(cfgs_to_upload)], directory_manager.location(), req, wmtest)
                    _, stdout, stderr = self.ssh_executor.execute(command)
                    if not stdout and not stderr:
                        self.logger.error('SSH error for request {0}. Could not retrieve outputs.'.format(self.prepid))
                        self.logger.inject('SSH error for request {0}. Could not retrieve outputs.'.format(self.prepid), level='error', handler=self.prepid)
                        req.test_failure('SSH error for request {0}. Could not retrieve outputs.'.format(self.prepid), what='Configuration upload')
                        return False
                    output = stdout.read()
                    error = stderr.read()
                    if error and not output: # money on the table that it will break
                        self.logger.error('Error in wmupload: {0}'.format(error))
                        req.test_failure('Error in wmupload: {0}'.format(error), what='Configuration upload')
                        return False
                    cfgs_uploaded = [l for l in output.split("\n") if 'DocID:' in l]

                    if len(cfgs_to_upload) != len(cfgs_uploaded):
                        self.logger.error('Problem with uploading the configurations. To upload: {0}, received doc_ids: {1}\nOutput:\n{2}\nError:\n{3}'.format(cfgs_to_upload, cfgs_uploaded, output, error))
                        self.logger.inject('Problem with uploading the configurations. To upload: {0}, received doc_ids: {1}\nOutput:\n{2}\nError:\n{3}'.format(cfgs_to_upload, cfgs_uploaded, output, error), level='error', handler=self.prepid)
                        req.test_failure('Problem with uploading the configurations. To upload: {0}, received doc_ids: {1}\nOutput:\n{2}\nError:\n{3}'.format(cfgs_to_upload, cfgs_uploaded, output, error), what='Configuration upload')
                        return False

                    for i, line in zip(sorted(cfgs_to_upload), cfgs_uploaded): # filling the config ids for request and config database with uploaded configurations
                        docid = line.split()[-1]
                        additional_config_ids[i] = docid
                        saved = self.config_db.save({"_id": req.configuration_identifier(i),
                                                 "docid": docid,
                                                 "prepid": self.prepid,
                                                 "unique_string": req.unique_string(i)})
                        if not saved:
                             self.logger.inject('Could not save the configuration {0}'.format( req.configuration_identifier(i) ), level='warning', handler=self.prepid)

                    self.logger.inject("Full upload result: {0}".format(output), handler=self.prepid)
            sorted_additional_config_ids = [additional_config_ids[i] for i in additional_config_ids]
            self.logger.inject("New configs for request {0} : {1}".format(self.prepid, sorted_additional_config_ids), handler=self.prepid)
            req.set_attribute('config_id', sorted_additional_config_ids)
            self.request_db.save(req.json())
            return True
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
        location = installer( self.rid, care_on_existing=False, clean_on_exit=True)
        try:
            test_script = location.location()+'validation_run_test.sh'
            with open( test_script ,'w') as there:
                ## one has to wait just a bit, so that the approval change operates, and the get retrieves the latest greatest _rev number
                #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
                time.sleep( 10 )
                mcm_r = request(self.db.get(self.rid))
                #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
                n_for_test = mcm_r.get_n_for_test(target=100.0)
                ## the following does change something on the request object, to be propagated in case of success
                there.write( mcm_r.get_setup_file( location.location() , n_for_test) )
            batch_test = batch_control( self.rid, test_script )
            try:
                success = batch_test.test()
            except:
                batch_test.log_err = traceback.format_exc()
                success = False

            if success:
                self.logger.log("batch_test result is %s" % success)
                try:
                    #suck in run-test if present
                     rt_xml=location.location()+'%s_rt.xml'%( self.rid )
                     if os.path.exists( rt_xml ):
                         mcm_r.update_performance( open(rt_xml).read(), 'perf')
                except:
                    batch_test.log_err = traceback.format_exc()
                    self.logger.error('Failed to get perf reports \n %s'%( batch_test.log_err))
                    success = False

                try:
                    gv_xml=location.location()+'%s_gv.xml'%( self.rid )
                    if os.path.exists( gv_xml ):
                        mcm_r.update_performance( open(gv_xml).read(), 'eff')
                except:
                    batch_test.log_err = traceback.format_exc()
                    self.logger.error('Failed to get gen valid reports \n %s'%( batch_test.log_err ))
                    success = False

            self.logger.error('I came all the way to here and %s (request %s)'%( success, self.rid ))
            if not success:
                ## need to provide all the information back
                the_logs='\t .out \n%s\n\t .err \n%s\n '% ( batch_test.log_out, batch_test.log_err)
                #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
                # reset the content of the request
                mcm_r = request(self.db.get(self.rid))
                mcm_r.test_failure(message=the_logs,what='Validation run test',rewind=True)
                #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
            else:
                #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
                ## change the status with notification
                mcm_current = request(self.db.get(self.rid))
                if mcm_current.json()['_rev']==mcm_r.json()['_rev']:
                    ## it's fine to push it through
                    mcm_r.set_status(with_notification=True)
                    saved = self.db.update( mcm_r.json() )
                    if not saved:
                        mcm_current.test_failure(message='The request could not be saved after the run test procedure',what='Validation run test',rewind=True)
                else:
                    mcm_current.test_failure(message='The request has changed during the run test procedure, preventing from being saved',what='Validation run test',rewind=True)
                #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
        finally:
            #mess = 'We have been taken out of run_safe of runtest_genvalid for %s because \n %s \n During an un-excepted exception. Please contact support.' % (self.rid, traceback.format_exc())
            #self.logger.error( mess )
            #mcm_r = request(self.db.get(self.rid))
            #mcm_r.test_failure(message=mess,what='Validation run test',rewind=True)
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
        self.ssh_executor = ssh_executor(server='pdmvserv-test.cern.ch')

    @staticmethod
    def prepare_command(req, batch_name):
        batch_number = batch_name.split("-")[-1]
        cmd = request_to_wmcontrol().get_command(req, batch_number, to_execute=True)
        return cmd

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
            self.injection_error("The request is in approval {0}, while submit is required".format(req.get_attribute('approval')), req)
            return False, None
        return True, req


    def internal_run(self):
        try:
            if not self.lock.acquire(blocking=False):
                return False
            try:
                okay, req = self.check_request()
                if not okay: return False
                batch_name = BatchPrepId().generate_prepid(req.json())
                semaphore_events.increment(batch_name) # so it's not possible to announce while still injecting
                try:
                    cmd = self.prepare_command(req, batch_name)
                    self.logger.inject("Command being used for injecting request {0}: {1}".format(self.prepid, cmd), handler=self.prepid)
                    _, stdout, stderr = self.ssh_executor.execute(cmd)
                    if not stdout and not stderr:
                            self.injection_error('ssh error for request {0} injection'.format(self.prepid), req)
                            return False
                    output = stdout.read()
                    error = stderr.read()
                    if error and not output: # money on the table that it will break as well?
                        self.injection_error('Error in wmcontrol: {0}'.format(error), req)
                        return False
                    injected_requests = [l.split()[-1] for l in output.split('\n') if l.startswith('Injected workflow:')]
                    approved_requests = [l.split()[-1] for l in output.split('\n') if l.startswith('Approved workflow:')]
                    if not approved_requests:
                        self.injection_error('Injection has succeeded but no request manager names were registered. Check with administrators. \nOutput: \n{0}\n\nError: \n{1}'.format(output, error), req)
                        return False
                    objects_to_invalidate = [{"_id": inv_req, "object": inv_req, "type": "request", "status": "new" , "prepid": self.prepid}
                                             for inv_req in injected_requests if inv_req not in approved_requests]
                    if objects_to_invalidate:
                        self.logger.inject("Some of the workflows had to be invalidated: {0}".format(objects_to_invalidate), handler=self.prepid)
                        invalidation = database('invalidation')
                        saved = invalidation.save_all(objects_to_invalidate)
                        if not saved:
                            self.injection_error('Could not save the invalidations {0}'.format(objects_to_invalidate), req)

                    added_requests = [{'name': app_req, 'content': {'pdmv_prep_id': self.prepid}} for app_req in approved_requests]
                    requests = req.get_attribute('reqmgr_name')
                    requests.extend(added_requests)
                    req.set_attribute('reqmgr_name', requests)

                    #inject to batch
                    with locker.lock(batch_name):
                        bdb = database('batches')
                        bat = batch(bdb.get(batch_name))
                        bat.add_requests(added_requests)
                        note = []

                        if req.get_attribute('extension'):
                            note.append(' is an extension ({0})'.format( req.get_attribute('extension')))
                        if len(req.get_attribute('reqmgr_name')) > 1 or req.get_attribute(
                                'version') != 0: #>1 because you just added that submission request a few lines above
                            note.append(' is a resubmission (v{0})'.format(req.get_attribute('version')))
                        if note:
                            bat.add_notes('\n{0}: {1}'.format(self.prepid, ','.join(note)))
                        bat.update_history({'action': 'updated', 'step': self.prepid})
                        saved = bdb.update(bat.json())
                    if not saved:
                        self.injection_error('There was a problem with registering request in the batch {0}'.format(batch_name), req)
                        return False

                    #and in the end update request in database
                    req.update_history({'action': 'inject'})
                    req.set_status(with_notification=True)
                    saved = self.request_db.update(req.json())
                    if not saved:
                        self.injection_error('Could not update request {0} in database'.format(self.prepid), req)
                        return False

                    for added_req in added_requests:
                        self.logger.inject('Request {0} sent to {1}'.format(added_req['name'], batch_name), handler=self.prepid)
                    return True
                finally:
                    semaphore_events.decrement(batch_name)
            finally:
                self.lock.release()
        except Exception as e:
            self.injection_error('Error with injecting the {0} request:\n{1}'.format(self.prepid, traceback.format_exc()), req)
        finally:
            self.ssh_executor.close_executor()


class RequestInjector(Handler):

    def __init__(self, **kwargs):
        Handler.__init__(self, **kwargs)
        self.lock = kwargs["lock"]
        self.prepid = kwargs["prepid"]
        self.uploader = ConfigMakerAndUploader(**kwargs)
        self.submitter = RequestSubmitter(**kwargs)

    def internal_run(self):
        self.logger.inject('## Logger instance retrieved', level='info', handler=self.prepid)
        with locker.lock('{0}-wait-for-approval'.format( self.prepid ) ):
            if not self.lock.acquire(blocking=False):
                return {"prepid": self.prepid, "results": False,
                        "message": "The request with name {0} is being handled already" .format(self.prepid)}
            try:
                if not self.uploader.internal_run():
                    return  {"prepid": self.prepid, "results": False,
                             "message": "Problem with uploading the configuration for request {0}" .format(self.prepid)}
                self.submitter.internal_run()
            finally:
                self.lock.release()
