import logging
import json
import sys
import os.path
import xml.etree.ElementTree as ET
from math import ceil, sqrt
from xml.parsers.expat import ExpatError
from validation_storage import ValidationStorage
from new_ssh_executor import SSHExecutor

sys.path.append(os.path.abspath(os.path.pardir + '/../'))
import tools.settings as settings
from couchdb_layer.mcm_database import database
from json_layer.request import request as Request
from json_layer.chained_request import chained_request as ChainedRequest
from tools.installer import installer as Locator


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
        self.ssh_executor = SSHExecutor(settings.get_value('node_for_test'),
                                        '/afs/cern.ch/user/j/jrumsevi/private/credentials_json.txt')
        self.storage = ValidationStorage()
        self.logger = logging.getLogger()
        locator = Locator('validation/tests', care_on_existing=False)
        self.test_directory_path = locator.location()
        self.logger.info('Location %s' % (self.test_directory_path))

    def get_jobs_in_condor(self):
        """
        Fetch jobs from HTCondor
        Return a dictionary where key is job id and value is status (IDLE, RUN, DONE)
        """
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
                continue

            job_id = columns[0]
            if columns[1] == '4':
                jobs_dict[job_id] = 'DONE'
            elif columns[1] == '2':
                jobs_dict[job_id] = 'RUN'
            elif columns[1] == '1':
                jobs_dict[job_id] = 'IDLE'

        self.logger.info('Job status in HTCondor:%s', json.dumps(jobs_dict, indent=2, sort_keys=True))
        return jobs_dict

    def get_requests_to_be_submitted(self):
        """
        Return list of request prepids that are in status validation-new
        """
        query = self.request_db.construct_lucene_query({'status': 'new', 'approval': 'validation'})
        result = self.request_db.full_text_search('search', query, page=-1, include_fields='prepid')
        result = [r['prepid'] for r in result]

        for_development = ('SMP-PhaseIITDRSpring19wmLHEGS-00005',
                           'SUS-RunIIFall17FSPremix-00065',
                           'SMP-RunIISummer19UL18GEN-00003')
        result = [r for r in result if r in for_development]
        return result

    def get_chained_requests_to_be_submitted(self):
        """
        Return list of chained request prepids that have validate=1
        """
        query = self.chained_request_db.construct_lucene_query({'validate<int>': '1'})
        result = self.chained_request_db.full_text_search('search', query, page=-1, include_fields='prepid')
        result = [r['prepid'] for r in result]
        return result

    def get_items_to_be_submitted(self, requests, chained_requests):
        """
        Take list of requests - list A
        Take list of chained requests -list B, and expand it to list of requests in that chained request - list C
        Remove requests from list A if they are in list C, i.e. do not validate separate requests if
        they are going to be validated together with a chain
        Take list of requests that already had validation submitted to condor - list D
        Add lists A and B together and remove already submitted items - list D
        """
        requests = set(requests)
        for chained_request_prepid in chained_requests:
            chained_request = self.chained_request_db.get(chained_request_prepid)
            for request in chained_request['chain']:
                if request in requests:
                    self.logger.info('Removing %s from requests because it is in %s', request, chained_request_prepid)
                    requests.remove(request)

        already_submitted = set(self.storage.get_all().keys())
        self.logger.info('Items that are already submitted: %s', ', '.join(already_submitted))
        to_be_submitted = list((requests | set(chained_requests)) - already_submitted)
        self.logger.info('Items to be submitted:\n%s', '\n'.join(to_be_submitted))
        return to_be_submitted

    def run(self):
        # Handle submitted requests and chained requests
        condor_jobs = self.get_jobs_in_condor()
        self.update_running_jobs(condor_jobs)
        self.process_done_jobs()
        # Handle new requests and chained requests
        requests_to_submit = self.get_requests_to_be_submitted()
        chained_requests_to_submit = self.get_chained_requests_to_be_submitted()
        items_to_submit = self.get_items_to_be_submitted(requests_to_submit, chained_requests_to_submit)
        self.submit_items(items_to_submit)

    def update_running_jobs(self, condor_jobs):
        """
        Update HTCondor job status in local storage
        """
        for prepid, storage_item in self.storage.get_all().iteritems():
            stage = storage_item['stage']
            running = storage_item['running']
            self.logger.info('%s is at stage %s. Running thread jobs: %s',
                             prepid,
                             stage,
                             ', '.join(running.keys()))
            for cores_name, cores_dict in running.iteritems():
                if cores_dict.get('condor_status') == 'DONE':
                    self.logger.info('%s %s threads job is already DONE', prepid, cores_name)
                    continue

                condor_id = str(cores_dict['condor_id'])
                current_status = cores_dict.get('condor_status', '<unknown>')
                new_status = condor_jobs.get(condor_id, 'DONE')
                if current_status != new_status:
                    cores_dict['condor_status'] = new_status
                    self.logger.info('%s %s threads job changed to %s',
                                     prepid,
                                     cores_name,
                                     new_status)
                    self.storage.save(prepid, storage_item)

        self.logger.info('Currently running jobs:')
        for prepid, storage_item in self.storage.get_all().iteritems():
            stage = storage_item['stage']
            self.logger.info('  %s is at stage %s. Running jobs:', prepid, stage)
            running = storage_item['running']
            for cores_name, cores_dict in running.iteritems():
                self.logger.info('    %s threads attempt: %s, job status: %s, job ID: %s',
                                 cores_name,
                                 cores_dict.get('attempt_number'),
                                 cores_dict.get('condor_status'),
                                 cores_dict.get('condor_id'))


    def process_done_jobs(self):
        """
        Iterate through all jobs in storage and check if they
        are done - all HTCondor jobs are DONE
        """
        for prepid, storage_item in self.storage.get_all().iteritems():
            self.logger.info('Checking if %s is all done', prepid)
            stage = storage_item['stage']
            running = storage_item['running']
            if not running:
                self.logger.error('No running jobs for %s', prepid)
                self.validation_failed(prepid)
                break

            all_done = True
            for cores_name, cores_dict in running.iteritems():
                if not cores_dict.get('condor_id'):
                    self.logger.error('%s %s threads do not have HTCondor ID. Failing validation',
                                      prepid,
                                      cores_name)
                    self.validation_failed(prepid)
                    break

                all_done = all_done and cores_dict.get('condor_status') == 'DONE'
            else:
                if all_done:
                    self.logger.info('All running jobs are DONE for %s at stage %s', prepid, stage)
                    self.process_done_job(prepid)

    def process_done_job(self, prepid):
        """
        Parse reports, fail, resubmit or proceed validation to next step
        """
        self.logger.info('Processing DONE %s', prepid)
        storage_item = self.storage.get(prepid)
        running = storage_item['running']
        cmssw_versions_of_succeeded = []
        for cores_name in list(running.keys()):
            cores_int = int(cores_name)
            cores_dict = running[cores_name]
            # Get report
            report = self.parse_job_report(prepid, cores_int)
            if not report.get('reports_exist', True):
                self.logger.error('Missing reports for %s %s thread validation', prepid, cores_name)
                self.validation_failed(prepid)
                return

            if not report.get('all_values_present', True):
                self.logger.error('Not all values present in %s %s thread reports', prepid, cores_name)
                self.validation_failed(prepid)
                return

            # Check report only for single core validation
            if cores_int != 1:
                storage_item['done'][cores_name] = report
                # Remove current item from running
                del running[cores_name]
                self.storage.save(prepid, storage_item)
                continue

            attempt_number = cores_dict['attempt_number']
            max_attempts = 3
            for request_name, expected_dict in cores_dict['expected'].items():
                report_dict = report[request_name]
                self.logger.info('Checking %s report in %s %s thread validation', request_name, prepid, cores_name)
                self.logger.info('%s %s threads:\nExpected:\n%s\nMeasured:\n%s',
                                 request_name,
                                 cores_name,
                                 json.dumps(expected_dict, indent=2, sort_keys=True),
                                 json.dumps(report_dict, indent=2, sort_keys=True))

                # Check time per event
                expected_time_per_event = expected_dict['time_per_event']
                actual_time_per_event = report_dict['time_per_event']
                time_per_event_margin = settings.get_value('timing_fraction')
                if not self.within(actual_time_per_event, expected_time_per_event, time_per_event_margin):
                    self.logger.error('%s with %s threads expected %ss +- %.2f%% time per event, measured %ss',
                                      request_name,
                                      cores_name,
                                      expected_time_per_event,
                                      time_per_event_margin * 100,
                                      actual_time_per_event)
                    if attempt_number >= max_attempts:
                        self.logger.error('%s with %s threads failed after %s attempts, validation failed',
                                          request_name,
                                          cores_name,
                                          attempt_number)
                        self.validation_failed(prepid)
                        return
                    else:
                        request = self.request_db.get(request_name)
                        number_of_sequences = len(request.get('sequences', []))
                        request['time_event'] = [(expected_time_per_event + 3 * actual_time_per_event) / 4] * number_of_sequences
                        self.request_db.save(request)
                        self.logger.info('Set %s time per event to %.4fs, will resubmit with %s cores',
                                         request_name,
                                         sum(request['time_event']),
                                         cores_name)
                        self.submit_item(prepid, cores_int)
                        break

                # Check size per event
                expected_size_per_event = expected_dict['size_per_event']
                actual_size_per_event = report_dict['size_per_event']
                size_per_event_margin = 0.1
                if not self.within(actual_size_per_event, expected_size_per_event, size_per_event_margin):
                    self.logger.error('%s with %s threads expected %skB +- %.2f%% size per event, measured %skB',
                                      request_name,
                                      cores_name,
                                      expected_size_per_event,
                                      size_per_event_margin * 100,
                                      actual_size_per_event)
                    if attempt_number >= max_attempts:
                        self.logger.error('%s with %s threads failed after %s attempts, validation failed',
                                          request_name,
                                          cores_name,
                                          attempt_number)
                        self.validation_failed(prepid)
                        return
                    else:
                        request = self.request_db.get(request_name)
                        number_of_sequences = len(request.get('sequences', []))
                        request['size_event'] = [(expected_size_per_event + 3 * actual_size_per_event) / 4] * number_of_sequences
                        self.request_db.save(request)
                        self.logger.info('Set %s size per event to %.4fs, will resubmit with %s cores',
                                         request_name,
                                         sum(request['size_event']),
                                         cores_name)
                        self.submit_item(prepid, cores_int)
                        break

                # Check memory usage
                expected_memory = expected_dict['memory']
                actual_memory = report_dict['peak_value_rss']
                if actual_memory > expected_memory:
                    self.logger.error('%s with %s threads expected %sMB memory, measured %sMB',
                                      request_name,
                                      cores_name,
                                      expected_memory,
                                      actual_memory)
                    self.validation_failed(prepid)
                    return

                # Check filter efficiency
                expected_filter_efficiency = expected_dict['filter_efficiency']
                actual_filter_efficiency = report_dict['filter_efficiency']
                sigma = sqrt((actual_filter_efficiency * (1 - actual_filter_efficiency)) / expected_dict['events'])
                sigma = 3 * max(sigma, 0.2)
                self.logger.warning('Using %s%% as filter margin, original value 3 * 0.05', sigma)
                if not (expected_filter_efficiency - sigma < actual_filter_efficiency < expected_filter_efficiency + sigma):
                    self.logger.error('%s with %s cores. %s expected %.4f%% +- %.4f%% filter efficiency, measured %.4f%%',
                                      prepid,
                                      cores_name,
                                      request_name,
                                      expected_filter_efficiency,
                                      sigma,
                                      actual_filter_efficiency)
                    self.validation_failed(prepid)
                    return

                request = self.request_db.get(request_name)
                cmssw_versions_of_succeeded.append(request.get('cmssw_release'))
                self.logger.info('Success for %s in %s validation with %s cores',
                                 request_name,
                                 prepid,
                                 cores_name)
            else:
                # If there was no break in the loop - nothing was resubmitted
                del running[cores_name]
                storage_item['done'][cores_name] = report
                self.storage.save(prepid, storage_item)

        storage_item = self.storage.get(prepid)
        if storage_item['running']:
            # If there is something still running, do not proceed to next stage
            self.logger.info('%s is not proceeding to next stage because there are runnig validation', prepid)
            return

        # Proceed to next stage
        stage = storage_item['stage'] + 1
        storage_item['stage'] = stage
        self.storage.save(prepid, storage_item)
        cmssw_versions_of_succeeded = list(set(cmssw_versions_of_succeeded))
        cmssw_versions_of_succeeded = [tuple(x.replace('CMSSW_', '').split('_')[0:3]) for x in cmssw_versions_of_succeeded]
        cmssw_versions_of_succeeded = sorted(cmssw_versions_of_succeeded)
        self.logger.info('CMSSW versions of requests: %s', ', '.join('_'.join(list(cmssw_versions_of_succeeded))))
        lowest_cmssw_version = cmssw_versions_of_succeeded[0]
        cmssw_too_low = lowest_cmssw_version[0] < 7 or (lowest_cmssw_version[0] == 7 and lowest_cmssw_version[1] < 4)
        if stage == 2 and not cmssw_too_low:
            # Do not submit multicore jobs for < CMSSW 7.4 
            self.submit_item(prepid, 2)
            self.submit_item(prepid, 4)
            self.submit_item(prepid, 8)
        else:
            self.validation_succeeded(prepid)

    def within(self, value, reference, margin_percent):
        return reference * (1 - margin_percent) <= value <= reference * (1 + margin_percent)

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

        self.storage.delete(prepid)
        self.logger.info('Validation failed for %s', prepid)

    def validation_succeeded(self, prepid):
        if '-chain_' in prepid:
            chained_req = self.chained_request_db.get(prepid)
            chained_req['validate'] = 0
            self.chained_request_db.save(chained_req)

        requests = {}
        request_dict = self.storage.get(prepid)
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

        self.storage.delete(prepid)
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
            results[request_prepid] = {}
            report_file_name = '%s_%s_threads_report.xml' % (request_prepid, threads)
            self.logger.info('Report file name: %s', report_file_name)
            if not os.path.isfile('%s/%s' % (item_directory, report_file_name)):
                return {'reports_exist': False}

            try:
                tree = ET.parse('%s/%s' % (item_directory, report_file_name))
            except ExpatError:
                # Empty or invalid XML file
                return {'reports_exist': False}

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
                elif attr_name == 'PeakValueRss':
                    peak_value_rss = float(attr_value)
                elif attr_name == 'Timing-tstoragefile-write-totalMegabytes':
                    total_size = float(attr_value) * 1024  # Megabytes to Kilobytes
                elif attr_name == 'TotalJobCPU':
                    total_job_cpu = float(attr_value)
                elif attr_name == 'TotalJobTime':
                    total_job_time = float(attr_value)
                elif attr_name == 'AvgEventTime' and event_throughput is None:
                    # Using old way if EventThroughput does not exist
                    event_throughput = 1 / (float(attr_value) / threads)

            self.logger.info('Request %s validation with %s threads report values:', request_prepid, threads)
            self.logger.info('  event_throughput %s', event_throughput)
            self.logger.info('  peak_value_rss %s', peak_value_rss)
            self.logger.info('  total_size %s', total_size)
            self.logger.info('  total_job_cpu %s', total_job_cpu)
            self.logger.info('  total_job_time %s', total_job_time)
            self.logger.info('  total_events %s', total_events)
            if None in (event_throughput, peak_value_rss, total_size, total_job_cpu, total_job_time, total_events):
                self.logger.error('Not all values are in %s, aborting %s with %s threads', report_file_name, prepid, threads)
                return {'all_values_present': False}

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
                       'periodic_remove       = (JobStatus == 5 && HoldReasonCode != 1 && HoldReasonCode != 16 && HoldReasonCode != 21 && HoldReasonCode != 26)',
                       '+MaxRuntime           = %s' % (job_length),
                       'RequestCpus           = %s' % (request_cores),
                       '+AccountingGroup      = "group_u_CMS.CAF.PHYS"',
                       'requirements          = (OpSysAndVer =?= "CentOS7")',
                       # Leave in queue when status is DONE for 30 minutes - 1800 seconds
                       'leave_in_queue        = JobStatus == 4 && (CompletionDate =?= UNDEFINED || ((CurrentTime - CompletionDate) < 1800))',
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

        expected_dict = {}
        job_length = 0
        memory = 0
        test_script = ''
        request_prepids = []
        for request in requests:
            # Max job runtime
            request_prepid = request.get_attribute('prepid')
            request_prepids.append(request_prepid)
            job_length += request.get_validation_max_runtime()
            # Get max memory of all requests
            request_memory = self.get_memory(request, threads)
            memory = max(memory, request_memory)
            # Combine validation scripts to one long script
            test_script += request.get_setup_file2(True, True, threads)
            test_script += '\n'
            expected_dict[request_prepid] = {'time_per_event': request.get_sum_time_events(),
                                             'size_per_event': request.get_sum_size_events(),
                                             'memory': request_memory,
                                             'filter_efficiency': request.get_efficiency(),
                                             'events': request.get_event_count_for_validation()}

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
            self.logger.info('Submitted %s, HTCondor ID %s' % (test_script_file_name.split('/')[-1], condor_id))
        else:
            self.logger.error('Error submitting %s:\nSTDOUT: %s\nSTDERR: %s', test_script_file_name.split('/')[-1], stdout, stderr)
            return

        storage_dict = self.storage.get(prepid)
        if not storage_dict:
            storage_dict = {'stage': 1,
                            'running': {},
                            'done': {}}

        threads_str = '%s' % (threads)
        running_dict = storage_dict.get('running', {})
        cores_dict = running_dict.get(threads_str, {})
        cores_dict['condor_id'] = condor_id
        cores_dict['attempt_number'] = cores_dict.get('attempt_number', 0) + 1
        self.logger.info('Submitted %s %s threads attempt number %s',
                         prepid,
                         threads,
                         cores_dict['attempt_number'])
        if 'condor_status' in cores_dict:
            del cores_dict['condor_status']

        cores_dict['expected'] = expected_dict
        storage_dict['running'][threads_str] = cores_dict
        self.storage.save(prepid, storage_dict)

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
        Do not scale on lower number of cores
        Scale on higher number of cores
        Limit per core 500mb - 4gb
        """
        prepid = request.get_attribute('prepid')
        sequences = request.get_attribute('sequences')
        request_memory = request.get_attribute('memory')
        request_threads = max((int(sequence.get('nThreads', 1)) for sequence in sequences))
        if target_threads <= request_threads:
            # Memory provided by user
            memory = request_memory
            self.logger.info('%s will use use %sMB for %s thread validation', prepid, memory, target_threads)
            return memory

        if request_threads == 1 and request_memory == 2300:
            single_core_memory = 2000
        else:
            single_core_memory = int(request_memory / request_threads)
            single_core_memory = max(single_core_memory, 2000)

        # Min 500, max 4000
        single_core_memory = max(500, min(4000, single_core_memory))
        memory = target_threads * single_core_memory
        self.logger.info('%s has %s nThreads and %sMB memory. Single core memory %sMB, so will use %sMB for %s thread validation',
                         prepid,
                         request_threads,
                         request_memory,
                         single_core_memory,
                         memory,
                         target_threads)
        return memory


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='[%(asctime)s][%(levelname)s] %(message)s',
                        datefmt='%Y-%b-%d:%H:%M:%S')
    logging.info('Starting...')
    ValidationControl().run()
    logging.info('Done')
