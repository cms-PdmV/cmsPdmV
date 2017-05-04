import os
import sys
import shutil
import time
import traceback
import logging
import math

from json import loads
from json import dumps

from couchdb_layer.mcm_database import database
from tools.installer import installer
from tools.ssh_executor import ssh_executor
from tools.settings import settings
from tools.communicator import communicator
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
    TEST_FILE_NAME = '%s_run_test.sh'
    CONDOR_FILE_NAME = 'cluster.sub'
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
        logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s][%(levelname)s]%(message)s',
                    datefmt='%d/%b/%Y:%H:%M:%S'
        )
        self.logger = logging.getLogger('validationJobs')

    def get_new_chain_prepids(self):
        __query = self.chained_request_db.construct_lucene_query({'validate<int>': '1'})
        query_result = self.chained_request_db.full_text_search("search", __query, page=-1, include_fields='prepid')
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

    def read_file_from_afs(self, path, trials_time_out=3):
        cmd = 'cat %s' % path
        stdin, stdout, stderr = self.ssh_exec.execute(cmd)
        out = ""
        err = ""
        if stdout:
            out=stdout.read()
            err=stderr.read()
        trials = 1
        # wait for afs to synchronize the output file
        while ( (not stdin and not stdout and not stderr) or err) and trials < trials_time_out:
            time.sleep(self.batch_retry_timeout)
            trials += 1
            self.logger.info('Trying to get %s for the %s time' % (path, trials))
            stdin, stdout, stderr = self.ssh_exec.execute(cmd)
            if stdout:
                out=stdout.read()
                err=stderr.read()

        if trials >= trials_time_out:
            self.logger.error('%s could not be retrieved after %s tries in interval of %s s' % (
                    path, trials, self.batch_retry_timeout))

        return out, err

    def check_ssh_outputs(self, stdin, stdout, stderr, fail_message):
        if not stdin and not stdout and not stderr:
            self.logger.error(fail_message)
            return False
        return True

    def create_test_file(self, to_write, run_test_path, file_name):
        location = installer(run_test_path, care_on_existing=False, is_abs_path=True)
        test_file_path = run_test_path + '/' + file_name
        try:
            with open(test_file_path, 'w') as there:
                there.write(to_write)
            return True
        except Exception as e:
            self.logger.error('There was a problem while creating the file: %s message: %s \ntraceback %s' % (test_file_path, str(e), traceback.format_exc()))
            return False

    def create_htcondor_config_file(self, run_test_path, prepid, timeout, memory, threads):
        file_name = self.TEST_FILE_NAME % prepid
        to_write =  'universe              = vanilla\n'
        to_write += 'environment           = HOME=/afs/cern.ch/user/p/pdmvserv\n'
        to_write += 'executable            = %s\n' % file_name
        to_write += 'output                = %s.out\n' % file_name
        to_write += 'error                 = %s.err\n' % file_name
        to_write += 'log                   = %s.log\n' % file_name
        to_write += 'transfer_output_files = %s_rt.xml\n' % prepid
        to_write += 'periodic_remove       = (JobStatus == 5 && HoldReasonCode == 13)\n' #remove the job if .xml transfer failed (expected reason: it wasn't generated)
        to_write += '+MaxRuntime           = %s\n' % timeout
        to_write += 'RequestCpus           = %s\n' % max(threads, int(math.ceil(memory/2000.0))) # htcondor gives 2GB per core, if you want more memory you need to request more cores
        to_write += 'queue'
        config_file_path = run_test_path + '/' + self.CONDOR_FILE_NAME
        try:
            with open(config_file_path, 'w') as config:
                config.write(to_write)
            return True
        except Exception as e:
            self.logger.error('There was a problem while creating the config file: %s message: %s \ntraceback %s' % (config_file_path, str(e), traceback.format_exc()))
            return False

    def submit_request(self, prepid, run_test_path):
        mcm_request = request(self.request_db.get(prepid))
        # check if the request should be validated as part of a chain
        for chain_prepid in mcm_request.get_attribute('member_of_chain'):
            mcm_chain = chained_request(self.chained_request_db.get(chain_prepid))
            if mcm_chain.get_attribute('validate') and prepid in mcm_chain.get_attribute('chain')[mcm_chain.get_attribute('step'):]:
                return {}
        aux_validation = mcm_request.get_attribute(self.DOC_VALIDATION)
        to_write = mcm_request.get_setup_file(run=True, do_valid=True, for_validation=True)
        file_name = self.TEST_FILE_NAME % prepid
        if not self.create_test_file(to_write, run_test_path, file_name):
            mcm_request.set_attribute(self.DOC_VALIDATION, aux_validation)
            mcm_request.test_failure(
                message='There was a problem while creating the file for prepid: %s' % (mcm_request.get_attribute('prepid')),
                what='Validation run test',
                rewind=True
            )
            return {}
        timeout = mcm_request.get_timeout()
        memory = mcm_request.get_attribute("memory")
        threads = mcm_request.get_core_num()
        self.create_htcondor_config_file(run_test_path, prepid, timeout, memory, threads)
        job_info = self.execute_command_submission(prepid, run_test_path)
        if 'error' in job_info:
            mcm_request.test_failure(message=job_info['error'], what='Validation run test', rewind=True)
            return {}
        job_info[self.DOC_REV] = mcm_request.json()[self.DOC_REV]
        job_info[self.DOC_VALIDATION] = mcm_request.get_attribute(self.DOC_VALIDATION) #this field change when calling request.get_setup_file, to be propagated in case of success
        return job_info

    def execute_command_submission(self, prepid, run_test_path):
        cmd = 'cd %s && condor_submit %s' % (run_test_path, self.CONDOR_FILE_NAME)
        self.logger.info('Executing submission command: \n%s' % cmd)
        stdin,  stdout,  stderr = self.ssh_exec.execute(cmd)
        message_ssh = "There was a problem with SSH remote execution of command:\n{0}!".format(cmd)
        if not self.check_ssh_outputs(stdin, stdout, stderr,
                message_ssh):
            return {'error': message_ssh}
        out = stdout.read()
        errors = stderr.read()
        self.logger.info(out)
        if 'submitted to cluster' not in out:
            message = 'Job submission failed for request: %s \nerror output:\n %s' % (prepid, errors)
            self.logger.error(message)
            return {'error': message}
        job_id = out.split()[7]
        return {self.JOB_ID: job_id[:-1]} #remove .

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
        to_write = mcm_chained_request.get_setup(run=True, validation= True, for_validation=True)
        file_name = self.TEST_FILE_NAME % prepid
        if not self.create_test_file(to_write, run_test_path, file_name):
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
        timeout, memory, threads = mcm_chained_request.get_timeout_memory_threads()
        self.create_htcondor_config_file(run_test_path, prepid, timeout, memory, threads)
        job_info = self.execute_command_submission(prepid, run_test_path)
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
                else:
                    self.removeDirectory(test_path)
            except Exception as e:
                #Catch any unexpected exepction and keep going
                message = "Unexpected exception while trying to submit %s message: %s\ntraceback %s" % (prepid, str(e), traceback.format_exc())
                try:
                    self.report_error(prepid, message)
                    self.removeDirectory(test_path)
                except Exception as e:
                    self.logger.error('Error while reporting failure message: %s\ntraceback %s' % (str(e), traceback.format_exc()))
                    self.removeDirectory(test_path)

    def get_jobs_status(self):
        cmd = 'condor_q -format "%d " ClusterId -format "%d\n" JobStatus'
        stdin, stdout, stderr = self.ssh_exec.execute(cmd)
        if not self.check_ssh_outputs(stdin, stdout, stderr,
                "Problem with SSH execution of command: %s" % (cmd)):
            return None
        jobs_dict = {}
        lines = stdout.read().split('\n')
        for line in lines:
            columns = line.split()
            if not len(columns):
                break
            job_id = columns[0]
            status = ''
            if columns[1] == '4':
                status = 'DONE'
            elif columns[1] == '2':
                status = 'RUN'
            elif columns[1] == '1':
                status = 'IDLE'
            jobs_dict[job_id] = status
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
        if jobs_dict is None:
            return
        remove_jobs = []
        for prepid, doc_info in self.submmited_jobs.iteritems():
            try:
                job_id = doc_info[self.JOB_ID]
                if job_id not in jobs_dict or jobs_dict[job_id] in ['DONE', '']:
                    self.logger.info('Job %s for prepid %s is DONE, processing it.....' % (job_id, prepid))
                    self.process_finished_job(prepid, doc_info)
                    remove_jobs.append(prepid)
                    continue
                elif jobs_dict[job_id] in ['RUN', 'IDLE']:
                    self.logger.info('Job %s for prepid %s status: %s' % (job_id ,prepid, jobs_dict[job_id]))
            except Exception as e:
                #Catch any unexpected exception and keep going
                message = "Unexpected exception while monitoring job for prepid %s message: %s \ntraceback: %s" % (prepid, str(e), traceback.format_exc())
                self.report_error(prepid, message)
                remove_jobs.append(prepid)
        for prepid in remove_jobs:
            self.submmited_jobs.pop(prepid)
            self.removeDirectory(self.test_directory_path + prepid)

    def parse_error_out(self, error_out):
        lines = error_out.split('\n')
        parsed_lines = ''
        previous_line = ''
        events_log_start = False
        for line in lines:
            if 'Begin processing the' in line:
                if not events_log_start:
                    parsed_lines += line + '\n'
                    parsed_lines += '....\n'
                    events_log_start = True
                previous_line = line
            elif events_log_start:
                parsed_lines += previous_line + '\n'
                parsed_lines += line + '\n'
                events_log_start = False
            else:
                parsed_lines += line + '\n'
        return parsed_lines

    def process_finished_job(self, prepid, doc_info):
        file_name = self.TEST_FILE_NAME % prepid
        out_path = self.test_directory_path + prepid + '/' + file_name + '.out'
        error_path = self.test_directory_path + prepid + '/' + file_name + '.err'
        log_path = self.test_directory_path + prepid + '/' + file_name + '.log'
        job_out, job_error_out = self.read_file_from_afs(out_path)
        error_out, _ = self.read_file_from_afs(error_path, trials_time_out=2)
        error_out = self.parse_error_out(error_out)
        log_out, _ = self.read_file_from_afs(log_path)
        was_exited = False
        if 'return value 0' in log_out:
            if 'chain' in prepid:
                self.process_finished_chain_success(prepid, doc_info, job_out, error_out, log_out)
            else:
                self.process_finished_request_success(prepid, doc_info, job_out, error_out, log_out)
            return
        elif 'return value' in log_out:
            was_exited = True
        if 'chain' in prepid:
            self.process_finished_chain_failed(prepid, job_out, job_error_out, error_out, was_exited, out_path, log_out)
        else:
            self.process_finished_request_failed(prepid, job_out, error_out, was_exited, job_error_out, out_path, log_out)

    def process_finished_chain_failed(self, prepid, job_out, job_error_out, error_out, was_exited, out_path, log_out):
        mcm_chained_request = chained_request(self.chained_request_db.get(prepid))
        if not was_exited:
            message = "File %s does not look properly formatted or does not exist. \n %s \n %s \n Error out: \n%s \n Log out:\n %s" % (
                out_path, job_out, job_error_out, error_out, log_out)
        else:
            message = "Job validation failed for chain %s \nJob out: \n%s \n Error out: \n%s \n Log out: \n%s" % (prepid, job_out, error_out, log_out)
        mcm_chained_request.reset_requests(message)

    def process_finished_chain_success(self, prepid, doc_info, job_out, error_out, log_out):
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
                    message = 'Error while picking up all the performance for request %s of chain %s: \n Error:\n%s\n Job out:\n%s\n Error out: \n%s\n Log out: \n%s\n' % (
                        request_prepid,
                        prepid, error,
                        job_out,
                        error_out,
                        log_out
                    )
            if not success:
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

    def process_finished_request_success(self, prepid, doc_info, job_out, error_out, log_out):
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
            error = 'Error:\n%s\n Error out:\n%s\n' % (error, error_out)
            self.process_finished_request_failed(prepid, job_out, error, log_out=log_out)
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

    def process_finished_request_failed(self, prepid, job_out, error_out, was_exited=True, job_error_out='', out_path='', log_out=''):
        mcm_request = request(self.request_db.get(prepid))
        # need to provide all the information back
        if not was_exited:
            no_success_message = "File %s does not look properly formatted or does not exist. \n %s \n %s \n Error out: \n%s \n Log out: \n%s" % (
                out_path, job_out, job_error_out, error_out, log_out)
        else:
            file_name = self.TEST_FILE_NAME % prepid
            no_success_message = '\t Job out: \n%s\n\t Error out: \n%s\n Log out: \n%s ' % (job_out, error_out, log_out)
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
    com = communicator()
    com.flush(0)