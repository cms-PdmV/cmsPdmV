import logging
import json
import paramiko
import tools.settings as settings
from couchdb_layer.mcm_database import database
from json_layer.request import request as Request
from json_layer.chained_request import chained_request as ChainedRequest
from tools.installer import installer as Locator


class SSHExecutor():
    """
    SSH executor allows to perform remote commands and upload/download files
    """

    def __init__(self, host, credentials_path):
        self.ssh_client = None
        self.ftp_client = None
        self.logger = logging.getLogger()
        self.remote_host = host
        self.credentials_file_path = credentials_path
        self.timeout = 3600

    def setup_ssh(self):
        """
        Initiate SSH connection and save it as self.ssh_client
        """
        self.logger.debug('Will set up ssh')
        if self.ssh_client:
            self.close_connections()

        with open(self.credentials_file_path) as json_file:
            credentials = json.load(json_file)

        self.logger.info('Credentials loaded successfully: %s', credentials['username'])
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(self.remote_host,
                                username=credentials["username"],
                                password=credentials["password"],
                                timeout=30)
        self.logger.debug('Done setting up ssh')

    def setup_ftp(self):
        """
        Initiate SFTP connection and save it as self.ftp_client
        If needed, SSH connection will be automatically set up
        """
        self.logger.debug('Will set up ftp')
        if self.ftp_client:
            self.close_connections()

        if not self.ssh_client:
            self.setup_ssh()

        self.ftp_client = self.ssh_client.open_sftp()
        self.logger.debug('Done setting up ftp')

    def execute_command(self, command):
        """
        Execute command over SSH
        """
        if not self.ssh_client:
            self.setup_ssh()

        if isinstance(command, list):
            command = '; '.join(command)

        self.logger.debug('Executing %s', command)
        (_, stdout, stderr) = self.ssh_client.exec_command(command, timeout=self.timeout)
        self.logger.debug('Executed %s. Reading response', command)
        stdout_list = []
        stderr_list = []
        for line in stdout.readlines():
            stdout_list.append(line[0:256])

        for line in stderr.readlines():
            stderr_list.append(line[0:256])

        stdout = ''.join(stdout_list).strip()
        stderr = ''.join(stderr_list).strip()

        # Read output from stdout and stderr streams
        if stdout:
            self.logger.debug('STDOUT (%s): %s', command, stdout)

        if stderr:
            self.logger.error('STDERR (%s): %s', command, stderr)

        return stdout, stderr

    def upload_file(self, copy_from, copy_to):
        """
        Upload a file
        """
        self.logger.debug('Will upload file %s to %s', copy_from, copy_to)
        if not self.ftp_client:
            self.setup_ftp()

        try:
            self.ftp_client.put(copy_from, copy_to)
            self.logger.debug('Uploaded file to %s', copy_to)
        except Exception as ex:
            self.logger.error('Error uploading file from %s to %s. %s', copy_from, copy_to, ex)
            return False

        return True

    def download_file(self, copy_from, copy_to):
        """
        Download file from remote host
        """
        self.logger.debug('Will download file %s to %s', copy_from, copy_to)
        if not self.ftp_client:
            self.setup_ftp()

        try:
            self.ftp_client.get(copy_from, copy_to)
            self.logger.debug('Downloaded file to %s', copy_to)
        except Exception as ex:
            self.logger.error('Error downloading file from %s to %s. %s', copy_from, copy_to, ex)
            return False

        return True

    def close_connections(self):
        """
        Close any active connections
        """
        if self.ftp_client:
            self.logger.debug('Closing ftp client')
            self.ftp_client.close()
            self.ftp_client = None
            self.logger.debug('Closed ftp client')

        if self.ssh_client:
            self.logger.debug('Closing ssh client')
            self.ssh_client.close()
            self.ssh_client = None
            self.logger.debug('Closed ssh client')


class ValidationControl():

    def __init__(self):
        self.request_db = database('requests')
        self.chained_request_db = database('chained_requests')
        self.ssh_executor = SSHExecutor('lxplus.cern.ch',
                                        '/afs/cern.ch/user/j/jrumsevi/private/credentials_json.txt')
        self.logger = logging.getLogger()
        locator = Locator('validation/tests', care_on_existing=False)
        self.test_directory_path = locator.location()
        self.logger.info('Location %s' % (self.test_directory_path))

    def get_jobs_in_condor(self):
        cmd = [# 'module load lxbatch/tzero',
               'condor_q -af:h ClusterId JobStatus']

        stdout, stderr = self.ssh_executor.execute_command(cmd)
        lines = stdout.split('\n')
        if not lines or 'ClusterId JobStatus' not in lines[0]:
            self.logger.error('Htcondor is failing!')
            self.logger.error('stdout:\n%s\nstderr:\n%s', stdout, stderr)
            return None

        jobs_dict = {}
        lines = lines[1:]
        for line in lines:
            columns = line.split()
            if not len(columns):
                break

            if columns[1] == '4':
                status = 'DONE'
            elif columns[1] == '2':
                status = 'RUN'
            elif columns[1] == '1':
                status = 'IDLE'
            else:
                continue

            job_id = columns[0]
            jobs_dict[job_id] = status

        self.logger.info('Job status in HTCondor:%s' % (json.dumps(jobs_dict, indent=2, sort_keys=True)))
        return jobs_dict

    def get_existing_jobs(self):
        return {}

    def get_requests_to_be_submitted(self):
        query = self.request_db.construct_lucene_query({'status': 'new', 'approval': 'validation'})
        result = self.request_db.full_text_search('search', query, page=-1, include_fields='prepid')
        result = [r['prepid'] for r in result]
        self.logger.info('Requests to be submitted:\n%s', '\n'.join(result))
        return result

    def get_chained_requests_to_be_submitted(self):
        query = self.chained_request_db.construct_lucene_query({'validate<int>': '1'})
        result = self.chained_request_db.full_text_search('search', query, page=-1, include_fields='prepid')
        result = [r['prepid'] for r in result]
        self.logger.info('Chained requests to be submitted:\n%s', '\n'.join(result))
        return result

    def get_items_to_be_submitted(self, requests, chained_requests):
        requests = set(requests)
        for chained_request_prepid in chained_requests:
            chained_request = self.chained_request_db.get(chained_request_prepid)
            for request in chained_request['chain']:
                if request in requests:
                    self.logger.info('Removing %s from requests because it is in %s', request, chained_request_prepid)
                    requests.remove(request)

        return list(requests | set(chained_requests))

    def run(self):
        # Handle submitted requests and chained requests
        condor_jobs = self.get_jobs_in_condor()
        submitted_jobs = self.get_existing_jobs()

        # Handle new requests and chained requests
        requests_to_submit = self.get_requests_to_be_submitted()
        chained_requests_to_submit = self.get_chained_requests_to_be_submitted()
        items_to_submit = self.get_items_to_be_submitted(requests_to_submit, chained_requests_to_submit)
        self.submit_items(items_to_submit)

    def get_htcondor_submission_file(self, prepid, scram_arch, job_length, threads, memory):
        # HTCondor gives 2GB per core, if you want more memory you need to request more cores)
        transfer_input_files = ['%s_%s_threads_test.sh' % (prepid, threads)]
        transfer_output_files = ['%s_%s_threads_report.xml' % (prepid, threads)]
        transfer_input_files = ','.join(transfer_input_files)
        transfer_output_files = ','.join(transfer_output_files)
        condor_file = ['universe              = vanilla',
                       'environment           = HOME=/afs/cern.ch/user/p/pdmvserv',
                       'executable            = %s_%s_threads_launcher.sh' % (prepid, threads),
                       'output                = %s_%s_threads.out' % (prepid, threads),
                       'error                 = %s_%s_threads.err' % (prepid, threads),
                       'log                   = %s_%s_threads.log' % (prepid, threads),
                       'transfer_output_files = %s' % (transfer_output_files),
                       'transfer_input_files  = %s' % (transfer_input_files),
                       'periodic_remove       = (JobStatus == 5 && HoldReasonCode != 1 && HoldReasonCode != 16 && HoldReasonCode != 21 && HoldReasonCode != 26)',
                       '+MaxRuntime           = %s' % (job_length),
                       'RequestCpus           = %s' % (threads),
                       # '+AccountingGroup      = "group_u_CMS.CAF.PHYS"',
                       'requirements          = (OpSysAndVer =?= "CentOS7")',
                       'queue']

        condor_file = '\n'.join(condor_file)
        self.logger.info('\n%s' % (condor_file))
        return condor_file

    def submit_items(self, items):
        for item in items:
            self.logger.info('\n\n')
            self.logger.info('*' * 100)
            self.logger.info('*' * 100)
            self.logger.info('*' * 100)
            self.logger.info('\n\n')
            if '-chain_' in item:
                self.submit_new_chained_request(item)
            else: 
                self.submit_new_request(item, threads=1)

    def submit_new_chained_request(self, prepid, threads=1):
        chained_request = ChainedRequest(self.chained_request_db.get(prepid))
        job_length = 0
        # How to handle multiple scram archs?
        scram_archs = []
        batch_timeout = settings.get_value('batch_timeout') * 60
        for request_prepid in chained_request.get_attribute('chain'):
            request = Request(self.request_db.get(request_prepid))
            if not request.is_root:
                continue

            # Max job runtime
            multiplier = request.get_attribute('validation').get('time_multiplier', 1)
            job_length += batch_timeout * multiplier
            scram_archs.append(request.get_scram_arch().lower())

        memory = threads * 2000
        condor_file = self.get_htcondor_submission_file(prepid,
                                                        scram_archs[0],
                                                        job_length,
                                                        threads,
                                                        memory)

    def submit_new_request(self, prepid, threads=1):
        request = Request(self.request_db.get(prepid))
        # Max job runtime
        batch_timeout = settings.get_value('batch_timeout') * 60
        multiplier = request.get_attribute('validation').get('time_multiplier', 1)
        job_length = batch_timeout * multiplier
        # Threads
        memory = threads * 2000
        condor_file = self.get_htcondor_submission_file(prepid,
                                                        request.get_scram_arch().lower(),
                                                        job_length,
                                                        threads,
                                                        memory)
        test_script = request.get_setup_file2(True, True, threads)
        Locator('%s%s' % (self.test_directory_path, prepid),
                care_on_existing=False,
                is_abs_path=True)
        file_name = '%s%s/%s_%s_threads' % (self.test_directory_path, prepid, prepid, threads)
        condor_file_name = '%s_condor.sub' % (file_name)
        test_script_file_name = '%s_launcher.sh' % (file_name)
        self.logger.info('Writing %s', condor_file_name)
        with open(condor_file_name, 'w') as f:
            f.write(condor_file)

        self.logger.info('Writing %s', test_script_file_name)
        with open(test_script_file_name, 'w') as f:
            f.write(test_script)

        command = ['cd %s%s' % (self.test_directory_path, prepid),
                   'condor_submit %s' % (condor_file_name.split('/')[-1])]
        stdout, stderr = self.ssh_executor.execute_command(command)

        if not stderr and '1 job(s) submitted to cluster' in stdout:
            # output is "1 job(s) submitted to cluster 801341"
            condor_id = int(float(stdout.split()[-1]))
            self.logger.info('Submitted %s with %s threads, HTCondor ID %s' % (prepid, threads, condor_id))
        else:
            self.logger.error('Error submitting %s with %s threads:\nSTDOUT: %s\nSTDERR: %s', prepid, threads, stdout, stderr)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='[%(asctime)s][%(levelname)s] %(message)s',
                        datefmt='%Y-%b-%d:%H:%M:%S')
    logging.info('Starting...')
    ValidationControl().run()
    logging.info('Done')
