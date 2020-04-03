import logging
import json
import paramiko
import tools.settings as settings
from couchdb_layer.mcm_database import database
from json_layer.request import request as Request
from json_layer.chained_request import chained_request as ChainedRequest
from tools.installer import installer as Locator
import xml.etree.ElementTree as ET
from math import ceil


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
    """
    Requests for test:
    SMP-PhaseIITDRSpring19wmLHEGS-00005 - CMSSW_10_6_0
    SUS-RunIIFall17FSPremix-00065 - CMSSW_9_4_12
    SMP-RunIISummer19UL18GEN-00003
    """

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
        cmd = ['module load lxbatch/tzero',
               'condor_q -af:h ClusterId JobStatus']

        stdout, stderr = self.ssh_executor.execute_command(cmd)
        lines = stdout.split('\n')
        if not lines or 'ClusterId JobStatus' not in lines[0]:
            self.logger.error('Htcondor is failing!')
            self.logger.error('stdout:\n%s\nstderr:\n%s', stdout, stderr)
            raise Exception('HTCondor is not working')

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

    def get_requests_to_be_submitted(self):
        query = self.request_db.construct_lucene_query({'status': 'new', 'approval': 'validation'})
        result = self.request_db.full_text_search('search', query, page=-1, include_fields='prepid')
        result = [r['prepid'] for r in result]

        result = [r for r in result if r in ('SMP-PhaseIITDRSpring19wmLHEGS-00005', 'SUS-RunIIFall17FSPremix-00065', 'SMP-RunIISummer19UL18GEN-00003')]
        # self.logger.info('Requests with validation-new:\n%s', '\n'.join(result))
        return result

    def get_chained_requests_to_be_submitted(self):
        query = self.chained_request_db.construct_lucene_query({'validate<int>': '1'})
        result = self.chained_request_db.full_text_search('search', query, page=-1, include_fields='prepid')
        result = [r['prepid'] for r in result]
        # self.logger.info('Chained requests with validate=1:\n%s', '\n'.join(result))
        return result

    def get_items_to_be_submitted(self, requests, chained_requests):
        requests = set(requests)
        for chained_request_prepid in chained_requests:
            chained_request = self.chained_request_db.get(chained_request_prepid)
            for request in chained_request['chain']:
                if request in requests:
                    self.logger.info('Removing %s from requests because it is in %s', request, chained_request_prepid)
                    requests.remove(request)

        already_submitted = set(self.get_all_from_storage().keys())
        self.logger.info('Items that are already submitted: %s', ', '.join(already_submitted))
        to_be_submitted = list((requests | set(chained_requests)) - already_submitted)
        self.logger.info('Items to be submitted:\n%s', '\n'.join(to_be_submitted))
        return to_be_submitted

    def run(self):
        # Handle submitted requests and chained requests
        condor_jobs = self.get_jobs_in_condor()
        self.process_running_jobs(condor_jobs)
        # Handle new requests and chained requests
        requests_to_submit = self.get_requests_to_be_submitted()
        chained_requests_to_submit = self.get_chained_requests_to_be_submitted()
        items_to_submit = self.get_items_to_be_submitted(requests_to_submit, chained_requests_to_submit)
        self.submit_items(items_to_submit)

    def process_running_jobs(self, condor_jobs):
        for prepid, request_in_storage in self.get_all_from_storage().iteritems():
            self.logger.info('Looking at %s', prepid)
            stage = request_in_storage['stage']
            running_dict = request_in_storage['running']
            self.logger.info('%s is at stage %s' % (prepid, stage))
            for _, core_dict in running_dict.iteritems():
                if core_dict.get('condor_status') == 'DONE':
                    continue

                condor_id = str(core_dict['condor_id'])
                if condor_id in condor_jobs:
                    core_dict['condor_status'] = condor_jobs[condor_id]
                else:
                    # Done?
                    core_dict['condor_status'] = 'DONE'

            self.save_to_storage(prepid, request_in_storage)
            self.logger.info('%s has these jobs running: %s' % (prepid, ', '.join(['%s (%s - %s)' % (k, v['condor_id'], v.get('condor_status', '<unknown>')) for k, v in running_dict.iteritems()])))

        for prepid, request_in_storage in self.get_all_from_storage().iteritems():
            self.logger.info('Looking again at %s', prepid)
            stage = request_in_storage['stage']
            running_dict = request_in_storage['running']
            all_done = len(core_dict) > 0
            for _, core_dict in running_dict.iteritems():
                if core_dict.get('condor_status') != 'DONE':
                    all_done = False
                    break

                if not core_dict.get('condor_id'):
                    all_done = False
                    self.validation_failed(prepid)
                    break

            if all_done:
                self.logger.info('All DONE for %s at stage %s', prepid, stage)
                request_dict = self.get_from_storage(prepid)
                request_dict['running'] = {}
                request_dict['stage'] += 1
                if stage == 1:
                    try:
                        request_dict['done'] = {'1': self.parse_job_report(prepid, 1)}
                        self.save_to_storage(prepid, request_dict)
                    except Exception as ex:
                        self.logger.error(ex)
                        self.validation_failed(prepid)
                        continue

                    self.submit_item(prepid, 2)
                    self.submit_item(prepid, 4)
                    self.submit_item(prepid, 8)
                else:
                    try:
                        request_dict['done']['2'] = self.parse_job_report(prepid, 2)
                        request_dict['done']['4'] = self.parse_job_report(prepid, 4)
                        request_dict['done']['8'] = self.parse_job_report(prepid, 8)
                        self.save_to_storage(prepid, request_dict)
                    except Exception as ex:
                        self.logger.error(ex)
                        self.validation_failed(prepid)
                        continue

                    self.validation_succeeded(prepid)

    def validation_failed(self, prepid):
        if '-chain_' in prepid:
            chained_req = self.chained_request_db.get(prepid)
            chained_req['validate'] = 0
            self.chained_request_db.save(chained_req)
            requests = self.get_requests_from_chained_request(ChainedRequest(chained_req))
            requests = [r.json() for r in requests]
        else:
            requests = [self.request_db.get(prepid)]

        for request in requests:
            request['validation']['results'] = {}
            request['approval'] = 'none'
            request['status'] = 'new'
            self.logger.warning('Saving %s', request['prepid'])
            self.request_db.save(request)

        self.delete_from_storage(prepid)
        self.logger.info('Validation failed for %s', prepid)

    def validation_succeeded(self, prepid):
        if '-chain_' in prepid:
            chained_req = self.chained_request_db.get(prepid)
            chained_req['validate'] = 0
            self.chained_request_db.save(chained_req)

        requests = {}
        request_dict = self.get_from_storage(prepid)
        for core_number in request_dict['done'].keys():
            for request_prepid in request_dict['done'][core_number].keys():
                if request_prepid not in requests:
                    requests[request_prepid] = self.request_db.get(request_prepid)
                    requests[request_prepid]['validation']['results'] = {}

                request = requests[request_prepid]
                request['approval'] = 'validation'
                request['status'] = 'validation'
                request['validation']['results'][core_number] = request_dict['done'][core_number][request_prepid]

        for _, request in requests.iteritems():
            self.logger.warning('Saving %s', request['prepid'])
            self.request_db.save(request)

        self.delete_from_storage(prepid)
        self.logger.info('Validation succeeded for %s', prepid)

    def parse_job_report(self, prepid, threads):
        requests_to_parse = []
        if '-chain_' in prepid:
            chained_request = ChainedRequest(self.chained_request_db.get(prepid))
            requests = self.get_requests_from_chained_request(chained_request)
        else:
            request = Request(self.request_db.get(prepid))
            requests = [request]

        results = {}
        self.logger.info('Parsing job reports for %s with %s threads', prepid, threads)
        item_directory = '%s%s' % (self.test_directory_path, prepid)
        for request in requests:
            request_prepid = request.get_attribute('prepid')
            report_file_name = '%s_%s_threads_report.xml' % (request_prepid, threads)
            self.logger.info('Report file name: %s', report_file_name)
            tree = ET.parse('%s/%s' % (item_directory, report_file_name))
            root = tree.getroot()

            total_events = root.find('.//TotalEvents')
            if total_events is not None:
                total_events = int(total_events.text)
            else:
                total_events = None

            # self.logger.info('TotalEvents %s', total_events)
            event_throughput = None
            peak_value_rss = None
            total_size = None
            total_job_cpu = None
            total_job_time = None
            for child in root.findall('.//PerformanceSummary/Metric'):
                attr_name = child.attrib['Name']
                attr_value = child.attrib['Value']
                if attr_name == 'EventThroughput':
                    event_throughput = float(attr_value)
                    # self.logger.info('EventThroughput %s', event_throughput)
                elif attr_name == 'PeakValueRss':
                    peak_value_rss = float(attr_value)
                    # self.logger.info('PeakValueRss %s', peak_value_rss)
                elif attr_name == 'Timing-tstoragefile-write-totalMegabytes':
                    total_size = float(attr_value) * 1024  # Megabytes to Kilobytes
                    # self.logger.info('Timing-tstoragefile-write-totalMegabytes %s', total_size)
                elif attr_name == 'TotalJobCPU':
                    total_job_cpu = float(attr_value)
                    # self.logger.info('TotalJobCPU %s', total_job_cpu)
                elif attr_name == 'TotalJobTime':
                    total_job_time = float(attr_value)
                    # self.logger.info('TotalJobTime %s', total_job_time)

            self.logger.info('event_throughput %s', event_throughput)
            self.logger.info('peak_value_rss %s', peak_value_rss)
            self.logger.info('total_size %s', total_size)
            self.logger.info('total_job_cpu %s', total_job_cpu)
            self.logger.info('total_job_time %s', total_job_time)
            self.logger.info('total_events %s', total_events)
            if None in (event_throughput, peak_value_rss, total_size, total_job_cpu, total_job_time, total_events):
                self.logger.error('Not all values are in %s, aborting %s with %s threads', report_file_name, prepid, threads)
                raise Exception()

            events_ran = request.get_event_count_for_validation()
            time_per_event = 1.0 / event_throughput
            size_per_event = total_size / total_events
            cpu_efficiency = total_job_cpu / (threads * total_job_time)
            filter_efficiency = float(total_events) / events_ran
            self.logger.info('Time per event %.4fs', time_per_event)
            self.logger.info('Size per event %.4fkb', size_per_event)
            self.logger.info('CPU efficiency %.2f%%', cpu_efficiency * 100)
            self.logger.info('Filter efficiency %.2f%%', filter_efficiency * 100)
            self.logger.info('Peak value RSS %.2fMB', peak_value_rss)
            results[request_prepid] = {'time_per_event': time_per_event,
                                       'size_per_event': size_per_event,
                                       'cpu_efficiency': cpu_efficiency,
                                       'filter_efficiency': filter_efficiency,
                                       'peak_value_rss': peak_value_rss}

        return results

    def get_htcondor_submission_file(self, prepid, job_length, threads, memory, output_prepids):
        transfer_input_files = ['voms_proxy.txt']
        transfer_output_files = []
        for output_prepid in output_prepids:
            transfer_output_files.append('%s_%s_threads_report.xml' % (output_prepid, threads))

        transfer_output_files = ','.join(transfer_output_files)
        transfer_input_files = ','.join(transfer_input_files)
        # HTCondor gives 2GB per core, if you want more memory you need to request more cores
        request_cores = int(max(threads, ceil(memory / 2000.0)))
        if request_cores != threads:
            self.logger.warning('Will request %s cpus because memory is %s', request_cores, memory)

        condor_file = ['universe              = vanilla',
                       # 'environment           = HOME=/afs/cern.ch/user/p/pdmvserv',
                       'executable            = %s_%s_threads_launcher.sh' % (prepid, threads),
                       'output                = %s_%s_threads.out' % (prepid, threads),
                       'error                 = %s_%s_threads.err' % (prepid, threads),
                       'log                   = %s_%s_threads.log' % (prepid, threads),
                       'transfer_output_files = %s' % (transfer_output_files),
                       'transfer_input_files  = %s' % (transfer_input_files),
                       # 'periodic_remove       = (JobStatus == 5 && HoldReasonCode != 1 && HoldReasonCode != 16 && HoldReasonCode != 21 && HoldReasonCode != 26)',
                       '+MaxRuntime           = %s' % (job_length),
                       'RequestCpus           = %s' % (request_cores),
                       '+AccountingGroup      = "group_u_CMS.CAF.PHYS"',
                       'requirements          = (OpSysAndVer =?= "CentOS7")',
                       # Leave in queue when status is DONE or HOLD for 30 minutes - 1800 seconds
                       'leave_in_queue        = (JobStatus == 4 || JobStatus == 5) && (CompletionDate =?= UNDEFINED || ((CurrentTime - CompletionDate) < 1800))',
                       'queue']

        condor_file = '\n'.join(condor_file)
        # self.logger.info('\n%s' % (condor_file))
        return condor_file

    def submit_items(self, items):
        for prepid in items:
            # Prepare empty directory for validation
            item_directory = '%s%s' % (self.test_directory_path, prepid)
            command = ['rm -rf %s' % (item_directory),
                       'mkdir -p %s' % (item_directory)]
            _, _ = self.ssh_executor.execute_command(command)
            self.submit_item(prepid, 1)

    def submit_item(self, prepid, threads):
        item_directory = '%s%s' % (self.test_directory_path, prepid)
        # Get list of requests that will run in this validation
        # Single request validation will have only that list
        # Chained request validation might have multiple requests in sequence
        if '-chain_' in prepid:
            chained_request = ChainedRequest(self.chained_request_db.get(prepid))
            requests = self.get_requests_from_chained_request(chained_request)
        else:
            request = Request(self.request_db.get(prepid))
            requests = [request]

        job_length = 0
        memory = 0
        test_script = ''
        request_prepids = []
        for request in requests:
            # Max job runtime
            request_prepids.append(request.get_attribute('prepid'))
            job_length += request.get_validation_max_runtime()
            # Get max memory of all requests
            memory = max(memory, self.get_memory(request, threads))
            # Combine validation scripts to one long script
            test_script += request.get_setup_file2(True, True, threads)
            test_script += '\n'

        # Make a HTCondor .sub file
        condor_file = self.get_htcondor_submission_file(prepid, job_length, threads, memory, request_prepids)

        # Write files straight to afs
        condor_file_name = '%s/%s_%s_threads_condor.sub' % (item_directory, prepid, threads)
        with open(condor_file_name, 'w') as f:
            f.write(condor_file)

        test_script_file_name = '%s/%s_%s_threads_launcher.sh' % (item_directory, prepid, threads)
        with open(test_script_file_name, 'w') as f:
            f.write(test_script)

        # Condor submit
        command = ['cd %s' % (item_directory),
                   'voms-proxy-init --voms cms --out $(pwd)/voms_proxy.txt --hours 48',
                   'chmod +x %s' % (test_script_file_name.split('/')[-1]),
                   'module load lxbatch/tzero',
                   'condor_submit %s' % (condor_file_name.split('/')[-1])]
        stdout, stderr = self.ssh_executor.execute_command(command)

        # Get condor job ID from std output
        if not stderr and '1 job(s) submitted to cluster' in stdout:
            # output is "1 job(s) submitted to cluster xxxxxx"
            condor_id = int(float(stdout.split()[-1]))
            self.logger.info('Submitted %s, HTCondor ID %s' % (test_script_file_name, condor_id))
        else:
            self.logger.error('Error submitting %s:\nSTDOUT: %s\nSTDERR: %s', test_script_file_name, stdout, stderr)
            return

        if threads == 1:
            self.save_to_storage(prepid, {'stage': 1,
                                          'running': {'1': {'condor_id': condor_id}}})
        else:
            storage_dict = self.get_from_storage(prepid)
            storage_dict['running']['%s' % (threads)] = {'condor_id': condor_id}
            self.save_to_storage(prepid, storage_dict)

    def get_requests_from_chained_request(self, chained_request):
        """
        Return list of Request objects that should be in validation
        """
        requests = []
        for request_prepid in chained_request.get_attribute('chain'):
            request = Request(self.request_db.get(request_prepid))
            if not request.is_root:
                continue

            requests.append(request)

        return requests

    def get_memory(self, request, target_threads):
        """
        Get memory scaled accordingly to number of threads
        """
        prepid = request.get_attribute('prepid')
        sequences = request.get_attribute('sequences')
        request_memory = request.get_attribute('memory')
        request_threads = max((int(sequence.get('nThreads', 1)) for sequence in sequences))
        if request_threads == target_threads:
            # Memory provided by user
            memory = request_memory
            self.logger.info('%s will use use %sMB for %s thread validation', prepid, memory, target_threads)
            return memory

        if request_threads == 1 and request_memory == 2300:
            single_core_memory = 2000
        else:
            single_core_memory = int(request_memory / request_threads)
            single_core_memory = max(single_core_memory, 2000)

        memory = target_threads * single_core_memory
        self.logger.info('%s has %s nThreads and %sMB memory. Single core memory %sMB, so will use %sMB for %s thread validation',
                         prepid,
                         request_threads,
                         request_memory,
                         single_core_memory,
                         memory,
                         target_threads)
        return memory

    def save_to_storage(self, prepid, dict_to_save):
        all_validations = self.get_all_from_storage()
        all_validations[prepid] = dict_to_save
        with open('validations.json', 'w') as f:
            f.write(json.dumps(all_validations, indent=2, sort_keys=True))

    def get_from_storage(self, prepid):
        return self.get_all_from_storage().get(prepid)

    def get_all_from_storage(self):
        with open('validations.json', 'r') as f:
            all_validations = json.loads(f.read())

        return all_validations

    def delete_from_storage(self, prepid):
        all_validations = self.get_all_from_storage()
        if prepid in all_validations:
            del all_validations[prepid]
            with open('validations.json', 'w') as f:
                f.write(json.dumps(all_validations, indent=2, sort_keys=True))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='[%(asctime)s][%(levelname)s] %(message)s',
                        datefmt='%Y-%b-%d:%H:%M:%S')
    logging.info('Starting...')
    ValidationControl().run()
    logging.info('Done')
