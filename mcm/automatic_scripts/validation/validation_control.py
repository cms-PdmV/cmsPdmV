import logging
import json
import sys
import os.path
import xml.etree.ElementTree as ET
from math import ceil, sqrt
from xml.parsers.expat import ExpatError
from xml.etree.ElementTree import ParseError
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
    Validation control handles submission of new and checking of already running validations
    as well as checking reported values
    """

    def __init__(self):
        self.request_db = database('requests')
        self.chained_request_db = database('chained_requests')
        self.ssh_executor = SSHExecutor(settings.get_value('node_for_test'),
                                        '/home/pdmvserv/private/credentials_json.txt')
        self.storage = ValidationStorage()
        self.logger = logging.getLogger()
        locator = Locator('validation/tests', care_on_existing=False)
        self.test_directory_path = locator.location()
        self.logger.info('Location %s' % (self.test_directory_path))
        self.max_attempts = 3

    def run(self):
        # Get status of validations in HTCondor
        condor_jobs = self.get_jobs_in_condor()
        # Update local storage accordingly
        self.update_running_jobs(condor_jobs)
        # Check if any of validations are done and if yes, process them
        self.process_done_validations()
        # Move validations to next stages if they are done
        self.move_validations_to_next_stage()
        # Get requests and chained requests that will be submitted to new validation
        items_to_submit = self.get_items_to_be_submitted()
        # Submit new items to validation
        self.submit_items(items_to_submit)

    def json_dumps(self, obj):
        return json.dumps(obj, indent=2, sort_keys=True)

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

        self.logger.info('Job status in HTCondor:%s', self.json_dumps(jobs_dict))
        return jobs_dict

    def get_items_to_be_submitted(self):
        """
        Take list of requests - list A
        Take list of chained requests -list B, and expand it to list of requests in that chained request - list C
        Remove requests from list A if they are in list C, i.e. do not validate separate requests if
        they are going to be validated together with a chain
        Take list of requests that already had validation submitted to condor - list D
        Add lists A and B together and remove already submitted items - list D
        """
        request_query = self.request_db.construct_lucene_query({'status': 'new',
                                                                'approval': 'validation'})
        requests = self.request_db.full_text_search('search', request_query, page=-1)
        requests = set(x['prepid'] for x in requests)

        chained_request_query = self.chained_request_db.construct_lucene_query({'validate<int>': '1'})
        chained_requests = self.chained_request_db.full_text_search('search', chained_request_query, page=-1)

        for chained_request in chained_requests:
            for request in chained_request['chain']:
                if request in requests:
                    self.logger.info('Removing %s from requests because it is in %s',
                                     request,
                                     chained_request['prepid'])
                    requests.remove(request)

        chained_requests = set(x['prepid'] for x in chained_requests)
        already_submitted = set(self.storage.get_all().keys())
        self.logger.info('Already submitted validations:\n%s', '\n'.join(already_submitted))
        to_be_submitted = list((chained_requests | requests) - already_submitted)

        self.logger.warning('Will keep only MultiValidation campaigns!')
        to_be_submitted = [x for x in to_be_submitted if 'multivalidation' in x.lower()]

        self.logger.info('New validations to be submitted:\n%s', '\n'.join(to_be_submitted))
        return to_be_submitted

    def update_running_jobs(self, condor_jobs):
        """
        Update HTCondor job status in local storage
        """
        self.logger.info('Will update job info in the local storage')
        all_items = self.storage.get_all()
        for validation_name, storage_item in all_items.items():
            self.logger.info('Updating %s information in local storage', validation_name)
            running = storage_item['running']
            for threads, threads_dict in running.items():
                if threads_dict.get('condor_status') == 'DONE':
                    continue

                condor_id = str(threads_dict['condor_id'])
                current_status = threads_dict.get('condor_status', '<unknown>')
                new_status = condor_jobs.get(condor_id, 'DONE')
                if current_status != new_status:
                    threads_dict['condor_status'] = new_status
                    self.logger.info('%s %s threads job changed to %s',
                                     validation_name,
                                     threads,
                                     new_status)
                    self.storage.save(validation_name, storage_item)

        self.logger.info('Updated local storage:')
        all_items = self.storage.get_all()
        for validation_name, storage_item in all_items.items():
            stage = storage_item['stage']
            self.logger.info('  %s is at stage %s:', validation_name, stage)
            running = storage_item['running']
            for threads in list(sorted(running.keys())):
                threads_dict = running[threads]
                self.logger.info('    Threads: %s, attempt: %s, status: %s, HTCondor ID: %s',
                                 threads,
                                 threads_dict.get('attempt_number'),
                                 threads_dict.get('condor_status'),
                                 threads_dict.get('condor_id'))

    def process_done_validations(self):
        """
        Iterate through all jobs in storage and check if they
        are done - all HTCondor jobs are DONE
        """
        self.logger.info('Will check if any validations changed to DONE')
        for validation_name, storage_item in self.storage.get_all().items():
            stage = storage_item['stage']
            self.logger.info('Checking %s at stage %s', validation_name, stage)
            running = storage_item['running']
            for threads in list(sorted(running.keys())):
                threads_dict = running[threads]
                status = threads_dict.get('condor_status')
                self.logger.info('%s thread validation is %s', threads, status)
                if status == 'DONE':
                    should_continue = self.process_done_validation(validation_name, threads)
                    if not should_continue:
                        break

    def get_reports(self, validation_name, threads, expected):
        reports = {}
        for request_prepid, expected_dict in expected.items():
            report_path = '%s%s/%s_%s_threads_report.xml' % (self.test_directory_path,
                                                             validation_name,
                                                             request_prepid,
                                                             threads)
            expected_events = expected_dict['events']
            report = self.parse_job_report(report_path, threads, expected_events)
            if not report:
                return None

            reports[request_prepid] = report

        return reports

    def check_time_per_event(self, request_name, expected, report):
        expected_time_per_event = expected['time_per_event']
        actual_time_per_event = report['time_per_event']
        time_per_event_margin = settings.get_value('timing_fraction')
        lower_threshold = expected_time_per_event * (1 - time_per_event_margin)
        upper_threshold = expected_time_per_event * (1 + time_per_event_margin)
        message = '%s expected %.4fs +- %.2f%% (%.4fs - %.4fs) time per event, measured %.4fs' % (request_name,
                                                                                                  expected_time_per_event,
                                                                                                  time_per_event_margin * 100,
                                                                                                  lower_threshold,
                                                                                                  upper_threshold,
                                                                                                  actual_time_per_event)
        self.logger.info(message)
        if lower_threshold <= actual_time_per_event <= upper_threshold:
            return True, ''

        self.logger.error('Time per event %.4fs not within expected range %.4fs - %.4fs',
                          actual_time_per_event,
                          lower_threshold,
                          upper_threshold)
        return False, message

    def check_size_per_event(self, request_name, expected, report):
        expected_size_per_event = expected['size_per_event']
        actual_size_per_event = report['size_per_event']
        size_per_event_margin = 0.1
        lower_threshold = expected_size_per_event * (1 - size_per_event_margin)
        upper_threshold = expected_size_per_event * (1 + size_per_event_margin)
        message = '%s expected %.4fkB +- %.2f%% (%.4fkB - %.4fkB) size per event, measured %.4fkB' % (request_name,
                                                                                                      expected_size_per_event,
                                                                                                      size_per_event_margin * 100,
                                                                                                      lower_threshold,
                                                                                                      upper_threshold,
                                                                                                      actual_size_per_event)
        self.logger.info(message)
        if lower_threshold <= actual_size_per_event <= upper_threshold:
            return True, ''

        self.logger.error('Size per event %.4fkB not within expected range %.4fkB - %.4fkB',
                          actual_size_per_event,
                          lower_threshold,
                          upper_threshold)
        return False, message

    def check_memory(self, request_name, expected, report):
        expected_memory = expected['memory']
        actual_memory = report['peak_value_rss']
        message = '%s expected up to %sMB memory, measured %sMB' % (request_name,
                                                                    expected_memory,
                                                                    actual_memory)
        self.logger.info(message)
        if actual_memory < expected_memory:
            return True, ''

        message += '. Peak memory %sMB is above expected %sMB by %sMB' % (actual_memory,
                                                                          expected_memory,
                                                                          actual_memory - expected_memory)

        return False, message

    def check_filter_efficiency(self, request_name, expected, report):
        expected_filter_efficiency = expected['filter_efficiency']
        actual_filter_efficiency = report['filter_efficiency']
        sigma = sqrt((actual_filter_efficiency * (1 - actual_filter_efficiency)) / expected['events'])
        sigma = max(sigma, 0.05 * actual_filter_efficiency)
        lower_threshold = expected_filter_efficiency - 3 * sigma
        upper_threshold = expected_filter_efficiency + 3 * sigma
        message = '%s expected %.4f%% +- %.4f%% (%.4f%% - %.4f%%) filter efficiency, measured %.4f%%' % (request_name,
                                                                                                         expected_filter_efficiency * 100,
                                                                                                         3 * sigma * 100,
                                                                                                         lower_threshold * 100,
                                                                                                         upper_threshold * 100,
                                                                                                         actual_filter_efficiency * 100)
        self.logger.info(message)
        if lower_threshold <= actual_filter_efficiency <= upper_threshold:
            return True, ''

        self.logger.error('Filter efficiency %.4f%% not within expected range %.4f%% - %.4f%%',
                          actual_filter_efficiency * 100,
                          lower_threshold * 100,
                          upper_threshold * 100)

        return False, message

    def adjust_time_per_event(self, request_name, expected, report):
        expected_time_per_event = expected['time_per_event']
        actual_time_per_event = report['time_per_event']
        request = self.request_db.get(request_name)
        number_of_sequences = len(request.get('sequences', []))
        adjusted_time_per_event = ((expected_time_per_event + 3 * actual_time_per_event) / 4) / number_of_sequences
        request['time_event'] = [adjusted_time_per_event] * number_of_sequences
        self.logger.info('%s expected %.4fs time per event, measured %.4fs, adjusting to %.4fs * %s sequences = %.4fs',
                         request_name,
                         expected_time_per_event,
                         actual_time_per_event,
                         adjusted_time_per_event,
                         number_of_sequences,
                         adjusted_time_per_event * number_of_sequences)
        self.request_db.save(request)
        return adjusted_time_per_event, number_of_sequences

    def adjust_size_per_event(self, request_name, expected, report):
        expected_size_per_event = expected['size_per_event']
        actual_size_per_event = report['size_per_event']
        request = self.request_db.get(request_name)
        number_of_sequences = len(request.get('sequences', []))
        adjusted_size_per_event = ((expected_size_per_event + 3 * actual_size_per_event) / 4) / number_of_sequences
        request['size_event'] = [adjusted_size_per_event] * number_of_sequences
        self.logger.info('%s expected %.4fkB size per event, measured %.4fkB, adjusting to %.4fkB * %s sequences = %.4fkB',
                         request_name,
                         expected_size_per_event,
                         actual_size_per_event,
                         adjusted_size_per_event,
                         number_of_sequences,
                         adjusted_size_per_event * number_of_sequences)
        self.request_db.save(request)
        return adjusted_size_per_event, number_of_sequences

    def read_output_files(self, validation_name, threads):
        item_directory = '%s%s' % (self.test_directory_path, validation_name)
        log_file_name = '%s/%s_threads.log' % (item_directory, threads)
        out_file_name = '%s/%s_threads.out' % (item_directory, threads)
        err_file_name = '%s/%s_threads.err' % (item_directory, threads)
        self.logger.info('Log file: %s', log_file_name)
        self.logger.info('Out file: %s', out_file_name)
        self.logger.info('Err file: %s', err_file_name)

        if not os.path.isfile(log_file_name):
            log_file = []
            self.logger.info('Log file does not exist')
        else:
            with open(log_file_name) as open_file:
                log_file = open_file.readlines()

        if not os.path.isfile(out_file_name):
            out_file = []
            self.logger.info('Out file does not exist')
        else:
            with open(out_file_name) as open_file:
                out_file = open_file.readlines()

        if not os.path.isfile(err_file_name):
            err_file = []
            self.logger.info('Err file does not exist')
        else:
            with open(err_file_name) as open_file:
                err_file = open_file.readlines()

        start_line = -1
        end_line = -1
        for index, line in enumerate(err_file):
            if 'Begin processing the' in line:
                if start_line == -1:
                    start_line = index + 1

                end_line = index

        if start_line > 0 and end_line > 0 and end_line > start_line:
            del err_file[start_line:end_line]
            err_file.insert(start_line, '...\n')

        return log_file, out_file, err_file

    def removed_due_to_exceeded_walltime(self, log_file):
        if not log_file:
            return False

        text = 'Job removed by SYSTEM_PERIODIC_REMOVE due to wall time exceeded allowed max'
        for line in log_file:
            if text in line:
                return True

        return False

    def validation_exit_code(self, log_file):
        if not log_file:
            return 0

        for line in reversed(log_file):
            if 'return value' in line:
                split_line = line.split('return value')
                split_line = split_line[1]
                code = ''
                for character in split_line:
                    if character in '0123456789':
                        code += character

                return int(code)

        return 0

    def check_events_ran(self, validation_name, expected, report):
        min_events = settings.get_value('timing_n_limit')
        passed_events = report['total_events']
        if passed_events >= min_events:
            self.logger.info('At least %s events are required and %s events were produced',
                             min_events,
                             passed_events)
            return True, ''

        message = 'At least %s events are required to do an accurate time per event estimation, but only %s events were produced.\n' % (min_events, passed_events)
        self.logger.error(message)
        return False, message

    def process_done_validation(self, validation_name, threads):
        """
        Parse reports, fail, resubmit or proceed validation to next step
        """
        self.logger.info('Processing done %s %s thread validation', validation_name, threads)
        storage_item = self.storage.get(validation_name)
        running = storage_item['running']
        cmssw_versions_of_succeeded = []
        threads_int = int(threads)
        threads_dict = running[threads]
        # Check log output
        log_file, out_file, err_file = self.read_output_files(validation_name, threads)
        if self.removed_due_to_exceeded_walltime(log_file):
            self.logger.error('Job was removed due to exceeded walltime')
            self.validation_failed(validation_name)
            self.notify_validation_failed(validation_name,
                                          'Validation job was removed due to exceeded walltime. '
                                          'This usually indicates that time per event is too small and should be increased.\n'
                                          'Job output:\n\n%s\n\n'
                                          'Job error stream output:\n\n%s\n\n'
                                          'Job log output:\n\n%s' % (''.join(out_file),
                                                                     ''.join(err_file),
                                                                     ''.join(log_file)))
            return False

        exit_code = self.validation_exit_code(log_file)
        self.logger.info('Validation exit code: %s', exit_code)
        if exit_code != 0:
            self.logger.error('Validation failed because it exited with code %s', exit_code)
            self.validation_failed(validation_name)
            self.notify_validation_failed(validation_name,
                                          'Validation job exited with code %s.\n'
                                          'Job output:\n\n%s\n\n'
                                          'Job error stream output:\n\n%s\n\n'
                                          'Job log output:\n\n%s' % (exit_code,
                                                                     ''.join(out_file),
                                                                     ''.join(err_file),
                                                                     ''.join(log_file)))
            return False

        # Get reports
        reports = self.get_reports(validation_name, threads_int, threads_dict['expected'])
        if not reports:
            self.logger.error('Reports are missing for %s %s thread validation', validation_name, threads)
            self.validation_failed(validation_name)
            self.notify_validation_failed(validation_name,
                                          'Job reports - XML files are missing for %s.\n'
                                          'Job output:\n\n%s\n\n'
                                          'Job error stream output:\n\n%s\n\n'
                                          'Job log output:\n\n%s' % (validation_name,
                                                                     ''.join(out_file),
                                                                     ''.join(err_file),
                                                                     ''.join(log_file)))


            return False

        self.logger.info('Reports include these requests:\n%s', '\n'.join(reports.keys()))
        if threads_int != 1:
            self.logger.info('Validation was done for %s threads, not checking the values', threads)
            for request_name, report in reports.items():
                expected_dict = threads_dict['expected'][request_name]
                self.logger.debug('%s expected:\n%s\n%s measured:\n%s',
                                  request_name,
                                  self.json_dumps(expected_dict),
                                  request_name,
                                  self.json_dumps(report))
        else:
            attempt_number = threads_dict['attempt_number']
            self.logger.info('This was attempt number %s for %s thread validation', attempt_number, threads)
            for request_name, report in reports.items():
                # Check report only for single core validation
                expected_dict = threads_dict['expected'][request_name]
                self.logger.info('Checking %s report', request_name)
                self.logger.info('Expected:\n%s\nMeasured:\n%s',
                                 self.json_dumps(expected_dict),
                                 self.json_dumps(report))

                passed, message = self.check_events_ran(request_name, expected_dict, report)
                if not passed:
                    self.validation_failed(validation_name)
                    message += ('Either time per event is too big or validation duration is not long enough. '
                                'Please adjust time per event or run a longer validation.')
                    self.notify_validation_failed(validation_name, message)
                    return False

                # Check time per event
                passed, message = self.check_time_per_event(request_name, expected_dict, report)
                if not passed:
                    if attempt_number < self.max_attempts:
                        adjusted_time_per_event, number_of_sequences = self.adjust_time_per_event(request_name, expected_dict, report)
                        message += '\nTime per event is adjusted to %.4fs per sequence. %.4fs * %s sequences = %.4fs\nValidation will be automatically retried' % (adjusted_time_per_event,
                                                                                                                                                                   adjusted_time_per_event,
                                                                                                                                                                   number_of_sequences,
                                                                                                                                                                   adjusted_time_per_event * number_of_sequences)
                        self.submit_item(validation_name, threads_int)
                        self.notify_validation_failed(validation_name, message)
                        return True
                    else:
                        self.validation_failed(validation_name)
                        message += '\nValidation failed %s attempts out of allowed %s.\nValidation will NOT be automatically retried.' % (attempt_number, self.max_attempts)
                        self.notify_validation_failed(validation_name, message)
                        return False

                # Check size per event
                passed, message = self.check_size_per_event(request_name, expected_dict, report)
                if not passed:
                    if attempt_number < self.max_attempts:
                        adjusted_size_per_event, number_of_sequences = self.adjust_size_per_event(request_name, expected_dict, report)
                        message += '\nSize per event is adjusted to %.4fkB per sequence. %.4fkB * %s sequences = %.4fkB\nValidation will be automatically retried' % (adjusted_size_per_event,
                                                                                                                                                                      adjusted_size_per_event,
                                                                                                                                                                      number_of_sequences,
                                                                                                                                                                      adjusted_size_per_event * number_of_sequences)
                        self.submit_item(validation_name, threads_int)
                        self.notify_validation_failed(validation_name, message)
                        return True
                    else:
                        self.validation_failed(validation_name)
                        message += '\nValidation failed %s attempts out of allowed %s.\nValidation will NOT be automatically retried.' % (attempt_number, self.max_attempts)
                        self.notify_validation_failed(validation_name, message)
                        return False

                # Check memory usage
                passed, message = self.check_memory(request_name, expected_dict, report)
                if not passed:
                    self.validation_failed(validation_name)
                    message += '\nPlease check and adjust memory and retry validation.'
                    self.notify_validation_failed(validation_name, message)
                    return False

                # Check filter efficiency
                passed, message = self.check_filter_efficiency(request_name, expected_dict, report)
                if not passed:
                    self.validation_failed(validation_name)
                    message += '\nPlease check and adjust generator filter parameter and retry validation.'
                    self.notify_validation_failed(validation_name, message)
                    return False

                self.logger.info('Success for %s in %s thread validation',
                                 request_name,
                                 threads)

        self.logger.info('Success for %s %s thread validation', validation_name, threads)
        # If there was no break in the loop - nothing was resubmitted
        del running[threads]
        storage_item['done'][threads] = reports
        self.storage.save(validation_name, storage_item)
        return True

    def notify_validation_failed(self, validation_name, message):
        if '-chain_' in validation_name:
            item = self.chained_request_db.get(validation_name)
            item = ChainedRequest(item)
        else:
            item = self.request_db.get(validation_name)
            item = Request(item)

        subject = 'Validation failed for %s' % (validation_name)
        message = 'Hello,\n\nUnfortunatelly %s validation failed.\n%s' % (validation_name, message)
        item.notify(subject, message)

    def notify_validation_suceeded(self, validation_name):
        if '-chain_' in validation_name:
            item = self.chained_request_db.get(validation_name)
            item = ChainedRequest(item)
        else:
            item = self.request_db.get(validation_name)
            item = Request(item)

        subject = 'Validation succeeded for %s' % (validation_name)
        message = 'Hello,\n\nValidation of %s succeeded.\nMeasured values:\n' % (validation_name)
        storage_item = self.storage.get(validation_name)['done']
        for threads in sorted(storage_item.keys()):
            threads_dict = storage_item[threads]
            message += '\nThreads: %s\n' % (threads)
            for request in sorted(threads_dict.keys()):
                request_dict = threads_dict[request]
                message += '  %s\n' % (request)
                for key in sorted(request_dict.keys()):
                    value = request_dict[key]
                    message += '    %s: %s\n' % (key, value)

        item.notify(subject, message)

    def move_validations_to_next_stage(self):
        all_items = self.storage.get_all()
        for validation_name, storage_item in all_items.items():
            stage = storage_item['stage']
            running = storage_item['running']
            self.logger.info('%s is at stage %s and has %s validations in running',
                             validation_name,
                             stage,
                             len(running))
            if running:
                self.logger.info('Will not proceed to next stage because there are runnig validations')
                continue

            stage += 1
            self.logger.info('Will proceed to stage %s', stage)
            # Proceed to next stage
            storage_item['stage'] = stage
            self.storage.save(validation_name, storage_item)
            if stage == 2 and self.can_run_multicore_validations(validation_name):
                self.submit_item(validation_name, 2)
                self.submit_item(validation_name, 4)
                self.submit_item(validation_name, 8)
            else:
                self.validation_succeeded(validation_name)

    def can_run_multicore_validations(self, validation_name):
        # Do not submit multicore jobs for < CMSSW 7.4
        requests = self.requests_for_validation(validation_name)
        list_of_cmssw = [x.get_attribute('cmssw_release') for x in requests]
        if not list_of_cmssw:
            return True

        list_of_cmssw = [x.replace('CMSSW_', '').split('_')[0:3] for x in list_of_cmssw]
        list_of_cmssw = sorted(list_of_cmssw, key=lambda x: tuple(x))
        self.logger.info('CMSSW versions of %s: %s', validation_name, ', '.join(['_'.join(x) for x in list_of_cmssw]))
        lowest_version = list_of_cmssw[0]
        return lowest_version[0] > 7 or (lowest_version[0] == 7 and lowest_version[1] > 3)

    def validation_failed(self, validation_name):
        if '-chain_' in validation_name:
            chained_req = self.chained_request_db.get(validation_name)
            chained_req['validate'] = 0
            self.chained_request_db.save(chained_req)
            requests = self.get_requests_from_chained_request(ChainedRequest(chained_req))
            requests = [r.json() for r in requests]
        else:
            request = self.request_db.get(validation_name)
            requests = [request]

        for request in requests:
            request['validation']['results'] = {}
            request['approval'] = 'none'
            request['status'] = 'new'
            self.logger.warning('Saving %s', request['prepid'])
            self.request_db.save(request)

        self.storage.delete(validation_name)
        self.logger.info('Validation failed for %s', validation_name)

    def validation_succeeded(self, validation_name):
        if '-chain_' in validation_name:
            chained_req = self.chained_request_db.get(validation_name)
            chained_req['validate'] = 0
            self.chained_request_db.save(chained_req)
        else:
            request = self.request_db.get(validation_name)

        requests = {}
        request_dict = self.storage.get(validation_name)
        for core_number in request_dict['done'].keys():
            for request_prepid in request_dict['done'][core_number].keys():
                if request_prepid not in requests:
                    requests[request_prepid] = self.request_db.get(request_prepid)
                    requests[request_prepid]['validation']['results'] = {}

                request = requests[request_prepid]
                request['approval'] = 'validation'
                request['status'] = 'validation'
                request['validation']['results'][core_number] = request_dict['done'][core_number][request_prepid]

        for _, request in requests.items():
            self.logger.warning('Saving %s', request['prepid'])
            self.request_db.save(request)

        self.notify_validation_suceeded(validation_name)
        self.storage.delete(validation_name)
        self.logger.info('Validation succeeded for %s', validation_name)

    def parse_job_report(self, report_path, threads, expected_events):
        report_file_name = report_path.split('/')[-1]

        if not os.path.isfile(report_path):
            return None

        try:
            tree = ET.parse(report_path)
        except ExpatError:
            # Invalid XML file
            return None
        except ParseError as err:
            self.logger.error('Error parsing XML: %s', err)
            # Empty or invalid XML file
            return None

        root = tree.getroot()
        total_events = root.findall('.//TotalEvents')
        if total_events is not None:
            total_events = int(total_events[-1].text)
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

        self.logger.debug('%s values:', report_file_name)
        self.logger.debug('  event_throughput %s', event_throughput)
        self.logger.debug('  peak_value_rss %s', peak_value_rss)
        self.logger.debug('  total_size %s', total_size)
        self.logger.debug('  total_job_cpu %s', total_job_cpu)
        self.logger.debug('  total_job_time %s', total_job_time)
        self.logger.debug('  total_events %s', total_events)
        if None in (event_throughput, peak_value_rss, total_size, total_job_cpu, total_job_time, total_events):
            self.logger.error('Not all values are in %s, aborting %s with %s threads', report_file_name, prepid, threads)
            return {'all_values_present': False}

        time_per_event = 1.0 / event_throughput
        size_per_event = total_size / total_events
        cpu_efficiency = total_job_cpu / (threads * total_job_time)
        filter_efficiency = float(total_events) / expected_events
        return {'time_per_event': time_per_event,
                'size_per_event': size_per_event,
                'cpu_efficiency': cpu_efficiency,
                'filter_efficiency': filter_efficiency,
                'peak_value_rss': peak_value_rss,
                'total_events': total_events}

    def get_htcondor_submission_file(self, validation_name, job_length, threads, memory, output_prepids):
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
                       'executable            = %s_%s_threads.sh' % (validation_name, threads),
                       'output                = %s_threads.out' % (threads),
                       'error                 = %s_threads.err' % (threads),
                       'log                   = %s_threads.log' % (threads),
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
        """
        Submit given item validation for 1 thread
        """
        for validation_name in items:
            # Prepare empty directory for validation
            item_directory = '%s%s' % (self.test_directory_path, validation_name)
            command = ['rm -rf %s' % (item_directory),
                       'mkdir -p %s' % (item_directory)]
            _, _ = self.ssh_executor.execute_command(command)
            self.submit_item(validation_name, 1)

    def requests_for_validation(self, validation_name):
        if '-chain_' in validation_name:
            chained_request = ChainedRequest(self.chained_request_db.get(validation_name))
            requests = self.get_requests_from_chained_request(chained_request)
        else:
            request = Request(self.request_db.get(validation_name))
            requests = [request]

        return requests

    def submit_item(self, validation_name, threads):
        validation_directory = '%s%s' % (self.test_directory_path, validation_name)
        # Get list of requests that will run in this validation
        # Single request validation will have only that list
        # Chained request validation might have multiple requests in sequence
        self.logger.info('Submitting %s validation with %s threads', validation_name, threads)
        requests = self.requests_for_validation(validation_name)
        expected_dict = {}
        validation_runtime = 0
        max_memory = 0
        validation_script = ''
        request_prepids = []
        for request in requests:
            # Max job runtime
            request_prepid = request.get_attribute('prepid')
            request_prepids.append(request_prepid)
            # Sum all run times
            validation_runtime += int(request.get_validation_max_runtime())
            # Get max memory of all requests
            request_memory = self.get_memory(request, threads)
            max_memory = max(max_memory, request_memory)
            # Combine validation scripts to one long script
            validation_script += request.get_setup_file2(for_validation=True,
                                                         automatic_validation=True,
                                                         threads=threads)
            validation_script += '\n'
            expected_dict[request_prepid] = {'time_per_event': request.get_sum_time_events(),
                                             'size_per_event': request.get_sum_size_events(),
                                             'memory': request_memory,
                                             'filter_efficiency': request.get_efficiency(),
                                             'events': request.get_event_count_for_validation()}

        self.logger.info('%s %s thread validation info:', validation_name, threads)
        self.logger.info('PrepIDs: %s', ', '.join(request_prepids))
        self.logger.info('Validation runtime: %s', validation_runtime)
        self.logger.info('Validation memory: %s', max_memory)
        # Make a HTCondor .sub file
        condor_file = self.get_htcondor_submission_file(validation_name, validation_runtime, threads, max_memory, request_prepids)

        # Write files straight to afs
        condor_file_name = '%s/%s_threads.sub' % (validation_directory, threads)
        with open(condor_file_name, 'w') as f:
            f.write(condor_file)

        validation_script_file_name = '%s/%s_%s_threads.sh' % (validation_directory, validation_name, threads)
        with open(validation_script_file_name, 'w') as f:
            f.write(validation_script)

        # Condor submit
        command = ['cd %s' % (validation_directory),
                   'voms-proxy-init --voms cms --out $(pwd)/voms_proxy.txt --hours 48',
                   'chmod +x %s' % (validation_script_file_name.split('/')[-1]),
                   'module load lxbatch/tzero',
                   'condor_submit %s' % (condor_file_name.split('/')[-1])]
        stdout, stderr = self.ssh_executor.execute_command(command)

        # Get condor job ID from std output
        if not stderr and '1 job(s) submitted to cluster' in stdout:
            # output is "1 job(s) submitted to cluster xxxxxx"
            condor_id = int(float(stdout.split()[-1]))
            self.logger.info('Submitted %s, HTCondor ID %s',
                             validation_script_file_name.split('/')[-1],
                             condor_id)
        else:
            self.logger.error('Error submitting %s:\nSTDOUT: %s\nSTDERR: %s',
                              validation_script_file_name.split('/')[-1],
                              stdout, stderr)
            return

        storage_dict = self.storage.get(validation_name)
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
                         validation_name,
                         threads,
                         cores_dict['attempt_number'])
        if 'condor_status' in cores_dict:
            del cores_dict['condor_status']

        cores_dict['expected'] = expected_dict
        storage_dict['running'][threads_str] = cores_dict
        self.storage.save(validation_name, storage_dict)

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
    logging.basicConfig(level=logging.DEBUG,
                        format='[%(asctime)s][%(levelname)s] %(message)s',
                        datefmt='%Y-%b-%d:%H:%M:%S')
    logging.info('Starting...')
    control = ValidationControl()
    control.run()
    logging.info('Done')
