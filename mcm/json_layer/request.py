from asyncio.log import logger
import os
import re
import hashlib
import copy
import time
import logging
import math
import random
import json
from math import sqrt
from operator import itemgetter

from couchdb_layer.mcm_database import database as Database
from json_layer.invalidation import Invalidation
from json_layer.json_base import json_base
from json_layer.campaign import Campaign
from json_layer.flow import Flow
from json_layer.batch import Batch
from json_layer.generator_parameters import generator_parameters
from json_layer.sequence import Sequence
from tools.ssh_executor import SSHExecutor
from tools.locator import locator
from tools.installer import installer
from tools.settings import Settings
from tools.locker import locker
from tools.logger import InjectionLogAdapter
from tools.utils import get_scram_arch as fetch_scram_arch
from tools.connection_wrapper import ConnectionWrapper
from json_layer.user import User, Role


class AFSPermissionError(Exception):
    def __init__(self, message=None):
        self.message = message

    def __str__(self):
        return 'AFS permission error: %s' % (self.message)


class Request(json_base):
    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'approval': 'none',
        'cmssw_release': '',
        'completed_events': -1,
        'config_id': [],
        'dataset_name': '',
        'energy': 0.0,
        'events_per_lumi': 0,
        'extension': 0,
        'flown_with': '',
        'fragment': '',
        'fragment_tag': '',
        'generator_parameters': [],
        'generators': [],
        'history': [],
        'input_dataset': '',
        'interested_pwg': [],
        'keep_output': [],  # list of booleans
        'mcdb_id': -1,
        'member_of_campaign': '',
        'member_of_chain': [],
        'memory': 2000,
        'name_of_fragment': '',
        'notes': '',
        'output_dataset': [],
        'pileup_dataset_name': '',
        'pilot': False,
        'priority': 20000,
        'process_string': '',
        'pwg': '',
        'reqmgr_name': [],
        'sequences': [],
        'size_event': [-1.0],
        'status': 'new',
        'tags': [],
        'time_event': [-1.0],
        'total_events': -1,
        'type': '',
        'validation': {"valid":False, "content":"all"},
        'version': 0,
    }

    # approval-status order
    order = ['none-new',
             'validation-new',
             'validation-validation',
             'define-defined',
             'approve-approved',
             'submit-approved',
             'submit-submitted',
             'submit-done']

    @classmethod
    def get_database(cls):
        """
        Return shared database instance
        """
        if not hasattr(cls, 'database'):
            cls.database = Database('requests')

        return cls.database

    def get_editing_info(self):
        info = super().get_editing_info()
        approval_status = self.get_approval_status()
        if approval_status in {'validation-new', 'submit-approved'}:
            return info

        user = User()
        user_role = user.get_role()
        is_admin = user_role >= Role.ADMINISTRATOR
        is_prod_expert = user_role >= Role.PRODUCTION_EXPERT
        is_prod_manager = user_role >= Role.PRODUCTION_MANAGER
        is_gen_convener = user_role >= Role.GEN_CONVENER
        is_mc_contact = user_role >= Role.MC_CONTACT
        is_user = user_role >= Role.USER
        # Some are always editable
        info['notes'] = is_user
        info['tags'] = is_user
        info['interested_pwg'] = is_user
        # Depending on status
        if approval_status == 'none-new':
            info['cmssw_release'] = is_prod_expert
            info['dataset_name'] = is_mc_contact and not self.get('flown_with')
            info['energy'] = is_mc_contact
            info['extension'] = is_mc_contact
            info['fragment'] = is_mc_contact
            info['fragment_tag'] = is_mc_contact
            info['generator_parameters'] = is_mc_contact
            info['generators'] = is_mc_contact
            info['input_dataset'] = is_mc_contact
            info['keep_output'] = is_mc_contact
            info['mcdb_id'] = is_mc_contact
            info['memory'] = is_prod_manager
            info['name_of_fragment'] = is_mc_contact
            info['pilot'] = is_mc_contact
            info['priority'] = is_prod_manager
            info['process_string'] = is_prod_manager
            info['sequences'] = is_prod_manager
            info['size_event'] = is_mc_contact
            info['time_event'] = is_mc_contact
            info['total_events'] = is_mc_contact
            info['size_event'] = is_mc_contact
            info['time_event'] = is_mc_contact
            info['validation'] = is_mc_contact
        elif approval_status == 'defined-defined':
            info['dataset_name'] = is_prod_manager
            info['total_events'] = is_prod_manager
            info['keep_output'] = is_prod_expert
            info['pilot'] = is_prod_manager
            info['extension'] = is_prod_manager
            info['input_dataset'] = is_prod_expert
            info['time_event'] = is_prod_expert
            info['size_event'] = is_prod_expert
            info['process_string'] = is_prod_manager
            info['priority'] = is_prod_manager
        elif approval_status == 'approve-approved':
            info['dataset_name'] = is_gen_convener

        return info

    def validate(self):
        """
        Check if all attributes of the object are valid
        """
        prepid = self.get_attribute('prepid')
        self.logger.info('Validating request %s', prepid)
        # Check if PWG is valid
        pwg = self.get_attribute('pwg')
        all_pwgs = Settings.get('pwg')
        if pwg not in all_pwgs:
            raise Exception('Invalid PWG - "%s"' % (pwg))

        # Check if interested PWGs are valid
        interested_pwgs = self.get_attribute('interested_pwg')
        if set(interested_pwgs) - set(all_pwgs):
            invalid_pwgs = sorted(list(set(interested_pwgs) - set(all_pwgs)))
            raise Exception('Invalid interested PWG: %s' % (', '.join(invalid_pwgs)))

        # Dataset name
        dataset_name = self.get_attribute('dataset_name')
        if dataset_name and not self.primary_dataset_regex(dataset_name):
            raise Exception('Dataset name "%s" does not match required format' % (dataset_name))

        # Events per lumi
        events_per_lumi = self.get_attribute('events_per_lumi')
        if events_per_lumi != 0 and not 100 <= events_per_lumi <= 1000:
            raise Exception('Events per lumi must be 100<=X<=1000 or 0 to use campaign value')

        # CMSSW release
        cmssw_release = self.get_attribute('cmssw_release')
        if not self.cmssw_regex(cmssw_release):
            raise Exception('Invalid CMSSW release name "%s"' % (cmssw_release))

        # Processing string check
        processing_string = self.get_attribute('process_string')
        if processing_string and not self.processing_string_regex(processing_string):
            raise Exception('Invalid processing string "%s"' % (processing_string))

        sequences = self.get_attribute('sequences')
        # Max number of cores:
        cores = max(s.get('nThreads', 1) for s in sequences)
        if not cores:
            raise Exception('Invalid number of nThreads in sequences')

        # Memory
        memory = self.get_attribute('memory')
        # Memory per core
        for seq in sequences:
            cores = seq.get('nThreads')
            cores = int(cores) if cores else 1
            memory_per_core = memory / cores
            if not (500 <= memory_per_core <= 4000):
                raise Exception('Allowed memory 500-4000MB/core, found %.1fMB' % (memory_per_core))

        # Number of time per event values:
        if len(self.get_attribute('time_event')) != len(sequences):
            raise Exception('Number of time per event values is different from number of sequences')

        # Number of size per event values:
        if len(self.get_attribute('size_event')) != len(sequences):
            raise Exception('Number of size per event values is different from number of sequences')

        # Number of keep output values:
        if len(self.get_attribute('keep_output')) != len(sequences):
            raise Exception('Number of keep output values is different from number of sequences')

    def keeps_output(self):
        """
        Return whether any sequence of request keeps output
        """
        return bool(list(filter(None, self.get('keep_output'))))

    def approve(self):
        """
        Approve request - move it to next status
        Statuses:
        - none-new              -> new
        - validation-new        -> validating
        - validation-validation -> validated
        - defined-defined       -> defined
        - approve-approved      -> approved
        - submit-approved       -> submitting
        - submit-submitted      -> submitted
        - submit-done           -> done
        """
        prepid = self.get_attribute('prepid')
        current_status = '%s-%s' % (self.get_attribute('approval'), self.get_attribute('status'))
        self.logger.info('Approving request "%s", current status "%s"', prepid, current_status)
        if current_status == 'none-new':
            # Need to check if this is root campaign or not, it root or possible
            # then move to validation, otherwise straight to approved
            campaign_db = Database('campaigns')
            campaign = campaign_db.get(self.get_attribute('member_of_campaign'))
            if campaign['root'] > 0:
                # Not root
                self.move_to_approved()
            else:
                # Root or possible root
                # Skip to validated if request is in validation bypass list
                self.move_to_validating()

        elif current_status == 'validation-new':
            # Move to validated, is allowed only for pdmvserv
            raise Exception('Request is being validated, approval is not allowed')
        elif current_status == 'validation-validation':
            # Move to defined
            self.move_to_defined()
        elif current_status == 'define-defined':
            # Last action of generator contacts
            self.move_to_approved()
        elif current_status == 'approve-approved':
            # Allowed only for generator contacts and explicitly listed people
            self.move_to_submitting()
        elif current_status == 'submit-approved':
            # Invalid action
            raise Exception('Request is being submitted, approval is not allowed')
        elif current_status == 'submit-submitted':
            # Check if request is done
            self.move_to_done()
        elif current_status == 'submit-done':
            # Cannot go further than done
            raise Exception('Request is already done, cannot move status further')
        else:
            self.logger.error('Unsupported request %s status "%s"', prepid, current_status)
            raise Exception('Unsupported request %s status "%s"' % (prepid, current_status))

    def get_chained_requests(self):
        """
        Return chained request dicts that this request is member of
        """
        chained_request_ids = self.get_attribute('member_of_chain')
        if not chained_request_ids:
            return []

        chained_request_db = Database('chained_requests')
        chained_requests = chained_request_db.bulk_get(chained_request_ids)
        return chained_requests

    def get_previous_request(self):
        """
        Return request that is input for the current request or None if it does
        not exist
        """
        chained_request_ids = self.get_attribute('member_of_chain')
        if not chained_request_ids:
            return None

        prepid = self.get_attribute('prepid')
        chained_request_db = Database('chained_requests')
        # Take first chained request as all of them should be identical
        chained_request = chained_request_db.get(chained_request_ids[0])
        index = chained_request['chain'].index(prepid)
        if index <= 0:
            return None

        previous_prepid = chained_request['chain'][index - 1]
        request_db = Database('requests')
        req = request_db.get(previous_prepid)
        self.logger.info('Previous request for %s is %s', prepid, previous_prepid)
        return req

    def set_approval_status(self, approval, status):
        """
        Set both approval and status of the request
        Update chained requests' "last_status" if needed
        """
        self.set_attribute('approval', approval)
        self.set_attribute('status', status)
        # When status is changed, udpdate it in all chained requests
        chained_requests = self.get_chained_requests()

        # No need to update to same satus
        chained_requests = [c for c in chained_requests if c['last_status'] != status]

        # Don't care where request is not current step
        prepid = self.get_attribute('prepid')
        chained_requests = [c for c in chained_requests if c['step'] == c['chain'].index(prepid)]

        if not chained_requests:
            return

        from json_layer.chained_request import ChainedRequest
        for chained_request_json in chained_requests:
            chained_request = ChainedRequest(chained_request_json)
            if chained_request.set_last_status(status):
                chained_request.save()

    def get_approval_status(self):
        """
        Return approval and status of a request
        """
        approval = self.get_attribute('approval')
        status = self.get_attribute('status')
        return '%s-%s' % (approval, status)

    def move_to_validating(self, for_chain=False):
        """
        Move request to validation-new ("validating") status
        """
        validation_halt = Settings.get('validation_stop')
        if validation_halt:
            raise Exception('Validation jobs are temporary stopped for upcoming McM restart')

        if not self.correct_types():
            raise TypeError('Wrong type of attribute(s)')

        if not self.get_scram_arch():
            raise Exception('SCRAM architecture is invalid, please double check the release')

        if not self.get_attribute('dataset_name'):
            raise Exception('Missing dataset name')

        # TODO: are generator parameters needed at all?
        gen_parameters = self.get_attribute('generator_parameters')
        if not gen_parameters or generator_parameters(gen_parameters[-1]).isInValid():
            raise Exception('The generator parameters are invalid: either none or negative or null '
                            'values, or efficiency larger than 1')

        gen_parameters[-1] = generator_parameters(gen_parameters[-1]).json()
        self.set_attribute('generator_parameters', gen_parameters)

        if not self.get_attribute('generators'):
            raise Exception('There should be at least one generator specified in the request')

        sequences = self.get_attribute('sequences')
        if not sequences:
            raise Exception('No sequences could be found in the request')

        if [t for t in self.get_attribute('time_event') if not t or t <= 0]:
            raise Exception('Invalid time per event - all values must be positive')

        if [s for s in self.get_attribute('size_event') if not s or s <= 0]:
            raise Exception('Invalid size per event - all values must be positive')

        mcdb_id = self.get_attribute('mcdb_id')
        if self.get_wmagent_type() == 'LHEStepZero' and mcdb_id <= 0:
            raise Exception('LHE requests should have a positive MCDB ID')

        if not for_chain:
            total_events = self.get_attribute('total_events')
            if total_events <= 0:
                raise Exception('Total events must be a positive number')

            fragment = self.get_attribute('fragment')
            fragment_name = self.get_attribute('name_of_fragment')
            input_dataset = self.get_attribute('input_dataset')
            if not fragment and not fragment_name and mcdb_id <= 0 and not input_dataset:
                # No fragment, no fragment name, no mcdb id and no input dataset
                raise Exception('No input: no fragment, no MCDB ID and no input dataset')

        # Do not allow to validate if there are collisions
        self.check_for_collisions()

        campaign_db = Database('campaigns')
        campaign = campaign_db.get(self.get_attribute('member_of_campaign'))
        # Check for changed number of sequences in campaign
        if len(sequences) != len(campaign['sequences']):
            raise Exception('Request has a different number of sequences '
                            'than the campaigns it belongs to')

        prepid = self.get_attribute('prepid')
        chained_requests = self.get_chained_requests()
        for chained_request in chained_requests:
            if chained_request['chain'].index(prepid) != chained_request['step']:
                raise Exception('Request if not current step of %s' % (chained_request['prepid']))

        # Check previous request
        self.check_with_previous(True)

        # Check if sequences in request are different from the sequences in
        # campaign. If they are different, then either flow or request should
        # have a processing string set
        processing_string = self.get_attribute('process_string')
        if not processing_string:
            flow_processing_string = None
            flow_name = self.get_attribute('flown_with')
            request_parameters = {}
            if flow_name:
                flow_db = Database('flows')
                flow = flow_db.get(flow_name)
                request_parameters = flow.get('request_parameters', {})
                flow_processing_string = request_parameters.get('process_string')

            if not flow_processing_string:
                def similar_sequences(seq1, seq2):
                    """
                    Return whether two sequences are similar enough to not need a
                    explicit processing string
                    """
                    ignore = {'conditions', 'datatier', 'eventcontent', 'nThreads'}
                    # Get keys of both sequences and remove the ignored ones
                    keys = list(set(list(seq1.keys()) + list(seq2.keys())) - ignore)
                    # Cound number of different values for the keys above
                    diff = [1 for k in keys if seq1.get(k) and seq2.get(k) and seq1[k] != seq2[k]]
                    return bool(diff)

                # Neither request, nor flow have processing string, compare
                # sequences of request and campaign
                campaign_sequences = campaign['sequences']
                # Get sequence names from flow
                flow_sequences = list(request_parameters.get('sequences', {}).keys())
                # Add 'default' name if any are missing
                flow_sequences += ['default'] * len(campaign_sequences) - len(flow_sequences)
                # Get sequences from campaign based on flow sequence names
                campaign_sequences = [s[f] for f, s in zip(flow_sequences, campaign_sequences)]
                for request_sequence, campaign_sequence in zip(sequences, campaign_sequences):
                    if not similar_sequences(request_sequence, campaign_sequence):
                        raise Exception('Sequences of request differ from campaign sequences, but '
                                        'neither flow, nor request itself have a processing string '
                                        'to show that')

        bypass_list = Settings.get('validation_bypass')
        if prepid in bypass_list:
            self.logger.info('Request %s is in validation bypass list and is being moved to approved status',
                             prepid)
            self.move_to_approved()
            return

        self.set_approval_status('validation', 'new')
        self.reload()

    def move_to_defined(self):
        """
        Move request to define-defined ("defined") status
        """
        self.logger.warning('Not checking if user moving request to defined is from correct PWG')
        self.set_approval_status('define', 'defined')
        self.reload()

    def move_to_approved(self):
        """
        Move reqeust to approve-approved ("approved") status
        """
        prepid = self.get_attribute('prepid')
        approval = self.get_attribute('approval')
        status = self.get_attribute('status')
        if approval == 'defined' and status == 'defined':
            # Only GEN conveners, production experts and administrators are
            # allowed to approve defined requests
            user = User()
            username = user.get_username()
            user_role = user.get_role()
            self.logger.info('User %s (%s) is trying to approve %s', username, user_role, prepid)
            if user_role != Role.GEN_CONVENER and user_role < Role.PRODUCTION_EXPERT:
                raise Exception('You are not allowed to approve "defined" requests')

        if not self.get_attribute('dataset_name'):
            raise Exception('Dataset name cannot be empty')

        # Validate attributes
        self.validate()

        # Check for invalidations
        self.check_for_invalidations()

        # Check for collisions
        self.check_for_collisions()

        # Set new status
        self.set_approval_status('approve', 'approved')

        chained_requests = self.get_chained_requests()
        # Check status of requests leading to this one
        self.check_status_of_previous(chained_requests)
        self.check_with_previous(True)
        self.get_input_dataset_status()
        self.reload()

    def check_for_collisions(self):
        """
        Check if there are any other requests that have same dataset name, same
        campaign, same processing string and datatier
        Ignore none-new requests
        """
        request_db = Database('requests')
        dataset_name = self.get_attribute('dataset_name')
        campaign = self.get_attribute('member_of_campaign')
        query = {'dataset_name': dataset_name, 'member_of_campaign': campaign}
        similar_requests = request_db.search('search', query, limit=-1)
        if len(similar_requests) == 0:
            raise Exception('It seems that database is down, could not check for duplicates')

        # Remove self
        prepid = self.get_attribute('prepid')
        similar_requests = [r for r in similar_requests if r['prepid'] != prepid]
        # Remove none-new requests
        similar_requests = [r for r in similar_requests if r['approval'] != 'none']
        # Maybe there are no more similar requests?
        if not similar_requests:
            return

        my_ps_and_tiers = set(self.get_kept_processing_strings_and_tiers())
        self.logger.info('Found %s requests with same dataset and campaign as %s: %s',
                         len(similar_requests),
                         prepid,
                         ', '.join(r['prepid'] for r in similar_requests))

        for similar_request_json in similar_requests:
            similar_request = Request(similar_request_json)
            ps_and_tiers = set(similar_request.get_kept_processing_strings_and_tiers())
            # Check for collision
            collisions = my_ps_and_tiers & ps_and_tiers
            if not collisions:
                continue

            similar_request_id = similar_request_json['prepid']
            collision = collisions.pop()
            message = ('Output dataset name collision with %s. '
                       'Process string "%s", datatier "%s"' % (similar_request_id,
                                                               collision[0],
                                                               collision[1]))
            self.logger.error(message)
            raise Exception(message)

    def check_for_invalidations(self):
        """
        Check if there are new/announced invalidations for the request.
        """
        invalidation_db = Database('invalidations')
        prepid = self.get_attribute('prepid')
        invalidations = invalidation_db.search("search", {'prepid': prepid}, limit=None)
        invalidations = [i for i in invalidations if i["status"] in {"new", "announced"}]
        if invalidations:
            raise Exception('There are %s unacknowledged invalidations for %s' % (len(invalidations),
                                                                                  prepid))

    def get_input_dataset(self, datasets):
        """
        Try to figure out a dataset of "datasets" that could be used as input
        for the first sequence based on sequence's "step"
        """
        sequences = self.get_attribute('sequences')
        if not datasets or not sequences:
            self.logger.warning('Return "" dataset name, becase datasets or sequences are missing')
            return ""

        steps = sequences[0]['step']
        if isinstance(steps, str):
            # TODO: Is this possible?
            steps = steps.split(',')

        # Take the first step and remove :... if needed
        step = steps[0].split(':')[0]
        step_input_dict = Settings.get_value('datatier_input')
        if step not in step_input_dict:
            self.logger.warning('Could not find input info for "%s" step, returning %s',
                                step,
                                datasets[0])
            return datasets[0]

        datatiers = step_input_dict[step]
        for datatier in datatiers:
            for dataset in datasets:
                if dataset.split('/')[-1] == datatier:
                    self.logger.info('Picked "%s" as input for "%s"', dataset, step)
                    return dataset

        return datasets[0]

    def check_with_previous(self, update_total_events=False):
        """
        Check if previous request in the chain has enough events
        Update total events of this request if needed
        """
        previous_request = self.get_previous_request()
        if not previous_request:
            return

        previous_prepid = previous_request['prepid']
        # By default, it's total_events
        previous_events = previous_request['total_events']
        # Get input dataset
        input_dataset = self.get_input_dataset(previous_request['output_dataset'])
        if input_dataset and previous_request['reqmgr_name']:
            for workflow in previous_request['reqmgr_name']:
                dataset_statuses = workflow["content"].get("pdmv_dataset_statuses", {})
                if input_dataset in dataset_statuses:
                    previous_events = dataset_statuses[input_dataset]["pdmv_evts_in_DAS"]
                    break

        if previous_events <= 0 and previous_request['completed_events'] > 0:
            previous_events = previous_request['completed_events']
        else:
            raise Exception('Cannot get events for previous request %s' % (previous_prepid))

        prepid = self.get_attribute('prepid')
        self.logger.debug('Found %s events in %s (%s) as input for %s',
                          previous_events,
                          previous_prepid,
                          input_dataset,
                          prepid)

        total_events = self.get_attribute('total_events')
        efficiency = self.get_efficiency()
        # How many events could be produced from input with certain filter
        events_after_filter = int(previous_events * efficiency)
        percentage = events_after_filter / total_events
        # If less than 75% events could be produced, throw an error
        if percentage < 0.75:
            raise Exception('%s requires %s events, but only ~%s (%.2f%%) can be produced using %s '
                            'as input with %s events' % (prepid,
                                                         total_events,
                                                         events_after_filter,
                                                         percentage * 100,
                                                         previous_prepid,
                                                         previous_events))

        if update_total_events and total_events > events_after_filter:
            self.set_attribute('total_events', events_after_filter)

    def check_status_of_previous(self, chained_requests):
        """
        Go through all chains that request is in and check if requests that are
        leading to this request are in greater or equal status
        """
        if not chained_requests:
            return

        prepids = set()
        prepid = self.get_attribute('prepid')
        for chained_request in chained_requests:
            chain = chained_request['chain']
            if prepid not in chain:
                raise Exception('%s is not a member of %s' % (prepid, chained_request['prepid']))

            prepids.update(chain[:chain.index(prepid)])

        if not prepids:
            return

        request_db = Database('requests')
        requests = request_db.bulk_get(list(prepids))
        approval_status = self.get_approval_status()

        for request in requests:
            request_approval_status = '%s-%s' % (request['approval'], request['status'])
            if self.order.index(request_approval_status) < self.order.index(approval_status):
                raise Exception('%s status is %s which is lower than %s' % (request['prepid'],
                                                                            request_approval_status,
                                                                            approval_status))

    def to_be_submitted_together(self, chained_requests):
        """
        Return dictionary of chained requests and their requests that should be
        submitted togetger with this request
        """
        chained_requests = [c for c in chained_requests if c['enabled']]
        prepid = self.get_attribute('prepid')
        chained_campaign_db = Database('chained_campaigns')
        request_db = Database('requests')
        requests_cache = {}
        flow_db = Database('flows')
        flows_cache = {}
        def get_requests(prepids):
            to_get = [p for p in prepids if p not in requests_cache]
            if to_get:
                requests = request_db.bulk_get(to_get)
                for request in requests:
                    requests_cache[request['prepid']] = request

            return [requests_cache[p] for p in prepids]

        def get_flow(prepid):
            if prepid not in flows_cache:
                flows_cache[prepid] = flow_db.get(prepid)

            return flows_cache[prepid]

        together = []
        for chained_request in chained_requests:
            chained_campaign = chained_campaign_db.get(chained_request['member_of_campaign'])
            if not chained_campaign['enabled']:
                chained_campaign_id = chained_campaign['prepid']
                self.logger.debug('Chained campaign %s is disabled, ignoring', chained_campaign_id)

            chain = chained_request['chain']
            chain = chain[chain.index(prepid) + 1:]
            if not chain:
                continue

            together[chained_request['prepid']] = []
            requests = get_requests(chain)
            for request in requests:
                flow = get_flow(request['flown_with'])
                if flow['approval'] == 'tasksubmit':
                    together[chained_request['prepid']].append(request)
                else:
                    break

        return together

    def move_to_submitting(self):
        """
        Move reqeust to approve-approved ("approved") status
        """
        prepid = self.get_attribute('prepid')
        user = User(db=True)
        username = user.get_username()
        user_role = user.user_dict.get('role')
        self.logger.info('User %s (%s) is trying to approve %s', username, user_role, prepid)
        if user_role not in {'production_manager', 'administrator'}:
            raise Exception('You are not allowed to submit requests')

        if not self.get_attribute('dataset_name'):
            raise Exception('Dataset name cannot be empty')

        if not self.get_scram_arch():
            raise Exception('SCRAM architecture is invalid, please double check the release')

        if not self.get_attribute('member_of_chain'):
            raise Exception('Request is not a member of any chains')

        # Validate attributes
        self.validate()

        # Check for invalidations
        self.check_for_invalidations()

        # Check for collisions
        self.check_for_collisions()

        # Set new status
        self.set_approval_status('submit', 'approved')

        chained_requests = self.get_chained_requests()
        # Check status of requests leading to this one
        self.check_status_of_previous(chained_requests)

        # TODO: Allow users to aprove only current steps of chain, only
        # submission or flowing code can approve otherwise
        chained_requests = [c for c in chained_requests if c['enabled']]
        previous_request = self.get_previous_request()
        if previous_request['status'] == 'done':
            self.get_input_dataset_status()
            for chained_request in chained_requests:
                if chained_request['chain'].index(prepid) != chained_request['step']:
                    raise Exception('%s is not current step of %s' % (prepid,
                                                                      chained_request['prepid']))
        else:
            self.set_attribute('input_dataset', '')

        # Collect chains and requests that should be submitted together
        submitted_together = self.to_be_submitted_together(chained_requests)
        raise NotImplemented('Submission is no implemented')
        # TODO: submit
        # from tools.handlers import ChainRequestInjector, submit_pool
        # _q_lock = locker.thread_lock(prepid)
        # if not locker.thread_acquire(prepid, blocking=False):
        #     return {'prepid': self.get_attribute('prepid'),
        #             'results': False,
        #             'message': 'Request %s is being handled already' % (prepid)}
        # threaded_submission = ChainRequestInjector(prepid=prepid,
        #                                            check_approval=False,
        #                                            lock=locker.lock(prepid),
        #                                            queue_lock=_q_lock)
        # submit_pool.add_task(threaded_submission.internal_run)

    def has_at_least_an_action(self):
        crdb = database('chained_requests')
        for in_chain_id in self.get_attribute('member_of_chain'):
            if not crdb.document_exists(in_chain_id):
                self.logger.error('for %s there is a chain inconsistency with %s' % (self.get_attribute('prepid'), in_chain_id))
                return False
            in_chain = crdb.get(in_chain_id)
            if in_chain['action_parameters']['flag']:
                return True
        return False

    def retrieve_fragment(self, name=None, get=True):
        if not name:
            name = self.get_attribute('name_of_fragment')
        get_me = ''
        tag = self.get_attribute('fragment_tag')
        fragment_retry_amount = 2
        if tag and name:
            # remove this to allow back-ward compatibility of fragments/requests placed with PREP
            name = name.replace('Configuration/GenProduction/python/', '')
            name = name.replace('Configuration/GenProduction/', '')
            # curl from git hub which has all history tags
            # get_me = 'curl -L -s https://raw.github.com/cms-sw/genproductions/%s/python/%s --retry %s ' % (
            get_me = 'curl  -s https://raw.githubusercontent.com/cms-sw/genproductions/%s/python/%s --retry %s ' % (
                self.get_attribute('fragment_tag'),
                name,
                fragment_retry_amount)
            # add the part to make it local
            if get:
                get_me += '--create-dirs -o Configuration/GenProduction/python/%s ' % (name)
                # lets check if downloaded file actually exists and has more than 0 bytes
                get_me += '\n[ -s Configuration/GenProduction/python/%s ] || exit $?;\n' % (name)

        if get:
            get_me += '\n'
        return get_me

    def get_fragment(self):
        # provides the name of the fragment depending on
        # fragment=self.get_attribute('name_of_fragment').decode('utf-8')
        fragment = self.get_attribute('name_of_fragment')
        if self.get_attribute('fragment') and not fragment:
            # fragment='Configuration/GenProduction/python/%s_fragment.py'%(self.get_attribute('prepid').replace('-','_'))
            fragment = 'Configuration/GenProduction/python/%s-fragment.py' % (self.get_attribute('prepid'))

        if fragment and not fragment.startswith('Configuration/GenProduction/python/'):
            fragment = 'Configuration/GenProduction/python/' + fragment

        return fragment

    def build_cmsDriver(self, sequenceindex):
        fragment = self.get_fragment()

        # JR
        if fragment == '':
            fragment = 'step%d' % (sequenceindex + 1)
        command = 'cmsDriver.py %s ' % fragment

        try:
            seq = sequence(self.get_attribute('sequences')[sequenceindex])
        except Exception:
            self.logger.error('Request %s has less sequences than expected. Missing step: %d' % (
                self.get_attribute('prepid'),
                sequenceindex))

            return ''

        cmsDriverOptions = seq.build_cmsDriver()

        if not cmsDriverOptions.strip():
            return '%s %s' % (command, cmsDriverOptions)

        # JR
        input_from_ds = None
        input_from_previous = None
        input_from_lhe = None
        if self.get_attribute('mcdb_id') > 0:
            input_from_lhe = 'lhe:%d ' % (self.get_attribute('mcdb_id'))
        if len(self.get_attribute('member_of_chain')):
            crdb = database('chained_requests')
            previouses = set()
            for crn in self.get_attribute('member_of_chain'):
                cr = crdb.get(crn)
                here = cr['chain'].index(self.get_attribute('prepid'))
                if here > 0 and here > cr['step']:  # there or not at root
                    previouses.add(cr['chain'][here - 1])
            if len(previouses) == 1:
                input_from_previous = "file:%s.root" % list(previouses)[0]
        if self.get_attribute('input_dataset') and not input_from_previous:
            input_from_ds = '"dbs:%s"' % (self.get_attribute('input_dataset'))

        input_default = 'file:%s_step%d.root' % (self.get_attribute('prepid'), sequenceindex)
        if sequenceindex == 0:
            if input_from_ds:
                input_default = input_from_ds
            elif input_from_previous:
                input_default = input_from_previous
            elif input_from_lhe:
                input_default = input_from_lhe
            else:
                input_default = None
        if input_default:
            command += '--filein %s ' % input_default

        output_file = ''
        if sequenceindex == len(self.get_attribute('sequences')) - 1:
            # last one
            command += '--fileout file:%s.root ' % (self.get_attribute('prepid'))
            output_file = '%s.root ' % (self.get_attribute('prepid'))
        else:
            command += '--fileout file:%s_step%d.root ' % (self.get_attribute('prepid'), sequenceindex + 1)
            output_file += '%s_step%d.root ' % (self.get_attribute('prepid'), sequenceindex + 1)

        # JR
        if self.get_attribute('pileup_dataset_name') and not (seq.get_attribute('pileup') in ['', 'NoPileUp']):
            command += '--pileup_input "dbs:%s" ' % (self.get_attribute('pileup_dataset_name'))
        elif self.get_attribute('pileup_dataset_name') and (seq.get_attribute('pileup') in ['']) and (seq.get_attribute('datamix') in ['PreMix']):
            command += ' --pileup_input "dbs:%s" ' % (self.get_attribute('pileup_dataset_name'))
        return '%s%s' % (command, cmsDriverOptions)

    def transfer_from(self, camp):
        keys_to_transfer = ['energy', 'cmssw_release', 'pileup_dataset_name', 'type', 'input_dataset', 'memory']
        for k in keys_to_transfer:
            try:
                if camp.get_attribute(k):
                    self.set_attribute(k, camp.get_attribute(k))
            except request.IllegalAttributeName:
                continue

    def reset_options(self):
        """
        Re-fetch energy, cmssw release, pu dataset, type, input dataset, memory
        and sequences from the campaign and apply flow parameters if any
        Make sure there is correct number of time and size per event values
        """
        prepid = self.get_attribute('prepid')
        if not self.get_attribute('status') == 'new':
            raise Exception('Cannot reset options for a non "new" request "%s"' % (prepid))

        campaign_name = self.get_attribute('member_of_campaign')
        campaign = Campaign.fetch(campaign_name)
        if not campaign:
            raise Exception('"%s" could not find "%s" to reset options' % (prepid, campaign_name))

        self.logger.info('Resetting options for "%s" from "%s"', prepid, campaign_name)
        # Copy values from campaign
        to_copy = ('energy', 'cmssw_release', 'pileup_dataset_name',
                   'type', 'input_dataset', 'memory', 'keep_output')
        for attribute in to_copy:
            self.set_attribute(attribute, campaign.get(attribute))

        # Get flow's request parameters
        request_parameters = {}
        flow_name = self.get_attribute('flown_with')
        if flow_name:
            flow = Flow.fetch(flow_name)
            if not flow:
                raise Exception('"%s" could not find "%s" to reset options' % (prepid, flow_name))

            request_parameters = flow.get('request_parameters')

        sequences = []
        sequences_name = request_parameters.get('sequences_name', 'default')
        campaign_sequences = campaign.get('sequences')[sequences_name]
        flow_sequences = request_parameters.get('sequences', [])
        # Add empty sequences to flow
        flow_sequences += (len(campaign_sequences) - len(flow_sequences)) * [{}]
        assert len(campaign_sequences) == len(flow_sequences)
        # Iterate through campaign and flow sequences
        # Apply flow changes over campaign's sequence and add to list
        for flow_seq, campaign_seq in zip(flow_sequences, campaign_sequences):
            # Allow all attributes?
            campaign_seq.update(flow_seq)
            sequences.append(campaign_seq)

        self.set_attribute('sequences', sequences)
        # Set values from request parameters
        for key, value in request_parameters.items():
            if key in ('sequences', 'sequences_name', 'keep_output'):
                continue

            self.set(key, value)

        # Keep output
        keep_output = campaign.get('keep_output')[sequences_name]
        self.set('keep_output', keep_output)

        # Assert Keep output
        assert len(sequences) == len(self.get('keep_output'))

        # Number of time per event values
        assert len(sequences) == len(self.get('time_event'))

        # Number of size per event values
        assert len(sequences) == len(self.get('size_event'))

        # Add hisotry entry
        self.update_history('reset', 'option')

    def build_cmsDrivers(self):
        commands = []
        for i in range(len(self.get_attribute('sequences'))):
            cd = self.build_cmsDriver(i)
            if cd:
                commands.append(cd)
        return commands

    def update_generator_parameters(self):
        """
        Create a new generator paramters at the end of the list
        """
        gens = self.get_attribute('generator_parameters')
        if not len(gens):
            genInfo = generator_parameters()
        else:
            genInfo = generator_parameters(gens[-1])
            genInfo.set_attribute('submission_details', self._json_base__get_submission_details())
            genInfo.set_attribute('version', genInfo.get_attribute('version') + 1)

        gens.append(genInfo.json())
        self.set_attribute('generator_parameters', gens)

    def get_tier(self, i):
        s = self.get_attribute('sequences')[i]
        tiers = s['datatier']
        if isinstance(tiers, str):
            tiers = tiers.split(',')

        # the first tier is the main output : reverse it
        return list(reversed(tiers))

    def get_tiers(self):
        r_tiers = []
        keeps = self.get_attribute('keep_output')
        for (i, s) in enumerate(self.get_attribute('sequences')):
            if i < len(keeps) and not keeps[i]:
                continue
            r_tiers.extend(self.get_tier(i))
        # the last tier is the main output : reverse it
        return list(reversed(r_tiers))

    def get_processing_string(self, i):
        """
        Get processing string for a certain sequence
        Processing string depends on conditions, so each sequence may have
        different processing string
        """
        ingredients = []
        if self.get_attribute('flown_with'):
            chained_campaign_db = Database('chained_campaigns')
            # could 2nd chain_req be with different process_string??
            # we dont want to use chained_camp object -> circular dependency :/
            # so we work on json object
            chained_campaign_id = self.get_attribute("member_of_chain")[0].split("-")[1]
            chained_campaign = chained_campaign_db.get(chained_campaign_id)
            if not chained_campaign:
                prepid = self.get_attribute('prepid')
                raise Exception('Chained campaign %s of %s could not be found' % (chained_campaign_id, prepid))

            member_of_campaign = self.get_attribute('member_of_campaign')
            flow_db = Database('flows')
            for campaign_name, flow_name in chained_campaign["campaigns"]:
                if flow_name:
                    flow = flow_db.get(flow_name)
                    ingredients.append(flow.get('request_parameters', {}).get('process_string', ''))

                # Don't include processing strings from subsequent flows
                if member_of_campaign == campaign_name:
                    break

        # Processing string of this request
        ingredients.append(self.get_attribute('process_string'))
        # Conditions of "i" sequence
        ingredients.append(self.get_attribute('sequences')[i]['conditions'].replace('::All', ''))
        # Add extension if it's > 0
        extension = self.get_attribute('extension')
        if extension > 0:
            ingredients.append("ext%s" % extension)

        # Join all truthy values with underscore
        ingredients = [ingredient.strip() for ingredient in ingredients if ingredient.strip()]
        return '_'.join(ingredients)

    def get_kept_processing_strings_and_tiers(self):
        """
        Return tuples of processing strings and datatiers of sequences that are
        kept (keep_output[x] = True)
        """
        keep_output = self.get_attribute('keep_output')
        sequences = self.get_attribute('sequences')
        assert len(keep_output) == len(sequences)
        tiers = []
        for i, (keep, sequence) in enumerate(zip(keep_output, sequences)):
            if keep:
                processing_string = self.get_processing_string(i)
                datatiers = [t for t in sequence.get('datatier', '').split(',') if t]
                tiers.extend([(processing_string, datatier) for datatier in datatiers])

        return tiers

    def get_scram_arch(self):
        """
        Get scram arch of the request's release
        """
        if hasattr(self, 'scram_arch'):
            return self.scram_arch

        self.scram_arch = fetch_scram_arch(self.get_attribute('cmssw_release'))
        return self.scram_arch

    def make_release(self):
        cmssw_release = self.get_attribute('cmssw_release')
        scram_arch = self.get_scram_arch()
        release_command = ['export SCRAM_ARCH=%s\n' % (scram_arch),
                           'source /cvmfs/cms.cern.ch/cmsset_default.sh',
                           'if [ -r %s/src ] ; then' % (cmssw_release),
                           '  echo release %s already exists' % (cmssw_release),
                           'else',
                           '  scram p CMSSW %s' % (cmssw_release),
                           'fi',
                           'cd %s/src' % (cmssw_release),
                           'eval `scram runtime -sh`',
                           '']

        return '\n'.join(release_command)

    def should_run_gen_script(self):
        """
        Return whether GEN checking script should be run during validation of this request
        """
        sequence_steps = []
        for seq in self.get_attribute('sequences'):
            for st in seq.get('step', []):
                sequence_steps.extend([x.strip() for x in st.split(',') if x.strip()])

        sequence_steps = set(sequence_steps)
        gen_script_steps = set(('GEN', 'LHE', 'FSPREMIX'))
        should_run = bool(sequence_steps & gen_script_steps)
        prepid = self.get_attribute('prepid')
        return should_run

    def build_cmsdriver(self, sequence_dict, fragment):
        command = 'cmsDriver.py %s' % (fragment)
        # Add pileup dataset name
        pileup_dataset_name = self.get_attribute('pileup_dataset_name').strip()
        seq_pileup = sequence_dict.get('pileup').strip()
        seq_datamix = sequence_dict.get('datamix')
        if pileup_dataset_name:
            if (seq_pileup not in ('', 'NoPileUp')) or (seq_pileup == '' and seq_datamix == 'PreMix'):
                sequence_dict['pileup_input'] = '"dbs:%s"' % (pileup_dataset_name)

        for key, value in sequence_dict.items():
            if not value or key in ('index', 'extra'):
                continue

            if isinstance(value, list):
                command += ' --%s %s' % (key, ','.join(value))
            elif key == 'nThreads' and int(value) == 1:
                # Do not add --nThreads 1 because some old CMSSW crashes
                continue
            else:
                command += ' --%s %s' % (key, value)

        # Extras
        if sequence_dict.get('extra'):
            command += ' %s' % (sequence_dict['extra'].strip())

        command += ' --no_exec --mc -n $EVENTS || exit $? ;'
        return command

    def get_input_file_for_sequence(self, sequence_index):
        prepid = self.get_attribute('prepid')
        if sequence_index == 0:
            # First sequence can have:
            # * output from previous request (if any)
            # * mcdb input
            # * input_dataset attribute
            # * no input file
            # Get all chained requests and look for previous request
            input_dataset = self.get_attribute('input_dataset')
            if input_dataset:
                return '"dbs:%s"' % (input_dataset)

            member_of_chain = self.get_attribute('member_of_chain')
            if member_of_chain:
                chained_requests_db = database('chained_requests')
                previouses = set()
                # Iterate through all chained requests
                for chained_request_prepid in member_of_chain:
                    chained_request = chained_requests_db.get(chained_request_prepid)
                    # Get place of this request
                    index_in_chain = chained_request['chain'].index(prepid)
                    # If there is something before this request, return that prepid
                    if index_in_chain > 0:
                        return 'file:%s.root' % (chained_request['chain'][index_in_chain - 1])

            mcdb_id = self.get_attribute('mcdb_id')
            if mcdb_id > 0:
                return '"lhe:%s"' % (mcdb_id)

        else:
            return 'file:%s_%s.root' % (prepid, sequence_index - 1)

        return ''

    def get_setup_file2(self, for_validation, automatic_validation, threads=None, configs_to_upload=None):
        loc = locator()
        is_dev = loc.isDev()
        base_url = loc.baseurl()
        prepid = self.get_attribute('prepid')
        member_of_campaign = self.get_attribute('member_of_campaign')
        scram_arch = self.get_scram_arch().lower()
        if scram_arch.startswith('slc7_'):
            scram_arch_os = 'CentOS7'
        else:
            scram_arch_os = 'SLCern6'

        bash_file = ['#!/bin/bash', '']

        if not for_validation or automatic_validation:
            bash_file += ['#############################################################',
                          '#   This script is used by McM when it performs automatic   #',
                          '#  validation in HTCondor or submits requests to computing  #',
                          '#                                                           #',
                          '#      !!! THIS FILE IS NOT MEANT TO BE RUN BY YOU !!!      #',
                          '# If you want to run validation script yourself you need to #',
                          '#     get a "Get test" script which can be retrieved by     #',
                          '#  clicking a button next to one you just clicked. It will  #',
                          '# say "Get test command" when you hover your mouse over it  #',
                          '#      If you try to run this, you will have a bad time     #',
                          '#############################################################',
                          '']

        if not for_validation and not automatic_validation:
            directory = installer.build_location(prepid)
            bash_file += ['cd %s' % (directory), '']

        sequences = self.get_attribute('sequences')
        if for_validation and automatic_validation:
            for index, sequence_dict in enumerate(sequences):
                report_name = '%s_' % (prepid)
                # If it is not the last sequence, add sequence index to then name
                if index != len(sequences) - 1:
                    report_name += '%s_' % (index)

                report_name += '%s_threads_report.xml' % (threads)
                bash_file += ['touch %s' % (report_name)]

        run_gen_script = for_validation and self.should_run_gen_script() and (threads == 1 or threads is None)
        self.logger.info('Should %s run GEN script: %s' % (prepid, 'YES' if run_gen_script else 'NO'))
        if run_gen_script:
            # Download the script
            bash_file += ['# GEN Script begin',
                          'rm -f request_fragment_check.py',
                          'wget -q https://raw.githubusercontent.com/cms-sw/genproductions/master/bin/utils/request_fragment_check.py',
                          'chmod +x request_fragment_check.py']
            # Checking script invocation
            request_fragment_check = './request_fragment_check.py --bypass_status --prepid %s' % (prepid)
            if is_dev:
                # Add --dev, so script would use McM DEV
                request_fragment_check += ' --dev'

            if automatic_validation:
                # For automatic validation
                if is_dev:
                    eos_path = '/eos/cms/store/group/pdmv/mcm_gen_checking_script_dev/%s' % (member_of_campaign)
                else:
                    eos_path = '/eos/cms/store/group/pdmv/mcm_gen_checking_script/%s' % (member_of_campaign)

                # Set variables to save the script output
                bash_file += ['eos mkdir -p %s' % (eos_path)]

                # Point output to EOS
                # Save stdout and stderr
                request_fragment_check += ' > %s_newest.log 2>&1' % (prepid)

            # Execute the GEN script
            bash_file += [request_fragment_check]
            # Get exit code of GEN script
            bash_file += ['GEN_ERR=$?']
            if automatic_validation:
                # Add latest log to all logs
                bash_file += ['eos cp %s/%s.log . 2>/dev/null' % (eos_path, prepid),
                              'touch %s.log' % (prepid),
                              'cat %s_newest.log >> %s.log' % (prepid, prepid),
                              # Write a couple of empty lines to the end of a file
                              'echo "" >> %s.log' % (prepid),
                              'echo "" >> %s.log' % (prepid),
                              'eos cp %s.log %s/%s.log' % (prepid, eos_path, prepid),
                              # Print newest log to stdout
                              'echo "--BEGIN GEN Request checking script output--"',
                              'cat %s_newest.log' % (prepid),
                              'echo "--END GEN Request checking script output--"']

            # Check exit code of script
            bash_file += ['if [ $GEN_ERR -ne 0 ]; then',
                          '  echo "GEN Checking Script returned exit code $GEN_ERR which means there are $GEN_ERR errors"',
                          '  echo "Validation WILL NOT RUN"',
                          '  echo "Please correct errors in the request and run validation again"',
                          '  exit $GEN_ERR',
                          'fi',
                          # If error code is zero, continue to validation
                          'echo "Running VALIDATION. GEN Request Checking Script returned no errors"',
                          '# GEN Script end',
                          # Empty line after GEN business
                          '']

        if automatic_validation:
            test_file_name = '%s_%s_threads_test.sh' % (prepid, threads)
        else:
            test_file_name = '%s_test.sh' % (prepid)

        if not for_validation:
            bash_file += ['# Make voms proxy',
                          'voms-proxy-init --voms cms --out $(pwd)/voms_proxy.txt --hours 4',
                          'export X509_USER_PROXY=$(pwd)/voms_proxy.txt',
                          '']

        if automatic_validation:
            bash_file += ['# Extract and print CPU name and hypervisor name',
                          'cpu_name=$(lscpu | grep "Model name" | head -n 1 | sed "s/Model name: *//g")',
                          'hypervisor_name=$(lscpu | grep "Hypervisor vendor" | head -n 1 | sed "s/Hypervisor vendor: *//g")',
                          'echo "CPU_NAME=$cpu_name ($hypervisor_name)"',
                          '']

        # Whether to dump cmsDriver.py to a file so it could be run using singularity
        dump_test_to_file = (scram_arch_os == 'SLCern6')
        if dump_test_to_file:
            bash_file += ['# Dump actual test code to a %s file that can be run in Singularity' % (test_file_name),
                          'cat <<\'EndOfTestFile\' > %s' % (test_file_name),
                          '#!/bin/bash',
                          '']

        # Set up CMSSW environment
        bash_file += self.make_release().split('\n')

        # Get the fragment if need to
        fragment_name = self.get_fragment()
        if fragment_name:
            fragment = self.get_attribute('fragment')
            if fragment:
                # Download the fragment directly from McM into a file
                bash_file += ['# Download fragment from McM',
                              'curl -s -k %spublic/restapi/requests/get_fragment/%s --retry 3 --create-dirs -o %s' % (base_url,
                                                                                                                      prepid,
                                                                                                                      fragment_name),
                              '[ -s %s ] || exit $?;' % (fragment_name)]
            else:
                bash_file += ['# Retrieve fragment from github and ensure it is there']
                bash_file += self.retrieve_fragment().strip().split('\n')

            # Check if fragment contains gridpack path and that gridpack is in cvmfs when running validation
            if for_validation:
                bash_file += ['',
                              '# Check if fragment contais gridpack path ant that it is in cvmfs',
                              'if grep -q "gridpacks" %s; then' % (fragment_name),
                              '  if ! grep -q "/cvmfs/cms.cern.ch/phys_generator/gridpacks" %s; then' % (fragment_name),
                              '    echo "Gridpack inside fragment is not in cvmfs."',
                              '    exit -1',
                              '  fi',
                              'fi']

        bash_file += ['scram b',
                      'cd ../..',
                      '']

        # Add proxy for submission and automatic validation
        if for_validation and automatic_validation:
            # Automatic validation
            bash_file += ['# Environment variable to voms proxy in order to fetch info from cmsweb',
                          'export X509_USER_PROXY=$(pwd)/voms_proxy.txt',
                          'export HOME=$(pwd)',
                          '']

        # Events to run
        events, explanation = self.get_event_count_for_validation(with_explanation=True)
        bash_file += [explanation,
                      'EVENTS=%s' % (events),
                      '']

        # Random seed for wmLHEGS requests
        if 'wmlhegs' in self.get_attribute('prepid').lower():
            bash_file += ['# Random seed between 1 and 100 for externalLHEProducer',
                          'SEED=$(($(date +%s) % 100 + 1))',
                          '']

        # Iterate over sequences and build cmsDriver.py commands
        for index, sequence_dict in enumerate(sequences):
            self.logger.info('Getting sequence %s of %s' % (index, prepid))
            config_filename = '%s_%s_cfg.py' % (prepid, index + 1)
            sequence_dict = copy.deepcopy(sequence_dict)
            sequence_dict['python_filename'] = config_filename
            if sequence_dict['customise']:
                sequence_dict['customise'] += ','

            sequence_dict['customise'] += 'Configuration/DataProcessing/Utils.addMonitoring'
            if 'wmlhegs' in prepid.lower():
                if sequence_dict['customise_commands']:
                    sequence_dict['customise_commands'] += '\\\\n'

                sequence_dict['customise_commands'] += 'process.RandomNumberGeneratorService.externalLHEProducer.initialSeed="int(${SEED})"'

            if for_validation and self.should_run_gen_script() and index == 0 :
                campaign_db = database('campaigns')
                request_campaign = campaign(campaign_db.get(self.get_attribute('member_of_campaign')))
                # CMSSW must be >= 9.3.0
                if request_campaign.is_release_greater_or_equal_to('CMSSW_9_3_0'):
                    member_of_chains = self.get_attribute('member_of_chain')
                    # Request must be first in chain
                    first_in_chain = True
                    if len(member_of_chains) > 0:
                        from json_layer.chained_request import chained_request
                        chained_request_db = database('chained_requests')
                        chained_req = chained_request(chained_request_db.get(member_of_chains[0]))
                        chained_req_chain = chained_req.get_attribute('chain')
                        if len(chained_req_chain) > 0 and chained_req_chain[0] != self.get_attribute('prepid'):
                            first_in_chain = False

                    self.logger.info('%s is first in chain: %s', prepid, 'YES' if first_in_chain else 'NO')
                    if first_in_chain:
                        events_per_lumi = self.get_events_per_lumi(threads)
                        events_per_lumi /= self.get_efficiency() # should stay nevertheless as it's in wmcontrol for now
                        events_per_lumi /= self.get_forward_efficiency()  # this does not take its own efficiency
                        events_per_lumi = int(events_per_lumi)
                        if sequence_dict['customise_commands']:
                            sequence_dict['customise_commands'] += '\\\\n'

                        sequence_dict['customise_commands'] += 'process.source.numberEventsInLuminosityBlock="cms.untracked.uint32(%s)"' % (events_per_lumi)

            if threads is not None:
                sequence_dict['nThreads'] = threads

            if index != len(sequences) - 1:
                # Add sequence index if this is not the last index
                sequence_dict['fileout'] = 'file:%s_%s.root' % (prepid, index)
            else:
                # Otherwise it is just <prepid>.root
                sequence_dict['fileout'] = 'file:%s.root' % (prepid)

            filein = self.get_input_file_for_sequence(index)
            if filein:
                sequence_dict['filein'] = filein

            bash_file += ['',
                          '# cmsDriver command',
                          self.build_cmsdriver(sequence_dict, fragment_name)]

            if for_validation:
                report_name = '%s_' % (prepid)
                # If it is not the last sequence, add sequence index to then name
                if index != len(sequences) - 1:
                    report_name += '%s_' % (index)

                if automatic_validation:
                    report_name += '%s_threads_report.xml' % (threads)
                else:
                    report_name += 'report.xml'

                if automatic_validation:
                    kill_timeout = self.get_validation_max_runtime() - 1800 # 30 minutes
                    bash_file += ['',
                                  '# Sleeping killer',
                                  'export VALIDATION_RUN=1',
                                  'KILL_TIMEOUT=%s' % (int(kill_timeout)),
                                  'PARENT_PID=$$',
                                  'echo "Starting at "$(date)',
                                  'echo "Will kill at "$(date -d "+$KILL_TIMEOUT seconds")',
                                  '(sleep $KILL_TIMEOUT && cmsRunPid=$(ps --ppid $PARENT_PID | grep cmsRun | awk \'{print $1}\') && echo "Killing PID $cmsRunPid" && kill -s SIGINT $cmsRunPid)&',
                                  'SLEEP_PID=$!']

                bash_file += ['',
                              '# Run generated config',
                              'REPORT_NAME=%s' % (report_name),
                              '# Run the cmsRun',
                              'cmsRun -e -j $REPORT_NAME %s || exit $? ;' % (config_filename),
                              '']

                if automatic_validation:
                    bash_file += ['kill $SLEEP_PID > /dev/null 2>& 1',
                                  '']

                # Parse report
                bash_file += [# '# Report %s' % (report_name),
                              # 'cat $REPORT_NAME',
                              # '',
                              '# Parse values from %s report' % (report_name),
                              'processedEvents=$(grep -Po "(?<=<Metric Name=\\"NumberEvents\\" Value=\\")(.*)(?=\\"/>)" $REPORT_NAME | tail -n 1)',
                              'producedEvents=$(grep -Po "(?<=<TotalEvents>)(\\d*)(?=</TotalEvents>)" $REPORT_NAME | tail -n 1)',
                              'threads=$(grep -Po "(?<=<Metric Name=\\"NumberOfThreads\\" Value=\\")(.*)(?=\\"/>)" $REPORT_NAME | tail -n 1)',
                              'peakValueRss=$(grep -Po "(?<=<Metric Name=\\"PeakValueRss\\" Value=\\")(.*)(?=\\"/>)" $REPORT_NAME | tail -n 1)',
                              'peakValueVsize=$(grep -Po "(?<=<Metric Name=\\"PeakValueVsize\\" Value=\\")(.*)(?=\\"/>)" $REPORT_NAME | tail -n 1)',
                              'totalSize=$(grep -Po "(?<=<Metric Name=\\"Timing-tstoragefile-write-totalMegabytes\\" Value=\\")(.*)(?=\\"/>)" $REPORT_NAME | tail -n 1)',
                              'totalSizeAlt=$(grep -Po "(?<=<Metric Name=\\"Timing-file-write-totalMegabytes\\" Value=\\")(.*)(?=\\"/>)" $REPORT_NAME | tail -n 1)',
                              'totalJobTime=$(grep -Po "(?<=<Metric Name=\\"TotalJobTime\\" Value=\\")(.*)(?=\\"/>)" $REPORT_NAME | tail -n 1)',
                              'totalJobCPU=$(grep -Po "(?<=<Metric Name=\\"TotalJobCPU\\" Value=\\")(.*)(?=\\"/>)" $REPORT_NAME | tail -n 1)',
                              'eventThroughput=$(grep -Po "(?<=<Metric Name=\\"EventThroughput\\" Value=\\")(.*)(?=\\"/>)" $REPORT_NAME | tail -n 1)',
                              'avgEventTime=$(grep -Po "(?<=<Metric Name=\\"AvgEventTime\\" Value=\\")(.*)(?=\\"/>)" $REPORT_NAME | tail -n 1)',
                              'if [ -z "$threads" ]; then',
                              '  echo "Could not find NumberOfThreads in report, defaulting to %s"' % (threads),
                              '  threads=%s' % (threads),
                              'fi',
                              'if [ -z "$eventThroughput" ]; then',
                              '  eventThroughput=$(bc -l <<< "scale=4; 1 / ($avgEventTime / $threads)")',
                              'fi',
                              'if [ -z "$totalSize" ]; then',
                              '  totalSize=$totalSizeAlt',
                              'fi',
                              'if [ -z "$processedEvents" ]; then',
                              '  processedEvents=$EVENTS',
                              'fi',
                              'echo "Validation report of %s sequence %s/%s"' % (prepid, index + 1, len(sequences)),
                              'echo "Processed events: $processedEvents"',
                              'echo "Produced events: $producedEvents"',
                              'echo "Threads: $threads"',
                              'echo "Peak value RSS: $peakValueRss MB"',
                              'echo "Peak value Vsize: $peakValueVsize MB"',
                              'echo "Total size: $totalSize MB"',
                              'echo "Total job time: $totalJobTime s"',
                              'echo "Total CPU time: $totalJobCPU s"',
                              'echo "Event throughput: $eventThroughput"',
                              'echo "CPU efficiency: "$(bc -l <<< "scale=2; ($totalJobCPU * 100) / ($threads * $totalJobTime)")" %"',
                              'echo "Size per event: "$(bc -l <<< "scale=4; ($totalSize * 1024 / $producedEvents)")" kB"',
                              'echo "Time per event: "$(bc -l <<< "scale=4; (1 / $eventThroughput)")" s"',
                              'echo "Filter efficiency percent: "$(bc -l <<< "scale=8; ($producedEvents * 100) / $processedEvents")" %"',
                              'echo "Filter efficiency fraction: "$(bc -l <<< "scale=10; ($producedEvents) / $processedEvents")'
                             ]

        if not for_validation and configs_to_upload:
            test_string = '--wmtest' if is_dev else ''
            bash_file += ['\n\n# Upload configs',
                          'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh',
                          'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}',
                          'if [[ $(head -n 1 `which cmsDriver.py`) =~ "python3" ]]; then',
                          '  python3 `which wmupload.py` %s -u pdmvserv -g ppd %s || exit $? ;' % (test_string, ' '.join(configs_to_upload)),
                          'else',
                          '  wmupload.py %s -u pdmvserv -g ppd %s || exit $? ;' % (test_string, ' '.join(configs_to_upload)),
                          'fi',
                         ]

        if dump_test_to_file:
            bash_file += ['',
                          '# End of %s file' % (test_file_name),
                          'EndOfTestFile',
                          '',
                          '# Make file executable',
                          'chmod +x %s' % (test_file_name),
                          '']

        if scram_arch_os == 'SLCern6':
            if for_validation:
                # Validation will run on CC7 machines (HTCondor, lxplus)
                # If it's CC7, just run the script normally
                # If it's SLC6, run it in slc6 singularity container
                bash_file += ['# Run in SLC6 container',
                              '# Mount afs, eos, cvmfs',
                              '# Mount /etc/grid-security for xrootd',
                              'export SINGULARITY_CACHEDIR="/tmp/$(whoami)/singularity"',
                              'singularity run -B /afs -B /eos -B /cvmfs -B /etc/grid-security --home $PWD:$PWD /cvmfs/unpacked.cern.ch/registry.hub.docker.com/cmssw/slc6:amd64 $(echo $(pwd)/%s)' % (test_file_name)]
            else:
                # Config generation for production run on CC7 machine - vocms0481
                # If it's CC7, just run the script normally
                # If it's SLC6, run it in slc6 singularity container
                bash_file += ['export SINGULARITY_CACHEDIR="/tmp/$(whoami)/singularity"',
                              'singularity run -B /afs -B /cvmfs -B /etc/grid-security --no-home /cvmfs/unpacked.cern.ch/registry.hub.docker.com/cmssw/slc6:amd64 $(echo $(pwd)/%s)' % (test_file_name)]

        # Empty line at the end of the file
        bash_file += ['']
        # self.logger.info('bash_file:\n%s' % ('\n'.join(bash_file)))
        return '\n'.join(bash_file)

    def change_priority(self, priority):
        """
        Change priority of all active workflows of the request
        """
        if self.get_attribute('priority') == priority:
            return True

        approval_status = self.get_approval_status()
        if approval_status == 'submit-done':
            return True

        if approval_status == 'submit-submitted':
            workflows = self.get_active_workflow_names()
            if workflows:
                loc = locator()
                self.logger.info('Will change %s priority to %s' % (workflows, priority))
                if loc.isDev():
                    cmsweb_url = 'https://cmsweb-testbed.cern.ch'
                else:
                    cmsweb_url = 'https://cmsweb.cern.ch'

                connection = ConnectionWrapper(host=cmsweb_url, keep_open=True)
                for workflow in workflows:
                    self.logger.info('Changing "%s" priority to %s', workflow, priority)
                    response = connection.api('PUT',
                                              '/reqmgr2/data/request/%s' % (workflow),
                                              {'RequestPriority': priority})
                    self.logger.debug(response)

                connection.close()

        self.set_attribute('priority', priority)
        self.update_history('priority', priority)

    def get_active_workflow_names(self):
        workflows = self.get('reqmgr_name')
        active_workflows = []
        rejected_status = {'aborted', 'aborted-archived', 'rejected', 'rejected-archived', 'failed'}
        for workflow in workflows:
            content = workflow.get('content')
            if not content:
                continue

            if content['pdmv_type'].lower() == 'resubmission':
                continue

            if set(content['pdmv_status_history_from_reqmngr']) & rejected_status:
                continue

            active_workflows.append(workflow['name'])

        return active_workflows

    def get_wmagent_type(self):
        if self.get_attribute('type') == 'Prod':
            if self.get_attribute('mcdb_id') == -1:
                if self.get_attribute('input_dataset'):
                    return 'MonteCarloFromGEN'
                else:
                    return 'MonteCarlo'
            else:
                return 'MonteCarloFromGEN'
        elif self.get_attribute('type') in ['LHE', 'LHEStepZero']:
            return 'LHEStepZero'
        elif self.get_attribute('type') == 'MCReproc':
            return 'ReDigi'

        return ''

    def get_actors(self, N=-1, what='author_username', Nchild=-1):
        # get the actors from itself, and all others it is related to
        actors = json_base.get_actors(self, N, what)
        crdb = database('chained_requests')
        lookedat = []
        # initiate the list with myself
        if Nchild == 0:
            return actors

        for cr in self.get_attribute('member_of_chain'):
            # this protection is bad against malformed db content. it should just fail badly with exception
            if not crdb.document_exists(cr):
                self.logger.error('For requests %s, the chain %s of which it is a member of does not exist.' % (
                    self.get_attribute('prepid'), cr))
                continue

            crr = crdb.get(cr)
            for (other_i, other) in enumerate(crr['chain']):
                # skip myself
                if other == self.get_attribute('prepid'):
                    continue
                if other in lookedat:
                    continue
                if Nchild > 0 and other_i > Nchild:
                    break
                rdb = database('requests')
                other_r = request(rdb.get(other))
                lookedat.append(other_r.get_attribute('prepid'))
                actors.extend(json_base.get_actors(other_r, N, what))

        actors = list(set(actors))
        return actors

    def test_failure(self, message, what='Submission', rewind=False, with_notification=True):
        if rewind:
            self.set_status(0)
            self.approve(0)

        self.update_history({'action': 'failed'})
        if with_notification:
            subject = '%s failed for request %s' % (what, self.get_attribute('prepid'))
            self.notify(subject, message)

        self.reload()

    def get_stats(self, forced=False):
        return
        stats_db = database('requests', url='http://vocms074.cern.ch:5984/')
        prepid = self.get_attribute('prepid')
        stats_workflows = stats_db.raw_query_view('_designDoc',
                                                  'requests',
                                                  page=0,
                                                  limit=1,
                                                  options={'key': prepid})
        mcm_reqmgr_list = self.get_attribute('reqmgr_name')
        mcm_reqmgr_name_list = [x['name'] for x in mcm_reqmgr_list]
        stats_reqmgr_name_list = [stats_wf['RequestName'] for stats_wf in stats_workflows]
        all_reqmgr_name_list = list(set(mcm_reqmgr_name_list).union(set(stats_reqmgr_name_list)))
        all_reqmgr_name_list = sorted(all_reqmgr_name_list, key=lambda workflow: '_'.join(workflow.split('_')[-3:]))
        # self.logger.debug('Stats workflows for %s: %s' % (self.get_attribute('prepid'),
        #                                                   dumps(list(stats_reqmgr_name_list), indent=2)))
        # self.logger.debug('McM workflows for %s: %s' % (self.get_attribute('prepid'),
        #                                                 dumps(list(mcm_reqmgr_name_list), indent=2)))
        # self.logger.debug('All workflows for %s: %s' % (self.get_attribute('prepid'),
        #                                                 dumps(list(all_reqmgr_name_list), indent=2)))
        new_mcm_reqmgr_list = []
        skippable_transitions = set(['rejected',
                                     'aborted',
                                     'failed',
                                     'rejected-archived',
                                     'aborted-archived',
                                     'failed-archived',
                                     'aborted-completed'])
        total_events = 0
        for reqmgr_name in all_reqmgr_name_list:
            stats_doc = None
            for stats_workflow in stats_workflows:
                if stats_workflow.get('RequestName') == reqmgr_name:
                    stats_doc = stats_workflow
                    break

            if not stats_doc and stats_db.document_exists(reqmgr_name):
                self.logger.info('Workflow %s is in Stats DB, but workflow does not have request %s in it\'s list' % (reqmgr_name,
                                                                                                                      self.get_attribute('prepid')))
                stats_doc = stats_db.get(reqmgr_name)

            if not stats_doc or not stats_db.document_exists(reqmgr_name):
                self.logger.warning('Workflow %s is in McM already, but not in Stats DB' % (reqmgr_name))
                new_mcm_reqmgr_list.append({'name': reqmgr_name,
                                            'content': {}})
                continue

            if stats_doc.get('RequestType', '').lower() != 'resubmission' and stats_doc.get('TotalEvents', 0) > 0:
                self.logger.info('TotalEvents %s', stats_doc['TotalEvents'])
                total_events = stats_doc['TotalEvents']

            stats_request_transition = stats_doc.get('RequestTransition', [])
            if not stats_request_transition:
                stats_request_transition = [{'Status': 'new', 'UpdateTime': 0}]

            status_history_from_reqmngr = [x['Status'] for x in stats_request_transition]
            if len(set(status_history_from_reqmngr).intersection(skippable_transitions)) > 0:
                self.logger.info('Adding empty %s because it has skippable status: %s' % (reqmgr_name, status_history_from_reqmngr))
                new_mcm_reqmgr_list.append({'name': reqmgr_name,
                                            'content': {}})
                continue

            submission_timestamp = stats_request_transition[0].get('UpdateTime', 0)
            last_update_timestamp = stats_doc.get('LastUpdate', 0)
            submission_date = time.strftime('%y%m%d', time.gmtime(submission_timestamp))
            submission_time = time.strftime('%H%M%S', time.gmtime(submission_timestamp))
            last_update_time = time.strftime('%a %b %d %H:%M:%S %Y', time.gmtime(last_update_timestamp))
            output_datasets = stats_doc.get('OutputDatasets', [])
            event_number_history = stats_doc.get('EventNumberHistory', [])
            dataset_name = output_datasets[0] if len(output_datasets) else ''
            dataset_statuses = {}
            events_in_das = 0
            status_in_das = 'NONE'
            open_evts_in_das = 0
            if event_number_history:
                event_number_history = event_number_history[-1]
                for dataset, content in event_number_history.get('Datasets', {}).iteritems():
                    dataset_statuses[dataset] = {'pdmv_evts_in_DAS': content.get('Events', 0),
                                                 'pdmv_status_in_DAS': content.get('Type', 'NONE'),
                                                 'pdmv_open_evts_in_DAS': 0}

                    if dataset == dataset_name:
                        events_in_das = dataset_statuses[dataset]['pdmv_evts_in_DAS']
                        status_in_das = dataset_statuses[dataset]['pdmv_status_in_DAS']
                        open_evts_in_das = dataset_statuses[dataset]['pdmv_open_evts_in_DAS']

            new_rr = {'name': reqmgr_name,
                      'content': {'pdmv_type': stats_doc.get('RequestType', ''),
                                  'pdmv_status_from_reqmngr': status_history_from_reqmngr[-1],
                                  'pdmv_dataset_name': dataset_name,
                                  'pdmv_prep_id': stats_doc.get('PrepID', ''),
                                  'pdmv_dataset_statuses': dataset_statuses,
                                  'pdmv_evts_in_DAS': events_in_das,
                                  'pdmv_dataset_list': output_datasets,
                                  'pdmv_submission_date': submission_date,
                                  'pdmv_status_in_DAS': status_in_das,
                                  'pdmv_present_priority': stats_doc.get('RequestPriority'),
                                  'pdmv_status_history_from_reqmngr': status_history_from_reqmngr,
                                  'pdmv_submission_time': submission_time,
                                  'pdmv_open_evts_in_DAS': open_evts_in_das,
                                  'pdmv_monitor_time': last_update_time}}

            new_mcm_reqmgr_list.append(new_rr)

        new_mcm_reqmgr_list = sorted(new_mcm_reqmgr_list, key=lambda workflow: '_'.join(workflow['name'].split('_')[-3:]))
        old_mcm_reqmgr_list_string = dumps(mcm_reqmgr_list, indent=2, sort_keys=True)
        new_mcm_reqmgr_list_string = dumps(new_mcm_reqmgr_list, indent=2, sort_keys=True)
        changes_happen = old_mcm_reqmgr_list_string != new_mcm_reqmgr_list_string
        # self.logger.debug('New workflows: %s' % (dumps(new_mcm_reqmgr_list, indent=2, sort_keys=True)))
        self.set_attribute('reqmgr_name', new_mcm_reqmgr_list)

        if len(new_mcm_reqmgr_list):
            tiers_expected = self.get_tiers()
            self.logger.debug('%s tiers expected: %s' % (self.get_attribute('prepid'), tiers_expected))
            collected = self.collect_outputs(new_mcm_reqmgr_list,
                                             tiers_expected,
                                             self.get_processing_strings(),
                                             self.get_attribute('dataset_name'),
                                             self.get_attribute('member_of_campaign'),
                                             skip_check=forced)

            self.logger.debug('Collected outputs for %s: %s' % (self.get_attribute('prepid'),
                                                                dumps(collected, indent=2, sort_keys=True)))

            # 1st element which is not DQMIO
            completed = 0
            if len(collected):
                # we find the first DS not DQMIO, if not possible default to 0th elem
                datasets_to_calc = next((el for el in collected if el.find("DQMIO") == -1), collected[0])
                (_, completed) = self.collect_status_and_completed_events(new_mcm_reqmgr_list, datasets_to_calc)
            else:
                self.logger.error('Could not calculate completed events for %s' % (self.get_attribute('prepid')))
                completed = 0

            keep_output = self.get_attribute("keep_output").count(True) > 0
            if keep_output:
                if self.get_attribute('completed_events') != completed:
                    self.set_attribute('completed_events', completed)
                    changes_happen = True

            self.logger.info('Completed events for %s: %s' % (self.get_attribute('prepid'),
                                                              completed))

            # we check if output_dataset managed to change.
            # ussually when request is assigned, but no evts are generated
            # we check for done status so we wouldn't be updating old requests with changed infrastructure
            # also we change it only if we keep any output in request
            output_dataset = self.get_attribute('output_dataset')
            if (output_dataset != collected) and (self.get_attribute('status') != 'done') and keep_output:
                self.logger.info('Stats update, DS differs. for %s' % (self.get_attribute("prepid")))
                self.set_attribute('output_dataset', collected)
                changes_happen = True

        crdb = database('chained_requests')
        rdb = database('requests')
        chained_requests = crdb.query_view('contains', self.get_attribute('prepid'), page_num=-1)
        for cr in chained_requests:
            chain = cr.get('chain', [])
            index_of_this_request = chain.index(self.get_attribute('prepid'))
            if index_of_this_request > -1 and index_of_this_request < len(chain) - 1:
                next_request = request(rdb.get(chain[index_of_this_request + 1]))
                if not next_request.get_attribute('input_dataset'):
                    input_dataset = self.get_ds_input(self.get_attribute('output_dataset'), next_request.get_attribute('sequences'))
                    next_request.set_attribute('input_dataset', input_dataset)
                    next_request.save()

        # Update priority if it changed
        if new_mcm_reqmgr_list:
            new_priority = new_mcm_reqmgr_list[-1].get('content', {}).get('pdmv_present_priority')
        else:
            new_priority = None

        if new_priority is not None and new_priority != self.get_attribute('priority'):
            self.set_attribute('priority', new_mcm_reqmgr_list[-1]['content']['pdmv_present_priority'])
            self.update_history({'action': 'wm priority',
                                 'step': new_mcm_reqmgr_list[-1]['content']['pdmv_present_priority']})

        # Update number of expected events
        if total_events != 0 and total_events != self.get_attribute('total_events'):
            self.logger.info('Total events changed %s -> %s for %s',
                             self.get_attribute('total_events'),
                             total_events,
                             self.get_attribute('prepid'))
            self.set_attribute('total_events', total_events)

        self.logger.info('Changes happen for %s - %s' % (self.get_attribute('prepid'), changes_happen))
        return changes_happen

    def get_input_dataset_status(self):
        input_dataset = self.get_attribute('input_dataset')
        if not input_dataset:
            return

        stats_db = database('requests', url='http://vocms074.cern.ch:5984/')
        stats_workflows = stats_db.raw_query_view('_designDoc',
                                                  'outputDatasets',
                                                  page=0,
                                                  limit=1,
                                                  options={'key': input_dataset})
        status = None
        prepid = self.get_attribute('prepid')
        self.logger.info('Found %s workflows with %s as output dataset' % (len(stats_workflows), input_dataset))
        if stats_workflows:
            workflow = stats_workflows[0]
            dataset_info = workflow.get('EventNumberHistory', [])
            dataset_info = [x for x in dataset_info if input_dataset in x.get('Datasets', {})]
            dataset_info = sorted(dataset_info, key=lambda x: x.get('Time', 0))
            for entry in reversed(dataset_info):
                if input_dataset in entry['Datasets']:
                    status = entry['Datasets'][input_dataset].get('Type')
                    self.logger.info('Status of input dataset %s of %s is %s' % (input_dataset,
                                                                                 prepid,
                                                                                 status))
                    break

        if status and status not in ('VALID',):
            self.logger.error('Input dataset %s of %s is %s' % (input_dataset, prepid, status))
            raise self.BadParameterValue('Input dataset of %s has status "%s" which is not allowed' % (prepid,
                                                                                                       status))

    def inspect(self, force=False):
        # this will look for corresponding wm requests, add them,
        # check on the last one in date and check the status of the output DS for -> done
        not_good = {"prepid": self.get_attribute('prepid'), "results": False}

        # only if you are in submitted status
        # later, we could inspect on "approved" and trigger injection
        if self.get_attribute('status') == 'submitted':
            return self.inspect_submitted(force=force)
        elif self.get_attribute('status') == 'approved':
            return self.inspect_approved()

        not_good.update({'message': 'cannot inspect a request in %s status'
                % (self.get_attribute('status'))})

        return not_good

    def inspect_approved(self):
        # try to inject the request
        not_good = {"prepid": self.get_attribute('prepid'), "results": False}
        db = database('requests')
        if self.get_attribute('approval') == 'approve':
            try:
                with locker.lock('{0}-wait-for-approval'.format(self.get_attribute('prepid'))):
                    self.approve()
                    saved = db.save(self.json())
                if saved:
                    return {"prepid": self.get_attribute('prepid'), "results": True}
                else:
                    not_good.update({'message': "Could not save the request after approve "})
                    return not_good
            except Exception as ex:
                not_good.update({'message': str(ex)})
                return not_good

        elif self.get_attribute('approval') == 'submit':
            # this is for automated retries of submissions of requests in approval/status submit/approved
            # this is a remnant of when submission was not done automatically on toggle submit approval
            # in the current paradigm, this automated is probably not necessary, as the failure might be genuine
            # and also, it interferes severly with chain submission
            # from tools.handlers import RequestInjector
            # threaded_submission = RequestInjector(prepid=self.get_attribute('prepid'), check_approval=False,
            #                                      lock=locker.lock(self.get_attribute('prepid')))
            # threaded_submission.start()
            # return {"prepid": self.get_attribute('prepid'), "results": True}
            return {"prepid": self.get_attribute('prepid'), "results": False}
        else:
            not_good.update({'message': 'Not implemented yet to inspect a request in %s status and approval %s' % (
                self.get_attribute('status'), self.get_attribute('approval'))})
            return not_good

    def collect_outputs(self, mcm_rr, tiers_expected, proc_strings, prime_ds, camp, skip_check=False):

        re_to_match = re.compile("/%s(.*)/%s(.*)\\-v(.*)/" % (prime_ds, camp))
        collected = []
        versioned = {}

        # make tiers and their priority hash_map to have O(1)
        tiers_hash_map = {}
        for t in tiers_expected:
            tiers_hash_map[t] = tiers_expected.index(t)

        for wma in mcm_rr:
            if 'content' not in wma or not wma['content']:
                continue
            if 'pdmv_dataset_list' not in wma['content']:
                continue
            those = wma['content']['pdmv_dataset_list']

            for ds in those:
                # we do all the DS-PS/TIER checks for the requests and last Step
                if re.match(re_to_match, ds) or skip_check:
                    # get current version
                    # 0th element is empty string of first /
                    # 1st is datset+process_string
                    # 2nd is version number
                    # 3rd is datatier
                    curr_v = re.split('(.*)\\-v(.*)/', ds)
                    # Do some checks
                    if not curr_v[-1] in tiers_expected and not skip_check:
                        continue

                    if not skip_check:
                        if not ds.split('/')[-2].split('-')[-2] in proc_strings:
                            # most likely there is a fake/wrong dataset
                            continue

                    # find and save the max version for the dataset
                    uniq_name = curr_v[1] + curr_v[-1]

                    # tier priority from has map, or max length if priority is not existing
                    if ds.split("/")[-1] not in tiers_hash_map:
                        tier_priority = len(tiers_hash_map)
                    else:
                        tier_priority = tiers_hash_map[(ds.split('/')[-1])]

                    if uniq_name in versioned:
                        if curr_v[-2] > versioned[uniq_name]["version"]:
                            versioned[uniq_name] = {
                                "version": curr_v[-2],
                                "full_dataset": ds,
                                "priority": tier_priority}
                    else:
                        versioned[uniq_name] = {
                            "version": curr_v[-2],
                            "full_dataset": ds,
                            "priority": tier_priority}
                else:
                    self.logger.info("collect_outputs didn't match anything for: %s" % (
                            self.get_attribute("prepid")))

        collected = [(versioned[el]["full_dataset"], versioned[el]["priority"]) for el in versioned]
        # sort by tier priority. 1st element is taken for events calculation
        collected.sort(key=itemgetter(1))

        # return only list of sorted datasets
        return [el[0] for el in collected]

    def collect_status_and_completed_events(self, mcm_rr, ds_for_accounting):
        counted = 0
        valid = True
        for wma in mcm_rr:
            if 'pdmv_dataset_statuses' not in wma['content']:
                if 'pdmv_dataset_name' in wma['content'] and wma['content']['pdmv_dataset_name'] == ds_for_accounting:
                    counted = max(counted, wma['content']['pdmv_evts_in_DAS'] + wma['content']['pdmv_open_evts_in_DAS'])
                    valid *= (wma['content']['pdmv_status_in_DAS'] == 'VALID')
                else:
                    continue
            elif ds_for_accounting in wma['content']['pdmv_dataset_statuses']:
                counted = max(counted, wma['content']['pdmv_dataset_statuses'][ds_for_accounting]['pdmv_evts_in_DAS'] + wma['content']['pdmv_dataset_statuses'][ds_for_accounting]['pdmv_open_evts_in_DAS'])
                valid *= (wma['content']['pdmv_dataset_statuses'][ds_for_accounting]['pdmv_status_in_DAS'] == 'VALID')
        return (valid,counted)

    def inspect_submitted(self, force):
        not_good = {"prepid": self.get_attribute('prepid'), "results": False}
        # get fresh up to date stats
        changes_happen = self.get_stats()
        mcm_rr = self.get_attribute('reqmgr_name')
        db = database('requests')
        ignore_for_status = settings.get_value('ignore_for_status')
        if len(mcm_rr):
            wma_r = mcm_rr[-1]  # the one used to check the status
            # pick up the last request of type!='Resubmission'
            for wma in reversed(mcm_rr):
                if ('content' in wma and 'pdmv_type' in wma['content'] and
                        not (wma['content']['pdmv_type'] in ignore_for_status)):
                    wma_r = wma  # the one to check the number of events in output
                    break

            if ('pdmv_status_in_DAS' in wma_r['content'] and
                    'pdmv_status_from_reqmngr' in wma_r['content']):

                if wma_r['content']['pdmv_status_from_reqmngr'] in ['announced', 'normal-archived']:
                    # this is enough to get all datasets
                    tiers_expected = self.get_tiers()
                    collected = self.collect_outputs(
                        mcm_rr, tiers_expected,
                        self.get_processing_strings(), self.get_attribute("dataset_name"),
                        self.get_attribute("member_of_campaign"),
                        skip_check=self.get_attribute("keep_output").count(True) == 0)

                    # collected as the correct order : in first place, there is what needs to be considered for accounting
                    if (not len(collected) and self.get_attribute("keep_output").count(True) > 0):
                        not_good.update({'message': 'No output dataset have been recognized'})
                        saved = db.save(self.json())
                        return not_good

                    # then pick up the first expected
                    ds_for_accounting = collected[0]
                    # find its statistics
                    valid, counted = self.collect_status_and_completed_events(mcm_rr, ds_for_accounting)

                    # we register output and events only if request keeps output.
                    if self.get_attribute("keep_output").count(True) > 0:
                        self.set_attribute('output_dataset', collected)
                        self.set_attribute('completed_events', counted)

                    if not valid:
                        not_good.update({'message' : 'Not all outputs are valid'})
                        saved = db.save(self.json())
                        return not_good

                    self.logger.info('Expected tiers of %s are %s' % (self.get_attribute('prepid'), tiers_expected))
                    # make sure no expected tier was left behind
                    if not force:
                        if not all(map(lambda t: any(map(lambda dn: t == dn.split('/')[-1],
                                collected)), tiers_expected)):

                            not_good.update({'message': 'One of the expected tiers %s has not been produced'
                                    % ( tiers_expected )})

                            saved = db.save(self.json())
                            return not_good

                    # in case it keeps any output and produced 0 events
                    # means something is wrong in production
                    if (self.get_attribute('completed_events') <= 0
                            and self.get_attribute("keep_output").count(True) > 0):

                        not_good.update({
                            'message': '%s completed but with no statistics. stats DB lag. saving the request anyway.' % (
                                    wma_r['content']['pdmv_dataset_name'])})

                        saved = db.save(self.json())
                        return not_good

                    if len(collected) == 0:
                        # there was no matching tier
                        not_good.update({'message': '%s completed but no tiers match any of %s' % (wma_r['content']['pdmv_dataset_name'], tiers_expected)})
                        saved = db.save(self.json())
                        return not_good
                        # set next status: which can only be done at this stage

                    self.set_status(with_notification=True)
                    # save the request back to db
                    saved = db.save(self.json())
                    if saved:
                        return {"prepid": self.get_attribute('prepid'), "results": True}
                    else:
                        not_good.update({'message': "Set status to %s could not be saved in DB" % (self.get_attribute('status'))})
                        return not_good
                else:
                    if changes_happen:
                        db.save(self.json())
                    not_good.update({'message': "last request %s is not ready" % (wma_r['name'])})
                    return not_good
            else:
                if changes_happen: db.save(self.json())
                not_good.update({'message': "last request %s is malformed %s" % (wma_r['name'],
                        wma_r['content'])})
                return not_good
        else:
            # add a reset acion here, in case in prod instance ?
            not_good.update({'message': " there are no requests in request manager. Please invsetigate!"})
            return not_good

    def parse_fragment(self):
        if self.get_attribute('fragment'):
            for line in self.get_attribute('fragment').split('\n'):
                yield line
        elif self.get_attribute('name_of_fragment') and self.get_attribute('fragment_tag'):
            # for line in os.popen('curl http://cmssw.cvs.cern.ch/cgi-bin/cmssw.cgi/CMSSW/%s?revision=%s'%(self.get_attribute('name_of_fragment'),self.get_attribute('fragment_tag') )).read().split('\n'):
            for line in os.popen(self.retrieve_fragment(get=False)).read().split('\n'):
                yield line
        else:
            for line in []:
                yield line

    def textified(self):
        l_type = locator()
        view_in_this_order = ['pwg',
                              'prepid',
                              'dataset_name',
                              'mcdb_id',
                              'notes',
                              'total_events',
                              'validation',
                              'approval',
                              'status',
                              'input_dataset',
                              'member_of_chain',
                              'reqmgr_name',
                              'completed_events']

        text = ''
        for view in view_in_this_order:
            value = self.get_attribute(view)
            if value:
                if isinstance(value, list) or isinstance(value, dict):
                    text += '%s: %s\n' % (view, dumps(value, indent=4))
                else:
                    text += '%s: %s\n' % (view, self.get_attribute(view))
        text += '\n'
        text += '%srequests?prepid=%s' % (l_type.baseurl(), self.get_attribute('prepid'))
        return text

    def target_for_test(self):
        """
        Return number of max events to run in validation
        """
        test_target = settings.get_value('test_target')
        total_events = self.get_attribute('total_events')
        return max(0, min(test_target, total_events))

    def get_efficiency_error(self, relative=True):
        if not self.get_attribute('generator_parameters'):
            return 0.
        match = float(self.get_attribute('generator_parameters')[-1]['match_efficiency_error'])
        filter_eff = float(self.get_attribute('generator_parameters')[-1]['filter_efficiency_error'])
        error = sqrt(match * match + filter_eff * filter_eff)

        if relative:
            eff = self.get_efficiency()
            if eff:
                return error / eff
            else:
                return 0.
        else:
            return error

    def get_efficiency(self):
        # use the trick of input_dataset ?
        if self.get_attribute('generator_parameters'):
            match = float(self.get_attribute('generator_parameters')[-1]['match_efficiency'])
            filter_eff = float(self.get_attribute('generator_parameters')[-1]['filter_efficiency'])
            return match * filter_eff
        return 1.

    def get_forward_efficiency(self, achain=None):
        chains = self.get_attribute('member_of_chain')
        myid = self.get_attribute('prepid')
        crdb = database('chained_requests')
        rdb = database('requests')
        max_forward_eff = 0.
        for cr in chains:
            if achain and cr != achain:
                continue
            forward_eff = None
            mcm_cr = crdb.get(cr)
            chain = mcm_cr['chain']
            chain = chain[chain.index(myid):]
            for r in chain:
                if r == myid:
                    continue
                mcm_r = request(rdb.get(r))
                an_eff = mcm_r.get_efficiency()
                if an_eff > 0:
                    if forward_eff:
                        forward_eff *= an_eff
                    else:
                        forward_eff = an_eff
            if forward_eff and forward_eff > max_forward_eff:
                max_forward_eff = forward_eff
        if bool(max_forward_eff):  # to check if its not 0. as it might trigger
            return max_forward_eff  # division by 0 in request_to_wma
        else:
            return 1

    def get_n_unfold_efficiency(self, target):
        if self.get_attribute('generator_parameters'):
            eff = self.get_efficiency()
            if eff != 0:
                target /= eff
        return int(target)

    def get_validation_max_runtime(self):
        """
        Return maximum number of seconds that job could run for, i.e. validation duration
        """
        multiplier = self.get_attribute('validation').get('time_multiplier', 1)
        max_runtime = settings.get_value('batch_timeout') * 60. * multiplier
        return max_runtime

    def get_event_count_for_validation(self, with_explanation=False):
        # Efficiency
        efficiency = self.get_efficiency()
        # Max number of events to run
        max_events = self.target_for_test()
        # Max events taking efficiency in consideration
        max_events_with_eff = max_events / efficiency
        # Max number of seconds that validation can run for
        max_runtime = self.get_validation_max_runtime()
        # "Safe" margin of validation that will not be used for actual running
        # but as a buffer in case user given time per event is slightly off
        margin = settings.get_value('test_timeout_fraction')
        # Time per event
        time_per_event = self.get_attribute('time_event')
        # Threads in sequences
        sequence_threads = [int(sequence.get('nThreads', 1)) for sequence in self.get_attribute('sequences')]
        while len(sequence_threads) < len(time_per_event):
            time_per_event = time_per_event[:-1]

        # Time per event for single thread
        single_thread_time_per_event = [time_per_event[i] * sequence_threads[i] for i in range(len(time_per_event))]
        # Sum of single thread time per events
        time_per_event_sum = sum(single_thread_time_per_event)
        # Max runtime with applied margin
        max_runtime_with_margin = max_runtime * (1.0 - margin)
        # How many events can be produced in given "safe" time
        events = int(max_runtime_with_margin / time_per_event_sum)
        # Try to produce at least one event
        clamped_events = int(max(1, min(events, max_events_with_eff)))
        # Estimate produced events
        estimate_produced = int(clamped_events * efficiency)

        self.logger.info('Events to run for %s - %s', self.get_attribute('prepid'), clamped_events)
        if not with_explanation:
            return clamped_events
        else:
            explanation = ['# Maximum validation duration: %ds' % (max_runtime),
                           '# Margin for validation duration: %d%%' % (margin * 100),
                           '# Validation duration with margin: %d * (1 - %.2f) = %ds' % (max_runtime, margin, max_runtime_with_margin),
                           '# Time per event for each sequence: %s' % (', '.join(['%.4fs' % (x) for x in time_per_event])),
                           '# Threads for each sequence: %s' % (', '.join(['%s' % (x) for x in sequence_threads])),
                           '# Time per event for single thread for each sequence: %s' % (', '.join(['%s * %.4fs = %.4fs' % (sequence_threads[i], time_per_event[i], single_thread_time_per_event[i]) for i in range(len(single_thread_time_per_event))])),
                           '# Which adds up to %.4fs per event' % (time_per_event_sum),
                           '# Single core events that fit in validation duration: %ds / %.4fs = %d' % (max_runtime_with_margin, time_per_event_sum, events),
                           '# Produced events limit in McM is %d' % (max_events),
                           '# According to %.4f efficiency, validation should run %d / %.4f = %d events to reach the limit of %s' % (efficiency, max_events, efficiency, max_events_with_eff, max_events),
                           '# Take the minimum of %d and %d, but more than 0 -> %d' % (events, max_events_with_eff, clamped_events),
                           '# It is estimated that this validation will produce: %d * %.4f = %d events' % (clamped_events, efficiency, estimate_produced)]
            return clamped_events, '\n'.join(explanation)

    def unique_string(self, step_i):
        # create a string that supposedly uniquely identifies the request configuration for step
        uniqueString = ''
        if self.get_attribute('fragment'):
            fragment_hash = hashlib.sha224(self.get_attribute('fragment')).hexdigest()
            uniqueString += fragment_hash
        if self.get_attribute('fragment_tag'):
            uniqueString += self.get_attribute('fragment_tag')
        if self.get_attribute('name_of_fragment'):
            uniqueString += self.get_attribute('name_of_fragment')
        if self.get_attribute('mcdb_id') >= 0 and self.get_attribute('type') in ['LHE', 'LHEStepZero']:
            uniqueString += 'mcdb%s' % (self.get_attribute('mcdb_id'))
        uniqueString += self.get_attribute('cmssw_release')
        seq = sequence(self.get_attribute('sequences')[step_i])
        uniqueString += seq.to_string()
        return uniqueString

    def configuration_identifier(self, step_i):
        uniqueString = self.unique_string(step_i)
        # create a hash value that supposedly uniquely defines the configuration
        hash_id = hashlib.sha224(uniqueString).hexdigest()
        return hash_id

    @staticmethod
    # another copy/paste
    def put_together(nc, fl, new_req):
        # copy the sequences of the flow
        sequences = []
        for i, step in enumerate(nc.get_attribute('sequences')):
            flag = False  # states that a sequence has been found
            for name in step:
                if name in fl.get_attribute('request_parameters')['sequences'][i]:
                    # if a seq name is defined, store that in the request
                    sequences.append(copy.deepcopy(step[name]))

                    # if the flow contains any parameters for the sequence,
                    # then override the default ones inherited from the campaign
                    if fl.get_attribute('request_parameters')['sequences'][i][name]:
                        for key in fl.get_attribute('request_parameters')['sequences'][i][name]:
                            sequences[-1][key] = fl.get_attribute('request_parameters')['sequences'][i][name][key]
                            # to avoid multiple sequence selection
                            # continue to the next step (if a valid seq is found)
                    flag = True
                    break

            # if no sequence has been found, use the default
            if not flag:
                sequences.append(copy.deepcopy(step['default']))

        new_req.set_attribute('sequences', sequences)
        # setup the keep output parameter
        keep = []
        for s in sequences:
            keep.append(False)

        if not nc.get_attribute('no_output'):
            keep[-1] = True

        new_req.set_attribute('keep_output', keep)
        # override request's parameters
        for key in fl.get_attribute('request_parameters'):
            if key == 'sequences':
                continue
            elif key == 'process_string':
                pass
            else:
                if key in new_req.json():
                    new_req.set_attribute(key, fl.get_attribute('request_parameters')[key])

    @staticmethod
    def transfer(current_request, next_request):
        to_be_transferred = ['dataset_name', 'generators', 'process_string', 'mcdb_id', 'notes', 'extension']
        for key in to_be_transferred:
            next_request.set_attribute(key, current_request.get_attribute(key))

    def get_parent_requests(self, chained_requests):
        """
        Return a list of requests that are considered as parents to the current
        request
        """
        if not chained_requests:
            return []

        chained_request = chained_requests[0]
        prepid = self.get_attribute('prepid')
        chain = chained_request['chain']
        if prepid not in chain:
            raise Exception('%s is not a member of %s' % (prepid, chained_request['prepid']))

        request_db = Database('requests')
        return request_db.bulk_get(chain[:chain.index(prepid)])

    def get_derived_requests(self, chained_requests):
        """
        Go through all chains that request is in and fetch requests that have
        current request as a parent
        Return a dictionary where key is chained request prepid and value is a
        list of request dictionaries
        """
        results = {}
        prepid = self.get_attribute('prepid')
        for chained_request in chained_requests:
            chain = chained_request['chain']
            if prepid not in chain:
                raise Exception('%s is not a member of %s' % (prepid, chained_request['prepid']))

            results[chained_request['prepid']] = chain[chain.index(prepid) + 1:]

        request_db = Database('requests')
        # Flatten list of lists and bulk fetch the requests
        requests = request_db.bulk_get(set(item for chain in results.values() for item in chain))
        requests = {r['prepid']: r for r in requests}
        results = {key: [requests[c] for c in chain] for key, chain in results.items()}
        return results

    def reset(self, soft=True):
        """
        Reset a request
        Hard reset resets to initial state
        Soft reset depends on current state, it's purpose is to move request
        back to a stable state (in case it is stuck)
        """
        user = User()
        role = user.get_role()
        approval_status = self.get_approval_status()
        # Check if soft reset can be done
        if soft and approval_status != 'submit-approved':
            raise Exception('Only submit-approved requests can be soft reset')

        # Check if user has permission to do the reset
        if approval_status == 'none-new':
            raise Exception('Request is already at initial state')
        elif approval_status in ('validation-validation', 'define-defined'):
            # Everyone can reset requests in none-new, validation-validation and
            # define-defined status
            pass
        elif approval_status == 'validation-new':
            raise Exception('Cannot reset a request that is being validated')
        elif approval_status == 'approve-approved':
            # Only GEN conveners and up can reset approve-approved
            if role < Role.GEN_CONVENER:
                username = user.get_username()
                raise Exception('%s is not allowed to reset approve-approved requests' % (username))
        elif approval_status in ('submit-approved', 'submit-submitted', 'submit-done'):
            if role < Role.PRODUCTION_MANAGER:
                username = user.get_username
                raise Exception('%s is not allowed to reset %s requests' % (username,
                                                                            approval_status))

        chained_requests = self.get_chained_requests()
        # Check if requests further down the chain are none-new
        derived_requests = self.get_derived_requests(chained_requests)
        for chain_prepid, requests in derived_requests.items():
            for request in requests:
                other_prepid = request['prepid']
                other_approval_status = '%s-%s' % (request['approval'], request['status'])
                if soft:
                    # Soft reset - enough that status is lower
                    if self.order.index(approval_status) <= self.order.index(other_approval_status):
                        raise Exception('%s status is %s' % (other_prepid, other_approval_status))
                else:
                    # Hard reset - status must be none-new
                    if other_approval_status != 'none-new':
                        raise Exception('%s in %s is not none-new' % (other_prepid, chain_prepid))

        prepid = self.get('prepid')
        if not soft:
            # Check if current step of chained requests is not further down
            for chained_request in chained_requests:
                if chained_request['step'] > chained_request['chain'].index(prepid):
                    chain_prepid = chained_request['prepid']
                    raise Exception('Current step of %s is after this request' % (chain_prepid))

        # Update stats in order to do more accurate invalidations
        self.get_stats()

        # Invalidations
        workflows_to_invalidate = set()
        datasets_to_invalidate = set()
        rejected_statuses = {'rejected', 'aborted', 'rejected-archived', 'aborted-archived'}
        # Iterate through workflows and collect workflow names and datasets
        for workflow in self.get_attribute('reqmgr_name'):
            content = workflow.get('content', {})
            workflow_statuses = set(content.get('pdmv_status_history_from_reqmngr', []))
            if not (workflow_statuses & rejected_statuses):
                # Add only if workflow was not rejected yet
                workflows_to_invalidate.add(workflow['name'])

            for dataset, dataset_info in content.get('pdmv_dataset_statuses', {}).items():
                if dataset_info.get('pdmv_status_in_DAS') not in {'DELETED', 'INVALID'}:
                    datasets_to_invalidate.add(dataset)

        # Sort workflows
        workflows_to_invalidate = sorted(list(workflows_to_invalidate),
                                         key=lambda s: '_'.join(s.split('_')[-3:]))
        # Sort datasets
        datasets_to_invalidate = sorted(list(datasets_to_invalidate))

        self.logger.info('Workflows/datasets to invalidate: %s/%s for %s',
                         len(workflows_to_invalidate),
                         len(datasets_to_invalidate),
                         prepid)
        if workflows_to_invalidate or datasets_to_invalidate:
            invalidation_db = Database('invalidations')
            with locker.lock('create-invalidations'):
                for workflow in workflows_to_invalidate:
                    if not invalidation_db.document_exists(workflow):
                        self.logger.info('Creating invalidation for %s of %s', workflow, prepid)
                        invalidation = Invalidation({'_id': workflow,
                                                     'object': workflow,
                                                     'type': 'request',
                                                     'status': 'new',
                                                     'prepid': prepid})
                        invalidation.save()

                for dataset in datasets_to_invalidate:
                    dataset = dataset.replace('/', '')
                    if not invalidation_db.document_exists(dataset):
                        self.logger.info('Creating invalidation for %s of %s', dataset, prepid)
                        invalidation = Invalidation({'_id': dataset,
                                                     'object': dataset,
                                                     'type': 'dataset',
                                                     'status': 'new',
                                                     'prepid': prepid})
                        invalidation.save()

        # Remove request from not-yet-announced batches
        batch_db = Database('batches')
        # Batches that have the request and are in status new
        batches = batch_db.search({'contains': prepid, 'status': 'new'}, limit=None)
        for batch_dict in batches:
            batch = Batch(batch_dict)
            batch.remove_request(prepid)
            if not batch.save():
                raise Exception('Cannot save %s batch to database' % (batch.get('prepid')))

        # Request attributes to reset
        self.set_attribute('completed_events', 0)
        self.set_attribute('reqmgr_name', [])
        self.set_attribute('config_id', [])
        self.set_attribute('output_dataset', [])

        # TODO: Delete configs from config database?
        # remove the configs doc hash in reset
        # hash_ids = database('configs')
        # for i in range(len(self.get_attribute('sequences'))):
        #     hash_id = self.configuration_identifier(i)
        #     if hash_ids.document_exists(hash_id):
        #         hash_ids.delete(hash_id)

        if soft:
            if approval_status == 'submit-approved':
                self.logger.info('Soft resetting %s', prepid)
                self.set_approval_status('approve', 'approved')
                self.update_history('soft_reset', '')
        else:
            self.logger.info('Resetting %s', prepid)
            self.set_approval_status('none', 'new')
            self.update_history('reset', '')

    def prepare_upload_command(self, cfgs, test_string):
        cmd = ''
        cmd += self.get_setup_file2(False, False, configs_to_upload=cfgs)
        self.inject_logger.info('Upload command:\n\n%s\n\n' % (cmd))
        return cmd

    def prepare_and_upload_config(self, execute=True):
        to_release = []
        config_db = database("configs")
        prepid = self.get_attribute('prepid')
        self.inject_logger = InjectionLogAdapter(logging.getLogger("mcm_inject"),
                {'handle': prepid})
        try:
            additional_config_ids = {}
            cfgs_to_upload = {}
            l_type = locator()
            dev = ''
            wmtest = ''
            if l_type.isDev():
                wmtest = '--wmtest'
            command = "#no command"
            if self.get_attribute('config_id'):  # we already have configuration ids saved in our request
                return command
            for i in range(len(self.get_attribute('sequences'))):
                hash_id = self.configuration_identifier(i)
                locker.acquire(hash_id)
                if config_db.document_exists(hash_id):  # cached in db
                    additional_config_ids[i] = config_db.get(hash_id)['docid']
                    locker.release(hash_id)
                else:  # has to be setup and uploaded to config cache
                    to_release.append(hash_id)
                    cfgs_to_upload[i] = "{0}{1}_{2}_cfg.py".format(prepid, dev, i + 1)
            if cfgs_to_upload:

                command = self.prepare_upload_command([cfgs_to_upload[i] for i in sorted(cfgs_to_upload)], wmtest)
                if execute:
                    with installer(prepid, care_on_existing=False):
                        request_arch = self.get_scram_arch()
                        if not request_arch:
                            self.logger.error('the release %s architecture is invalid' % self.get_attribute('member_of_campaign'))
                            self.test_failure('Problem with uploading the configurations. The release %s architecture is invalid' % self.get_attribute('member_of_campaign'), what='Configuration upload')
                            return False

                        machine_name = "vocms0481.cern.ch"
                        with ssh_executor(server=machine_name) as executor:
                            _, stdout, stderr = executor.execute(command)

                            if not stdout and not stderr:
                                self.logger.error('SSH error for request {0}. Could not retrieve outputs.'.format(prepid))
                                self.inject_logger.error('SSH error for request {0}. Could not retrieve outputs.'.format(prepid))
                                self.test_failure('SSH error for request {0}. Could not retrieve outputs.'.format(prepid),
                                                what='Configuration upload')
                                return False
                            output = stdout.read()
                            error = stderr.read()

                        if error and not output:  # money on the table that it will break
                            self.logger.error('Error in wmupload: {0}'.format(error))
                            self.test_failure('Error in wmupload: {0}'.format(error), what='Configuration upload')
                            if '.bashrc: Permission denied' in error:
                                raise AFSPermissionError(error)

                            return False
                        cfgs_uploaded = [l for l in output.split("\n") if 'DocID:' in l]

                        if len(cfgs_to_upload) != len(cfgs_uploaded):
                            self.logger.error(
                                'Problem with uploading the configurations. To upload: {0}, received doc_ids: {1}\nOutput:\n{2}\nError:\n{3}'.format(
                                    cfgs_to_upload, cfgs_uploaded, output, error))
                            self.inject_logger.error(
                                'Problem with uploading the configurations. To upload: {0}, received doc_ids: {1}\nOutput:\n{2}\nError:\n{3}'.format(
                                    cfgs_to_upload, cfgs_uploaded, output, error))
                            self.test_failure(
                                'Problem with uploading the configurations. To upload: {0}, received doc_ids: {1}\nOutput:\n{2}\nError:\n{3}'.format(
                                    cfgs_to_upload, cfgs_uploaded, output, error), what='Configuration upload')
                            return False

                        for i, line in zip(sorted(cfgs_to_upload),
                                           cfgs_uploaded):  # filling the config ids for request and config database with uploaded configurations
                            docid = line.split()[-1]
                            additional_config_ids[i] = docid
                            hash_id = self.configuration_identifier(i)
                            saved = config_db.save({"_id": hash_id, "docid": docid,
                                    "prepid": prepid, "unique_string": self.unique_string(i)})

                            to_release.remove(hash_id)
                            locker.release(hash_id)
                            if not saved:
                                self.inject_logger.error(
                                    'Could not save the configuration {0}'.format(self.configuration_identifier(i)))

                        self.inject_logger.info("Full upload result: {0}".format(output))
            if execute:
                sorted_additional_config_ids = [additional_config_ids[i] for i in additional_config_ids]
                self.inject_logger.info("New configs for request {0} : {1}".format(prepid, sorted_additional_config_ids))
                if not self.overwrite({'config_id': sorted_additional_config_ids}):
                    self.inject_logger.error('There was a problem overwriting the config_id %s for request %s' % (sorted_additional_config_ids, prepid))
                    self.logger.error('There was a problem overwriting the config_id %s for request %s' % (sorted_additional_config_ids, prepid))
                    return False
            return command
        finally:
            for i in to_release:
                locker.release(i)

    def get_events_per_lumi(self, num_cores):
        cdb = database('campaigns')
        camp = campaign(cdb.get(self.get_attribute("member_of_campaign")))
        evts_per_lumi = camp.get_attribute("events_per_lumi")
        if num_cores and num_cores > 1:
            if 'multicore' in evts_per_lumi:  # multicore value set for campaign
                return evts_per_lumi["multicore"]
            else:  # in case someone removed multicore from dict
                return int(num_cores) * int(evts_per_lumi["singlecore"])
        else:  # TO-DO what if singlecore is deleted from dict?
            return evts_per_lumi["singlecore"]

    def get_core_num(self):
        self.logger.info("calling get_core_num for:%s" % (self.get_attribute('prepid')))
        num = 1
        for seq in self.get_attribute('sequences'):
            local_num = 0
            if 'nThreads' in seq:
                local_num = seq['nThreads']
            if local_num > num:
                num = local_num

        return int(num)

    def get_list_of_steps(self, in_string):
        if isinstance(in_string, basestring):
            # in case sequence is defined as string -> legacy support
            return [el.split(":")[0] for el in in_string.split(",")]
        else:
            return [el.split(":")[0] for el in in_string]

    @staticmethod
    def do_datatier_selection(possible_inputs, __prev_outputs):
            # we check for every possible tier in prioritised possible inputs
            # we iterate on all generated unique previous outputs
            # if its a match -> we return

            __in_taskName = ""
            __in_InputModule = ""
            for possible in possible_inputs:
                 for taskName, tier in reversed(__prev_outputs):
                    for t in tier:
                        if t == possible:
                            return "%soutput" % (t), taskName
            # return empty values if nothing found
            return "", ""

    def sequences_cpu_efficiency(self, sequences):
        self.logger.info('Calculating eff %s', sequences)
        numerator = 0
        denominator = 0
        for seq in sequences:
            numerator += seq['cpu_efficiency'] * seq['time_per_event']
            denominator += seq['time_per_event']

        efficiency = float(numerator) / denominator
        self.logger.info('Eff %s', efficiency)
        return efficiency

    def sequences_filter_efficiency(self, sequences):
        efficiency = 1
        for seq in sequences:
            efficiency *= seq['filter_efficiency']

        return efficiency

    def request_to_tasks(self, base, depend):
        tasks = []
        settings_db = database('settings')
        __DT_prio = settings_db.get('datatier_input')["value"]
        validation_info = []
        for threads, sequences in self.get_attribute('validation').get('results', {}).items():
            if not isinstance(sequences, list):
                sequences = [sequences]

            for s in sequences:
                if 'estimated_events_per_lumi' not in s:
                    s['estimated_events_per_lumi'] = (28800 * s['filter_efficiency'] / s['time_per_event']) if s.get('time_per_event') else 0

            validation_info.append({'threads': int(threads),
                                    'cpu_efficiency': self.sequences_cpu_efficiency(sequences),
                                    'filter_efficiency': self.sequences_filter_efficiency(sequences),
                                    'events_per_lumi': min([s['estimated_events_per_lumi'] for s in sequences]),
                                    'sequences': sequences})

        self.logger.info('Validation info of %s:\n%s', self.get_attribute('prepid'), dumps(validation_info, indent=2, sort_keys=True))
        filter_efficiency = self.get_efficiency()
        if validation_info:
            # Average filter efficiency
            filter_efficiency = sum([x['filter_efficiency'] for x in validation_info]) / len(validation_info)
            filter_efficiency_threshold = 0.001
            if filter_efficiency < filter_efficiency_threshold:
                # If filter eff < 10^-3, then filter based on events/lumi first and choose highest cpu efficiency
                self.logger.info('Filter efficiency lower than %s (%s), choosing cores based on evens/lumi',
                                 filter_efficiency_threshold,
                                 filter_efficiency)
                validation_info = sorted([v for v in validation_info if v['events_per_lumi'] >= 45], key=lambda v: v['cpu_efficiency'])
                self.logger.info('Validation info after filter (by cpu eff) %s', dumps(validation_info, indent=2, sort_keys=True))
                if validation_info:
                    validation_info = validation_info[-1]
                else:
                    raise Exception('Cannot choose number of cores: %s' % (self.get_attribute('validation')))

            else:
                # If filter eff >= 10^-3, then choose highest number of threads where cpu efficiency is >= 70%
                validation_info = sorted(validation_info, key=lambda v: v['threads'])
                self.logger.info('Validation info (by threads) %s', dumps(validation_info, indent=2, sort_keys=True))
                cpu_efficiency_threshold = settings.get_value('cpu_efficiency_threshold')
                for thread_info in reversed(validation_info):
                    if thread_info['cpu_efficiency'] >= cpu_efficiency_threshold:
                        validation_info = thread_info
                        break
                else:
                    validation_info = validation_info[0]

            self.logger.info('Selected validation info: %s', dumps(validation_info, indent=2, sort_keys=True))

        memory = self.get_attribute('memory')
        sequences = self.get_attribute('sequences')
        sequence_count = len(sequences)
        # Add missing validation info for all sequences
        while validation_info and len(validation_info['sequences']) < sequence_count:
            validation_info['sequences'].append(validation_info['sequences'][-1])

        for sequence_index in range(sequence_count):
            sequence = sequences[sequence_index]
            threads = int(self.get_attribute('sequences')[sequence_index].get('nThreads', 1))
            size_per_event = self.get_attribute('size_event')[sequence_index]
            time_per_event = self.get_attribute('time_event')[sequence_index]
            if validation_info:
                # If there are multi-validation results, use them
                self.logger.info('Using multi-validation values')
                threads = validation_info['threads']
                size_per_event = validation_info['sequences'][sequence_index]['size_per_event'] / sequence_count
                time_per_event = validation_info['sequences'][sequence_index]['time_per_event'] / sequence_count
                peak_value_rss = validation_info['sequences'][sequence_index]['peak_value_rss']
                filter_efficiency = validation_info['sequences'][sequence_index]['filter_efficiency']
                # Safety margin +60%, +50%, +40%, +30%, +20%
                self.logger.info('Adding memory safety margin')
                if peak_value_rss < 4000:
                    peak_value_rss *= 1.6
                elif peak_value_rss < 6000:
                    peak_value_rss *= 1.5
                elif peak_value_rss < 8000:
                    peak_value_rss *= 1.4
                elif peak_value_rss < 10000:
                    peak_value_rss *= 1.3
                else:
                    peak_value_rss *= 1.2

                # Rounding up to next thousand MB
                memory = int(math.ceil(peak_value_rss / 1000.0) * 1000)
                self.logger.info('Rounding up memory GBs %.2fMB -> %.2fMB', peak_value_rss, memory)

            elif self.get_attribute('validation').get('peak_value_rss', 0) > 0:
                # Old way of getting PeakValueRSS
                peak_value_rss = self.get_attribute('validation')['peak_value_rss']
                if threads == 1 and memory == 2300 and peak_value_rss < 2000.0:
                    # If it is single core with memory 2300 and peak rss value < 2000, use 2000
                    memory = 2000

            task_dict = {
                "TaskName": "%s_%d" % (self.get_attribute('prepid'), sequence_index),
                "KeepOutput": True,
                "ConfigCacheID": None,
                "GlobalTag": sequences[sequence_index]['conditions'],
                "CMSSWVersion": self.get_attribute('cmssw_release'),
                "ScramArch": self.get_scram_arch(),
                "PrimaryDataset": self.get_attribute('dataset_name'),
                "AcquisitionEra": self.get_attribute('member_of_campaign'),
                "Campaign": self.get_attribute('member_of_campaign'),
                "ProcessingString": self.get_processing_string(sequence_index),
                "TimePerEvent": time_per_event,
                "SizePerEvent": size_per_event,
                "Memory": memory,
                "FilterEfficiency": filter_efficiency,
                "PrepID": self.get_attribute('prepid')}
            # check if we have multicore an it's not an empty string
            if 'nThreads' in sequence and sequence['nThreads']:
                task_dict["Multicore"] = threads

            if 'nStreams' in sequence and int(sequence['nStreams']) > 0:
                task_dict['EventStreams'] = int(sequence['nStreams'])

            __list_of_steps = self.get_list_of_steps(sequences[sequence_index]['step'])
            if len(self.get_attribute('config_id')) > sequence_index:
                task_dict["ConfigCacheID"] = self.get_attribute('config_id')[sequence_index]
            if len(self.get_attribute('keep_output')) > sequence_index:
                task_dict["KeepOutput"] = self.get_attribute('keep_output')[sequence_index]
            if self.get_attribute('pileup_dataset_name').strip():
                task_dict["MCPileup"] = self.get_attribute('pileup_dataset_name')
            # due to discussion in https://github.com/dmwm/WMCore/issues/7398
            if self.get_attribute('version') > 0:
                task_dict["ProcessingVersion"] = self.get_attribute('version')
            if self.get_attribute('pilot'):
                task_dict['pilot_'] = 'Pilot'

            if sequence_index == 0:
                if base:
                    if self.get_attribute('events_per_lumi') > 0:
                        events_per_lumi = self.get_attribute('events_per_lumi')
                        self.logger.info('Using custom events per lumi for %s: %s' % (self.get_attribute('prepid'), events_per_lumi))
                    else:
                        events_per_lumi = self.get_events_per_lumi(task_dict.get("Multicore", None))

                    task_dict.update({
                        "SplittingAlgo": "EventBased",
                        "RequestNumEvents": self.get_attribute('total_events'),
                        "Seeding": "AutomaticSeeding",
                        "EventsPerLumi": events_per_lumi,
                        "LheInputFiles": self.get_attribute('mcdb_id') > 0})
                    # temporary work-around for request manager not creating enough jobs
                    # https://github.com/dmwm/WMCore/issues/5336
                    # inflate requestnumevents by the efficiency to create enough output
                    max_forward_eff = self.get_forward_efficiency()
                    task_dict["EventsPerLumi"] /= task_dict["FilterEfficiency"] # should stay nevertheless as it's in wmcontrol for now
                    task_dict["EventsPerLumi"] /= max_forward_eff # this does not take its own efficiency
                else:
                    if depend:
                        task_dict.update({
                            "SplittingAlgo": "EventAwareLumiBased",
                            "InputFromOutputModule": None,
                            "InputTask": None})
                    else:
                        task_dict.update({
                            "SplittingAlgo": "EventAwareLumiBased",
                            "InputDataset": self.get_attribute('input_dataset'),
                            "RequestNumEvents": self.get_attribute("total_events")})
            else:
                # here we select the appropriate DATATier from previous step
                # in case -step tier1,tier2,tier3 and
                __curr_first_step = __list_of_steps[0]
                __prev_tiers = [(tasks[-1]["TaskName"], tasks[-1]["_output_tiers_"])]
                tModule = tName = ""
                if __curr_first_step in __DT_prio:
                    # if 1st step is defined in DataTier priority dictionary
                    self.logger.debug("do_datatier_selection input:\n%s %s" % (__DT_prio[__curr_first_step], __prev_tiers))
                    tModule, tName = request.do_datatier_selection(__DT_prio[__curr_first_step], __prev_tiers)
                if tModule != "" and tName != "":
                    task_dict.update({
                        "SplittingAlgo": "EventAwareLumiBased",
                        "InputFromOutputModule": tModule,
                        "InputTask": tName})
                else:
                    # fallback solution
                    task_dict.update({"SplittingAlgo": "EventAwareLumiBased",
                        "InputFromOutputModule": tasks[-1]['output_'],
                        "InputTask": tasks[-1]['TaskName']})
            task_dict['_first_step_'] = __list_of_steps[0]
            task_dict['_output_tiers_'] = sequences[sequence_index]["eventcontent"]
            task_dict['output_'] = "%soutput" % (sequences[sequence_index]['eventcontent'][0])
            task_dict['priority_'] = self.get_attribute('priority')
            task_dict['request_type_'] = self.get_wmagent_type()

            tasks.append(task_dict)
        return tasks

    def get_sum_time_events(self):
        """
        return sum of time_events for request
        """
        return sum(self.get_attribute("time_event"))

    def get_sum_size_events(self):
        """
        return sum of size_events for request
        """
        return sum(self.get_attribute("size_event"))

    def any_negative_events(self, field):
        """
        return True if there is a negative or zero value in time_event/size_event list
        """
        return any(n <= 0 for n in self.get_attribute(field))

    def get_gen_script_output(self):
        prepid = self.get_attribute('prepid')
        campaign = self.get_attribute('member_of_campaign')
        filename = '%s.log' % (prepid)
        eos_path = '/eos/cms/store/group/pdmv/mcm_gen_checking_script'
        l_type = locator()
        if l_type.isDev():
            eos_path += '_dev'

        command = ''
        command += 'export EOS_MGM_URL=root://eoscms.cern.ch\n'
        command += 'eos cp %s/%s/%s /tmp\n' % (eos_path, campaign, filename)
        command += 'if [ $? -ne 0 ]; then\n'
        command += '    echo "Error getting checking script output. Either output does not exist or log fetch from EOS failed"\n'
        command += 'else\n'
        command += '    cat /tmp/%s\n' % (filename)
        command += '    rm /tmp/%s\n' % (filename)
        command += 'fi\n'
        result = str(os.popen(command).read())
        return result



