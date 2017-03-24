import os
import sys
import shutil
import time
import traceback
import logging
from json import loads
from json import dumps

from couchdb_layer.mcm_database import database
from tools.installer import installer
from tools.ssh_executor import ssh_executor
from tools.settings import settings
from json_layer.request import request
from json_layer.chained_request import chained_request
from tools.locator import locator
from itertools import izip


class ValidationHandler:
    '''
    A class that handles everything for chained requests and requests validations, this includes constructing the command, creating related files and directories,
    monitoring the bjobs and getting the results to update the performance.
    '''

    JOBS_FILE_NAME = 'validationJobs' + os.environ['HOSTNAME'] + '.txt'
    LOG_FILE_NAME = 'validationJobs' + os.environ['HOSTNAME'] + '.log'
    TEST_FILE_NAME = 'validation_run_test.sh'
    QUEUE_8NH = '8nh'
    QUEUE_1ND = '1nd' # fall back to the one day queue at worse
    JOB_STATUS = 'status'
    JOB_PERCENTAGE = 'percentage'
    JOB_ID = 'job_id'
    DOC_REV = '_rev'
    DOC_VALIDATION = 'validation'
    request_db = database('requests')
    chained_request_db = database('chained_requests')
    CHAIN_REQUESTS = 'requests'
    new_jobs = [] #could be a request id or chain id
    submmited_jobs = {} #could be a request id or chain id
    submmited_prepids_set = set()
    test_directory_path = ''
    data_script_path = ''

    def __init__(self):
        self.setup_directories()
        self.setup_logger()
        self.get_submmited_prepids()
        self.batch_retry_timeout = settings().get_value('batch_retry_timeout')
        self.check_term_runlimit = settings().get_value('check_term_runlimit')
        try:
            self.ssh_exec = ssh_executor()
        except Exception as e:
            self.ssh_exec = None
            self.logger.error(str(e) + 'traceback %s ' % traceback.format_exc())
            return
        if locator().isDev():
            self.group = '/dev'
        else:
            self.group = '/prod'

    def setup_directories(self):
        locator = installer('validation/tests', care_on_existing=False)
        self.test_directory_path = locator.location()
        self.data_script_path = self.test_directory_path[:-6] #remove tests/

    def setup_logger(self):
        self.logger = logging.getLogger('validationJobs')
        error_formatter = logging.Formatter(
            fmt='[%(asctime)s][%(levelname)s]%(message)s',
            datefmt='%d/%b/%Y:%H:%M:%S'
        )
        # The size of the log file increse very fast, should be ok with the records in jenkins and emails, if not, uncomment this
        #file_handler = logging.FileHandler(self.data_script_path + self.LOG_FILE_NAME, 'a')
        #file_handler.setLevel(logging.DEBUG)
        #file_handler.setFormatter(error_formatter)
        #self.logger.addHandler(file_handler)
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(error_formatter)
        self.logger.addHandler(stream_handler)
        self.logger.setLevel(logging.DEBUG)

    def get_new_chain_prepids(self):
        __query = self.chained_request_db.construct_lucene_query({'validate<int>': '1'})
        query_result = self.chained_request_db.full_text_search("search", __query, page=0, limit=10, include_fields='prepid')
        return [record['prepid'] for record in query_result]

    def get_new_request_prepids(self):
        __query = self.request_db.construct_lucene_query(
            {
                'status': 'new',
                'approval': 'validation'
            }
        )
        query_result = self.request_db.full_text_search("search", __query, page=-1, include_fields='prepid')
        return [record['prepid'] for record in query_result]

    def get_submmited_prepids(self):
        full_path = self.data_script_path + self.JOBS_FILE_NAME
        if not os.path.exists(full_path):
            self.submmited_jobs = {}
            return
        with open(full_path, 'r') as file:
            self.submmited_jobs = loads(file.read())

    def save_jobs(self):
        full_path = self.data_script_path + self.JOBS_FILE_NAME
        file = open(full_path, 'w+')
        file.write(dumps(self.submmited_jobs, indent=4))
        file.close()

    def get_prepids_to_submit(self):
        submmited_prepids_list = []
        for prepid in self.submmited_jobs.iterkeys():
            if 'chain' in prepid:
                submmited_prepids_list += self.submmited_jobs[prepid][self.CHAIN_REQUESTS].iterkeys()
            submmited_prepids_list.append(prepid)
        new_prepids_set = set(self.new_jobs)
        self.submmited_prepids_set = set(submmited_prepids_list)
        return list(new_prepids_set - self.submmited_prepids_set)

    def read_file_from_afs(self, path, trials_time_out=5):
        cmd = 'cat %s' % path
        stdin, stdout, stderr = self.ssh_exec.execute(cmd)
        out = ""
        err = ""
        if stdout:
            out=stdout.read()
            err=stderr.read()
        trials = 0
        # wait for afs to synchronize the output file
        while ( (not stdin and not stdout and not stderr) or err) and trials < trials_time_out:
            time.sleep(self.batch_retry_timeout)
            trials += 1
            self.logger.info('Trying to get %s for the %s time' % (path, trials+1))
            stdin, stdout, stderr = self.ssh_exec.execute(cmd)
            if stdout:
                out=stdout.read()
                err=stderr.read()

        if trials >= trials_time_out:
            self.logger.error('%s could not be retrieved after %s tries in interval of %s s' % (
                    path, trials, self.batch_retry_timeout))
            return '',''

        return out, err

    def build_submission_command(self, prepid, run_test_path, timeout, memory):
        timeout = int(timeout / 60.)
        queue = self.QUEUE_1ND if (timeout / 3600. ) > 8. else self.QUEUE_8NH
        memory = str(memory*1000) #we convert from MB to KB for batch
        cmd = 'bsub -J ' + prepid
        cmd += ' -g ' + self.group
        cmd += ' -q ' + queue
        cmd += ' -cwd ' + run_test_path
        cmd += ' -W %s'%  timeout
        run_test_path += '/' + self.TEST_FILE_NAME
        cmd += ' -eo ' + run_test_path + '.err'
        cmd += ' -oo ' + run_test_path + '.out'
        cmd += ' -M ' + memory
        cmd += ' bash ' + run_test_path
        return cmd

    def check_ssh_outputs(self, stdin, stdout, stderr, fail_message):
        if not stdin and not stdout and not stderr:
            self.logger.error(fail_message)
            return False
        return True

    def create_test_file(self, to_write, run_test_path):
        location = installer(run_test_path, care_on_existing=False, is_abs_path=True)
        test_file_path = run_test_path + '/' + self.TEST_FILE_NAME
        try:
            with open(test_file_path, 'w') as there:
                there.write(to_write)
            return True
        except Exception as e:
            self.logger.error('There was a problem while creating the file: %s message: %s \ntraceback %s' % (run_test_path, str(e), traceback.format_exc()))
            return False


    def submit_request(self, prepid, run_test_path):
        mcm_request = request(self.request_db.get(prepid))
        # check if the request should be validated as part of a chain
        for chain_prepid in mcm_request.get_attribute('member_of_chain'):
            mcm_chain = chained_request(self.chained_request_db.get(chain_prepid))
            if mcm_chain.get_attribute('validate') and prepid in mcm_chain.get_attribute('chain')[mcm_chain.get_attribute('step'):]:
                return {}
        aux_validation = mcm_request.get_attribute(self.DOC_VALIDATION)
        to_write = mcm_request.get_setup_file(run_test_path, run=True, do_valid=True)
        if not self.create_test_file(to_write, run_test_path):
            mcm_request.set_attribute(self.DOC_VALIDATION, aux_validation)
            mcm_request.test_failure(
                message='There was a problem while creating the file for prepid: %s' % (mcm_request.get_attribute('prepid')),
                what='Validation run test',
                rewind=True
            )
            return {}
        timeout = mcm_request.get_timeout()
        memory = mcm_request.get_attribute("memory")
        job_info = self.execute_command_submission(prepid, run_test_path, timeout, memory)
        if 'error' in job_info:
            mcm_request.test_failure(message=job_info['error'], what='Validation run test', rewind=True)
            return {}
        job_info[self.DOC_REV] = mcm_request.json()[self.DOC_REV]
        job_info[self.DOC_VALIDATION] = mcm_request.get_attribute(self.DOC_VALIDATION) #this field change when calling request.get_setup_file, to be propagated in case of success
        return job_info

    def execute_command_submission(self, prepid, run_test_path, timeout, memory):
        cmd = self.build_submission_command(prepid, run_test_path, timeout, memory)
        self.logger.info('Executing submission command: \n%s' % cmd)
        stdin,  stdout,  stderr = self.ssh_exec.execute(cmd)
        message_ssh = "There was a problem with SSH remote execution of command:\n{0}!".format(cmd)
        if not self.check_ssh_outputs(stdin, stdout, stderr,
                message_ssh):
            return {'error': message_ssh}
        out = stdout.read()
        errors = stderr.read()
        self.logger.info(out)
        if 'Job not submitted' in errors:
            message = 'Job submission failed for request: %s \nerror output:\n %s' % (prepid, errors)
            self.logger.error(message)
            return {'error': message}
        job_id = out.split()[1]
        return {self.JOB_ID: job_id[1:-1]} #remove < >

    def submit_chain(self, prepid, run_test_path):
        mcm_chained_request = chained_request(self.chained_request_db.get(prepid))
        except_requests = []
        reset = False
        #If a request of a chain was singly submmited to validation and then somebody reseted it, we will find it here
        for request_prepid in mcm_chained_request.get_attribute('chain')[mcm_chained_request.get_attribute('step'):]:
            if request_prepid in self.submmited_prepids_set:
                except_requests.append(request_prepid)
                reset = True
        if reset:
            message = "Requests %s of the chain %s are already in validation" % (except_requests, prepid)
            self.logger.error(message)
            mcm_chained_request.reset_requests(message, except_requests=except_requests)
            return {}
        to_write = mcm_chained_request.get_setup(directory=run_test_path, run=True, validation= True)
        if not self.create_test_file(to_write, run_test_path):
            mcm_chained_request.reset_requests('There was a problem while creating the file for prepid: %s' % (mcm_chained_request.get_attribute('prepid')))
            return {}
        requests_in_chain = {}
        for request_prepid in mcm_chained_request.get_attribute('chain')[mcm_chained_request.get_attribute('step'):]:
            mcm_request = request(self.request_db.get(request_prepid))
            if not mcm_request.is_root and 'validation' not in mcm_request._json_base__status: #only root or possible root requests
                break
            status = mcm_request.get_attribute('status')
            approval = mcm_request.get_attribute('approval')
            if status != 'new' or approval != 'validation':
                message = "The request %s of chain %s is in status: %s approval: %s" % (request_prepid, prepid, status, approval)
                self.logger.error(message)
                mcm_chained_request.reset_requests(message)
                return {}
            requests_in_chain[request_prepid] = mcm_request.json()[self.DOC_REV]
        if not len(requests_in_chain):
            message = 'No requests to be validated in chain: %s' % prepid
            self.logger.info(message)
            mcm_chained_request.reset_requests(message)
            return {}
        timeout, memory = mcm_chained_request.get_timeout_and_memory()
        job_info = self.execute_command_submission(prepid, run_test_path, timeout, memory)
        if 'error' in job_info:
            mcm_chained_request.reset_requests(job_info['error'])
            return {}
        job_info[self.CHAIN_REQUESTS] = requests_in_chain
        return job_info

    def submit_jobs(self, prepids_to_submit):
        for prepid in prepids_to_submit:
            test_path = self.test_directory_path + prepid
            try:
                if 'chain' in prepid:
                    result_dict = self.submit_chain(prepid, test_path)
                    if len(result_dict):
                        self.submmited_prepids_set.update(result_dict[self.CHAIN_REQUESTS].iterkeys())
                else:
                    result_dict = self.submit_request(prepid, test_path)
                if len(result_dict):
                    self.submmited_jobs[prepid] = result_dict
            except Exception as e:
                #Catch any unexpected exepction and keep going
                message = "Unexpected exception while trying to submit %s message: %s\ntraceback %s" % (prepid, str(e), traceback.format_exc())
                self.report_error(prepid, message)

    def get_jobs_status(self):
        cmd = 'bjobs -noheader -a -g %s -WP' % (self.group)
        stdin, stdout, stderr = self.ssh_exec.execute(cmd)
        if not self.check_ssh_outputs(stdin, stdout, stderr,
                "Problem with SSH execution of command: %s" % (cmd)):
            return {}
        jobs_dict = {}
        for line in stdout.read().split('\n'):
            columns = line.split()
            num_columns = len(columns)
            if len(columns) < 9:
                continue
            jobs_dict[columns[0]] = {
                self.JOB_STATUS: columns[2],
                self.JOB_PERCENTAGE: '-' if num_columns == 10 else columns[10]
            }
        return jobs_dict

    def report_error(self, prepid, message):
        self.logger.error(message)
        if 'chain' in  prepid:
            mcm_chained_request = chained_request(self.chained_request_db.get(prepid))
            mcm_chained_request.reset_requests(message)
        else:
            mcm_request = request(self.request_db.get(prepid))
            mcm_request.test_failure(
                    message=message,
                    what='Validation run test',
                    rewind=True
            )

    def monitor_submmited_jobs(self):
        jobs_dict = self.get_jobs_status()
        if not len(jobs_dict):
            return
        remove_jobs = []
        for prepid, doc_info in self.submmited_jobs.iteritems():
            try:
                job_id = doc_info[self.JOB_ID]
                if job_id not in jobs_dict:
                    self.report_error(prepid, 'Unable to find information about job: %s' % job_id)
                    remove_jobs.append(prepid)
                    continue
                job_info = jobs_dict[job_id]
                if job_info[self.JOB_STATUS] == 'RUN':
                    self.logger.info('Job %s for prepid %s is running, %%Complete: %s' % (job_id, prepid, job_info[self.JOB_PERCENTAGE]))
                elif job_info[self.JOB_STATUS] in ['DONE', 'EXIT'] :
                    self.logger.info('Job %s for prepid %s is DONE or EXIT, processing it.....' % (job_id, prepid))
                    self.process_finished_job(prepid, doc_info)
                    remove_jobs.append(prepid)
                else:
                    self.logger.info('The status for job %s (prepid: %s) is %s' % (job_id, prepid, job_info[self.JOB_STATUS]))
            except Exception as e:
                #Catch any unexpected exception and keep going
                message = "Unexpected exception while monitoring job for prepid %s message: %s \ntraceback: %s" % (prepid, str(e), traceback.format_exc())
                self.report_error(prepid, message)
                remove_jobs.append(prepid)
        for prepid in remove_jobs:
            self.submmited_jobs.pop(prepid)
            self.removeDirectory(self.test_directory_path + prepid)

    def process_finished_job(self, prepid, doc_info):
        out_path = self.test_directory_path + prepid + '/' + self.TEST_FILE_NAME + '.out'
        error_path = self.test_directory_path + prepid + '/' + self.TEST_FILE_NAME + '.err'
        job_out, job_error_out = self.read_file_from_afs(out_path)
        was_exited = False
        for line in job_out.split('\n'):
            if 'Successfully completed.' in line:
                if 'chain' in prepid:
                    self.process_finished_chain_success(prepid, doc_info)
                else:
                    self.process_finished_request_success(prepid, doc_info, job_out)
                return
            elif 'Exited with' in line:
                was_exited = True
                break
        error_out, _ = self.read_file_from_afs(error_path, trials_time_out=1)
        if 'chain' in prepid:
            self.process_finished_chain_failed(prepid, job_out, job_error_out, error_out, was_exited, out_path)
        else:
            self.process_finished_request_failed(prepid, job_out, error_out, was_exited, job_error_out, out_path)

    def process_finished_chain_failed(self, prepid, job_out, job_error_out, error_out, was_exited, out_path):
        mcm_chained_request = chained_request(self.chained_request_db.get(prepid))
        if not was_exited:
            message = "File %s does not look properly formatted or does not exist. \n %s \n %s \n Error out: %s" % (
                out_path, job_out, job_error_out, error_out)
        else:
            message = "Job validation failed for chain %s \nJob out: \n%s \n Error out: \n%s" % (prepid, job_out, error_out)
        self.logger.error(message)
        mcm_chained_request.reset_requests(message)

    def process_finished_chain_success(self, prepid, doc_info):
        mcm_chained_request = chained_request(self.chained_request_db.get(prepid))
        requests_in_chain = []
        for request_prepid, doc_rev in doc_info[self.CHAIN_REQUESTS].iteritems():
            mcm_request = request(self.request_db.get(request_prepid))
            success = True
            message = ''
            if doc_rev != mcm_request.json()[self.DOC_REV]:
                message = 'The request %s in the chain %s has changed during the run test procedure, preventing from being saved' % (request_prepid, prepid)
                success = False
            path = self.test_directory_path + prepid + '/'
            if success:
                success, error = mcm_request.pickup_all_performance(path)
                if not success:
                    message = 'Error while picking up all the performance for request %s of chain %s: \n %s' % (request_prepid, prepid, error)
            if not success:
                self.logger.error(message)
                mcm_chained_request.reset_requests(message, notify_one=request_prepid)
                return
            requests_in_chain.append(mcm_request)
        for mcm_request in requests_in_chain:
            mcm_request.set_status(with_notification=True)
            if not self.request_db.update(mcm_request.json()):
                request_prepid = mcm_request.get_attribute('prepid')
                message = "The request %s of chain %s could not be saved after the runtest procedure" % (request_prepid, prepid)
                self.logger.error(message)
                #reset it and keep saving requests
                mcm_request.test_failure(
                        message=message,
                        what='Chain validation run test',
                        rewind=True
                )
        mcm_chained_request.reload(save_current=False) # setting new requests status change the chain object
        mcm_chained_request.set_attribute('validate', 0)
        if not self.chained_request_db.update(mcm_chained_request.json()):
            message = 'Problem saving changes in chain %s, set validate = False ASAP!' % prepid
            self.logger.error(message)
            mcm_chained_request.notify('Chained validation run test', message)
            return
        self.logger.info('Validation job for prepid %s SUCCESSFUL!!!' % prepid)

    def removeDirectory(self, path):
        try:
            self.logger.info('Deleting the directory: %s' % path)
            shutil.rmtree(path)
        except Exception as ex:
            self.logger.error('Could not delete directory "%s". Reason: %s \ntraceback: %s' % (path, ex, traceback.format_exc()))

    def process_finished_request_success(self, prepid, doc_info, job_out):
        mcm_request = request(self.request_db.get(prepid))
        doc_revision = doc_info[self.DOC_REV]
        doc_validation = doc_info[self.DOC_VALIDATION]
        if doc_revision != mcm_request.json()[self.DOC_REV]:
            message = 'The request %s has changed during the run test procedure, preventing from being saved' % (prepid)
            self.logger.error(message)
            mcm_request.test_failure(
                        message=message,
                        what='Validation run test',
                        rewind=True
            )
            return
        path = self.test_directory_path + prepid + '/'
        (is_success, error) = mcm_request.pickup_all_performance(path)
        if not is_success:
            self.logger.error('Error while picking up all the performance: \n %s' % error)
            self.process_finished_request_failed(prepid, job_out, error)
            return
        mcm_request.set_status(with_notification=True)
        aux_validation = mcm_request.get_attribute(self.DOC_VALIDATION)
        mcm_request.set_attribute(self.DOC_VALIDATION, doc_validation)
        saved = self.request_db.update(mcm_request.json())
        if not saved:
            mcm_request.set_attribute(self.DOC_VALIDATION, aux_validation)
            mcm_current.test_failure(
                message='The request could not be saved after the run test procedure',
                what='Validation run test',
                rewind=True
            )
            return
        self.logger.info('Validation job for prepid %s SUCCESSFUL!!!' % prepid)

    def process_finished_request_failed(self, prepid, job_out, error_out, was_exited=True, job_error_out='', out_path=''):
        mcm_request = request(self.request_db.get(prepid))
        # need to provide all the information back
        if not was_exited:
            no_success_message = "We could get %s, but it does not look properly formatted. \n %s \n %s \n Error out: %s" % (
                out_path, job_out, job_error_out, error_out)
        elif self.check_term_runlimit and "TERM_RUNLIMIT" in job_out:
            no_success_message = "LSF job was terminated after reaching run time limit.\n\n"
            no_success_message += "Average CPU time per event specified for request was {0} seconds. \n\n".format(
                mcm_request.get_attribute("time_event")
            )
            additional_message = "Time report not found in LSF job."
            split_log = error_out.split('\n')
            for l_id, line in izip(reversed(xrange(len(split_log))), reversed(split_log)):
                if "TimeReport>" in line:
                    additional_message = "\n".join(split_log[l_id:l_id + 12])
            no_success_message += additional_message
        else:
            no_success_message = '\t %s.out \n%s\n\t %s.err \n%s\n ' % (self.TEST_FILE_NAME,
                    job_out, self.TEST_FILE_NAME, error_out)
        self.logger.error(no_success_message)
        mcm_request.test_failure(
            message=no_success_message,
            what='Validation run test',
            rewind=True
        )

    def main(self):
        if validation_handler.ssh_exec is None:
            sys.exit(-1)
        validation_handler.monitor_submmited_jobs()
        self.new_jobs =  self.get_new_request_prepids() + self.get_new_chain_prepids()
        prepids_to_submit = validation_handler.get_prepids_to_submit()
        validation_handler.submit_jobs(prepids_to_submit)
        validation_handler.save_jobs()

if __name__ == "__main__":
    validation_handler = ValidationHandler()
    validation_handler.main()