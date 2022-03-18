import os
import re
import hashlib
import time
import json
import logging
import math
from operator import itemgetter

from couchdb_layer.mcm_database import database as Database
from json_layer.chained_campaign import ChainedCampaign
from json_layer.invalidation import Invalidation
from json_layer.json_base import json_base
from json_layer.campaign import Campaign
from json_layer.flow import Flow
from json_layer.batch import Batch
from json_layer.generator_parameters import generator_parameters
from json_layer.sequence import Sequence
from tools.locator import locator
from tools.installer import installer
from tools.settings import Settings
from tools.locker import locker
from tools.logger import InjectionLogAdapter
from tools.utils import cmssw_setup, get_scram_arch as fetch_scram_arch, get_workflows_from_stats, get_workflows_from_stats_for_prepid, run_commands_in_singularity, sort_workflows_by_name
from tools.connection_wrapper import ConnectionWrapper
from json_layer.user import User, Role


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
        'fragment_name': '',
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
        'validation': {},
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
        is_gen_convener = user_role >= Role.GENERATOR_CONVENER
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
            if not 500 <= memory_per_core <= 4000:
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

    def get_chained_requests(self, only_enabled=False):
        """
        Return chained request dicts that this request is member of
        """
        chained_request_ids = self.get_attribute('member_of_chain')
        if not chained_request_ids:
            return []

        from json_layer.chained_request import ChainedRequest
        chained_request_db = ChainedRequest.get_database()
        chains = chained_request_db.bulk_get(chained_request_ids)
        if only_enabled:
            self.logger.info('Filtering out disabled chained requests, including chained campaigns')
            chains = [c for c in chains if c['enabled']]
            chained_campaign_ids = [c['member_of_campaign'] for c in chains]
            self.logger.debug('Fetching %s chained campaigns to check if enabled',
                              len(chained_campaign_ids))
            chained_campaigns = {c: ChainedCampaign.fetch(c) for c in chained_campaign_ids}
            enabled = []
            for chain in chains:
                if chained_campaigns[chain['member_of_campaign']].get('enabled'):
                    enabled.append(chain)

            chains = enabled

        return chains

    def get_parent_request(self):
        """
        Return request dictionary that is input for the current request or None
        if it does not exist
        """
        flown_with = self.get('flown_with')
        if not flown_with:
            # This is a root request
            return None

        chained_request_ids = self.get_attribute('member_of_chain')
        if not chained_request_ids:
            # Not member of any chains
            return None

        prepid = self.get_attribute('prepid')
        from json_layer.chained_request import ChainedRequest
        chained_request_db = ChainedRequest.get_database()
        # Take first chained request as all of them should be identical
        chained_request = chained_request_db.get(chained_request_ids[0])
        index = chained_request['chain'].index(prepid)
        if index == 0:
            return None

        parent_prepid = chained_request['chain'][index - 1]
        parent = self.get_database().get(parent_prepid)
        self.logger.debug('Parent request for %s is %s', prepid, parent_prepid)
        return parent

    def get_parent_requests(self):
        """
        Return a list of request dictionaries that are parents and grandparents
        to the current request of empty list if they do not exist
        """
        flown_with = self.get('flown_with')
        if not flown_with:
            # This is a root request
            return []

        chained_request_ids = self.get_attribute('member_of_chain')
        if not chained_request_ids:
            # Not member of any chains
            return []

        prepid = self.get_attribute('prepid')
        from json_layer.chained_request import ChainedRequest
        chained_request_db = ChainedRequest.get_database()
        # Take first chained request as all of them should be identical
        chained_request = chained_request_db.get(chained_request_ids[0])
        index = chained_request['chain'].index(prepid)
        if index == 0:
            return []

        parent_prepids = chained_request['chain'][:index]
        parents = self.get_database().bulk_get(parent_prepids)
        self.logger.debug('Parent requests for %s are %s',
                          prepid,
                          ','.join(p.get('prepid') for p in parents))
        return parents

    def get_derived_requests(self):
        """
        Go through all chains that request is in and fetch requests that have
        current request as a parent
        Return a dictionary where key is chained request prepid and value is a
        list of request dictionaries
        """
        results = {}
        prepid = self.get_attribute('prepid')
        for chained_request in self.get_chained_requests():
            chain = chained_request['chain']
            if prepid not in chain:
                raise Exception('%s is not a member of %s' % (prepid, chained_request['prepid']))

            further_chain = chain[chain.index(prepid) + 1:]
            results[chained_request['prepid']] = self.get_database().bulk_get(further_chain)

        return results

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
        return f'{approval}-{status}'

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
            self.logger.info('Request %s is in validation bypass list and is moved to approved',
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
            if user_role != Role.GENERATOR_CONVENER and user_role < Role.PRODUCTION_EXPERT:
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
        self.check_status_of_parents(chained_requests)
        self.check_with_previous(True)
        self.get_input_dataset_status()
        self.reload()

    def check_for_collisions(self):
        """
        Check if there are any other requests that have same dataset name, same
        campaign, same processing string and datatier
        Ignore none-new requests
        """
        request_db = self.get_database()
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
            raise Exception(f'There are {len(invalidations)} unacknowledged '
                            f'invalidations for {prepid}')

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
        previous_request = self.get_parent_request()
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

    def check_status_of_parents(self):
        """
        Go through all chains that request is in and check if requests that are
        leading to this request are in greater or equal status
        """
        parents = self.get_parent_requests()
        approval_status = self.get_approval_status()
        for parent in parents:
            parent_approval_status = f'{parent["approval"]}-{parent["status"]}'
            if self.order.index(parent_approval_status) < self.order.index(approval_status):
                parent_prepid = parent.get('prepid')
                raise Exception(f'{parent_prepid} status is {parent_approval_status} '
                                f'which is lower than {approval_status}')

    def to_be_submitted_together(self):
        """
        Return dictionary of chained requests and their requests that should be
        submitted togetger with this request
        """
        chained_requests = self.get_chained_requests(only_enabled=True)
        request_db = Request.get_database()
        flow_db = Flow.get_database()
        cache = {}
        def get_flow(prepid):
            if prepid not in cache:
                cache[prepid] = flow_db.get(prepid)

            return cache[prepid]

        def get_request(prepid):
            if prepid not in cache:
                cache[prepid] = request_db.get(prepid)

            return cache[prepid]

        prepid = self.get('prepid')
        together = {c['prepid']: [prepid] for c in chained_requests}
        # Just in case, in order not to run into infinite loop
        max_iterations = max(len(c['chain']) for c in chained_requests) + 1
        # Tuples - (chained request, current prepid)
        chained_requests = [(c, prepid) for c in chained_requests]
        while chained_requests and max_iterations > 0:
            max_iterations -= 1
            # Remove chained requests that don't have any further requests
            chained_requests = [c for c in chained_requests if c[0]['chain'][-1] != c[1]]
            if not chained_requests:
                break

            current_request_chains_flows = {}
            # Get (chained request, next request prepid and next flow approval)
            # Group them by current request
            for chained_request, current_prepid in chained_requests:
                chain = chained_request['chain']
                next_prepid = chain[chain.index(current_prepid) + 1]
                self.logger.info('Request after %s -> %s', current_prepid, next_prepid)
                next_request = get_request(next_prepid)
                next_flow = get_flow(next_request['flown_with'])
                next_approval = next_flow['approval']
                current_request_chains_flows.setdefault(current_prepid, []).append((chained_request,
                                                                                    next_prepid,
                                                                                    next_approval))

            # Go through groups and either take all chained requests or pick one
            # if there are at least one together_unique flow
            new_chained_requests = []
            for current_prepid, chains_requests_flows in current_request_chains_flows.items():
                self.logger.debug('%s group:', current_prepid)

                # Try to find together_unique first
                for chain_request_flow in chains_requests_flows:
                    chained_request, next_request, next_approval = chain_request_flow
                    if next_approval == 'together_unique':
                        self.logger.debug('   (%s) %s', next_approval, next_request)
                        # Add all chained requests that have next request
                        for chained_request, _, _ in chains_requests_flows:
                            if next_request in chained_request['chain']:
                                new_chained_requests.append((chained_request, next_request))

                        break
                else:
                    # No together_unique found - add all that have flow 'together'
                    for chain_request_flow in chains_requests_flows:
                        chained_request, next_request, next_approval = chain_request_flow
                        if next_approval == 'together':
                            self.logger.debug('   (%s) %s', next_approval, next_request)
                            new_chained_requests.append((chained_request, next_request))

            chained_requests = new_chained_requests
            for chained_request, next_request in chained_requests:
                together[chained_request['prepid']].append(next_request)

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
        self.check_status_of_parents(chained_requests)

        # TODO: Allow users to aprove only current steps of chain, only
        # submission or flowing code can approve otherwise
        chained_requests = [c for c in chained_requests if c['enabled']]
        previous_request = self.get_parent_request()
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

    def retrieve_fragment_command(self):
        """
        Return a list of bash commands that would download required fragment
        and rebuild the CMSSW
        """
        fragment_name = self.get_fragment_name()
        if not fragment_name:
            return []

        bash = ['# Get fragment',
                f'cd $CMSSW_SRC',
                f'mkdir -p $(dirname {fragment_name})']
        fragment = self.get('fragment')
        if fragment:
            prepid = self.get('prepid')
            url = f'{locator().baseurl()}public/restapi/requests/get_fragment/{prepid}'
        else:
            tag = self.get_attribute('fragment_tag')
            url = 'https://raw.githubusercontent.com/cms-sw/genproductions/'
            if tag:
                url += '{tag}/python/'
            else:
                url += 'master/genfragments/'

            url += fragment_name.replace('Configuration/GenProduction/', '').replace('python/', '')

        bash += [f'wget {url} --quiet -O {fragment_name}']
        bash += [f'[ -s {fragment_name} ] || exit $?;',
                 '',
                 '# Check if fragment contais gridpack path ant that it is in cvmfs',
                 f'if grep -q "gridpacks" {fragment_name}; then',
                 f'  if ! grep -q "/cvmfs/cms.cern.ch/phys_generator/gridpacks" {fragment_name}; then',
                 '    echo "Gridpack inside fragment is not in /cvmfs"',
                 '    exit 1',
                 '  fi',
                 'fi',
                 '',
                 '# Rebuild CMSSW with new fragment',
                 'scram b',
                 'cd $ORG_PWD']

        return bash

    def get_fragment_name(self):
        """
        Return a fragment name
        """
        fragment_name = self.get('name_of_fragment')
        fragment = self.get('fragment')
        prepid = self.get('prepid')
        if fragment and not fragment_name:
            fragment_name = f'Configuration/GenProduction/python/{prepid}-fragment.py'

        if fragment_name and not fragment_name.startswith('Configuration/GenProduction/python/'):
            fragment_name = f'Configuration/GenProduction/python/{fragment_name}'

        return fragment_name

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
        Get scram arch of the request release
        """
        if hasattr(self, 'scram_arch'):
            return self.scram_arch

        self.scram_arch = fetch_scram_arch(self.get_attribute('cmssw_release'))
        return self.scram_arch

    def run_gen_script(self):
        """
        Return whether GEN checking script should be run during validation
        """
        sequence_steps = []
        for seq in self.get_attribute('sequences'):
            for st in seq.get('step', []):
                sequence_steps.extend([x.strip() for x in st.split(',') if x.strip()])

        sequence_steps = set(sequence_steps)
        gen_script_steps = set(('GEN', 'LHE', 'FSPREMIX'))
        should_run = bool(sequence_steps & gen_script_steps)
        return should_run

    def get_cmsdrivers(self):
        """
        Return all cmsDrivers of a request, with information available in
        sequences
        No filein, fileout, python_filename, addMonitoring, etc.
        """
        sequences = [Sequence(s) for s in self.get('sequences')]
        pileup_dataset_name = self.get('pileup_dataset_name')
        return [s.get_cmsdriver(None, pileup_dataset_name, None) for s in sequences]

    def get_input_file_for_sequence(self, sequence_index):
        """
        Return input file name for a sequence at given index
        """
        prepid = self.get_attribute('prepid')
        if sequence_index > 0:
            # Input is output of previous sequence
            return f'file:{prepid}_{sequence_index-1}.root'

        # First sequence can have (checked in following order):
        # * output from previous request (if any)
        # * mcdb input
        # * input_dataset attribute
        # * no input file
        # Get all chained requests and look for previous request
        parent = self.get_parent_request()
        if parent:
            return f'file:{parent.get("prepid")}.root'

        mcdb_id = self.get('mcdb_id')
        if mcdb_id > 0:
            return f'"lhe:{mcdb_id}"'

        input_dataset = self.get('input_dataset')
        if input_dataset:
            return f'"dbs:{input_dataset}"'

        return ''

    def get_output_file_for_sequence(self, sequence_index):
        """
        Return output file name for a sequence at given index
        """
        prepid = self.get_attribute('prepid')
        if sequence_index != len(self.get('sequences')) - 1:
            # Add sequence index if this is not the last index
            return f'file:{prepid}_{sequence_index}.root'

        return f'file:{prepid}.root'

    def get_gen_script_command(self, automatic_validation, dev, prepid, campaign):
        """
        Return a list of bash commands to run GEN checking script
        """
        # Download the script
        bash = ['# GEN Script begin',
                'rm -f request_fragment_check.py',
                'wget -q https://raw.githubusercontent.com/cms-sw/genproductions/'
                'master/bin/utils/request_fragment_check.py',
                'chmod +x request_fragment_check.py']
        command = f'./request_fragment_check.py --bypass_status --prepid {prepid}'
        if dev:
            # Add --dev, so script would use McM DEV
            command += ' --dev'

        if automatic_validation:
            eos_path = '/eos/cms/store/group/pdmv/mcm_gen_checking_script'
            if dev:
                eos_path += '_dev'

            eos_path += f'/{campaign}'
            bash += [f'eos mkdir -p "{eos_path}"']
            command += f' > {prepid}_newest.log 2>&1'

        # Execute the GEN script
        bash += [command,
                 'GEN_ERR=$?']
        if automatic_validation:
            bash += [f'eos cp {eos_path}/{prepid}.log . 2>/dev/null',
                     f'touch {prepid}.log',
                     f'cat {prepid}_newest.log >> {prepid}.log',
                     f'echo "" >> {prepid}.log',
                     f'echo "" >> {prepid}.log',
                     f'eos cp {prepid}.log {eos_path}/{prepid}.log',
                     'echo "--BEGIN GEN Request checking script output--"',
                     f'cat {prepid}_newest.log',
                     'echo "--END GEN Request checking script output--"',
                     '']

        # Check exit code of script
        bash += ['if [ $GEN_ERR -ne 0 ]; then',
                 '  echo "GEN Checking Script exit with code $GEN_ERR - there are $GEN_ERR errors"',
                 '  echo "Validation WILL NOT RUN"',
                 '  echo "Please correct errors in the request and run validation again"',
                 '  exit $GEN_ERR',
                 'fi',
                 # If error code is zero, continue to validation
                 'echo "Running VALIDATION. GEN Request Checking Script returned no errors"',
                 '# GEN Script end']

        return bash

    def release_gte(self, cmssw_release):
        """
        Return whether request's CMSSW release is greater or equal to given one
        """
        my_release = self.get('cmssw_release')
        my_release = tuple(int(x) for x in re.sub('[^0-9_]', '', my_release).split('_') if x)
        other_release = tuple(int(x) for x in re.sub('[^0-9_]', '', cmssw_release).split('_') if x)
        # It only compares major and minor version, does not compare the build,
        # i.e. CMSSW_X_Y_Z, it compares only X and Y parts
        # Why? Because it was like this for ever
        my_release = my_release[:3]
        other_release = other_release[:3]
        return my_release >= other_release

    def get_setup_file(self, for_submission, for_test, for_validation, threads=1, configs_to_upload=None):
        loc = locator()
        dev = loc.isDev()
        prepid = self.get_attribute('prepid')
        campaign_id = self.get_attribute('member_of_campaign')

        bash_file = ['#!/bin/bash', '']
        if for_submission or for_validation:
            bash_file += ['#############################################################',
                          '#   This script is used by McM when it performs automatic   #',
                          '#  validation in HTCondor or submits requests to computing  #',
                          '#      !!! THIS FILE IS NOT MEANT TO BE RUN BY YOU !!!      #',
                          '#############################################################',
                          '',
                          'if [[ "$USER" != "pdmvserv" ]]; then',
                          '  echo "You should not be running this"',
                          '  exit 1',
                          'fi',
                          '']

        if for_submission:
            directory = '/afs/cern.ch/cms/PPD/PdmV/work/McM/submit'
            if dev:
                directory += '_dev'

            bash_file += [f'cd {directory}',
                          f'rm -rf {prepid}',
                          f'mkdir {prepid}',
                          '']

        sequences = self.get_attribute('sequences')
        sequence_names = [f'{prepid}_{i}_{threads}' for i in range(len(sequences))]
        report_names = [f'{name}_report.xml' for name in sequence_names]
        if for_validation:
            bash_file += [f'touch {report}' for report in report_names]
            bash_file += ['']

        run_gen_script = (for_validation or for_test) and self.run_gen_script() and threads == 1
        self.logger.info('Should %s run GEN script: %s', prepid, run_gen_script)
        if run_gen_script:
            bash_file += self.get_gen_script_command(for_validation, dev, prepid, campaign_id)
            bash_file += ['']

        if for_validation:
            bash_file += ['# Extract and print CPU name and hypervisor name',
                          'cpu_name=$(lscpu | grep "Model name" | head -n 1 '
                          '| sed "s/Model name: *//g")',
                          'hypervisor_name=$(lscpu | grep "Hypervisor vendor" | head -n 1 '
                          '| sed "s/Hypervisor vendor: *//g")',
                          'echo "CPU_NAME=$cpu_name ($hypervisor_name)"',
                          '']

        # Set up CMSSW environment
        script = ['# Setup CMSSW environment']
        script += cmssw_setup(self.get('cmssw_release')).split('\n')

        # Get the fragment if need to
        script += ['']
        script += self.retrieve_fragment_command()
        script += ['']
        if for_validation or for_submission:
            script += ['# Make voms proxy',
                       'voms-proxy-init --voms cms --out $(pwd)/voms_proxy.txt --hours 4',
                       'export X509_USER_PROXY=$(pwd)/voms_proxy.txt',
                       '']

        if for_validation:
            script += ['export HOME=$(pwd)', '']

        # Events to run
        event_command = self.get_validation_event_command()
        script += event_command

        # Random seed for wmLHEGS requests
        if 'wmlhegs' in prepid.lower():
            script += ['# Random seed between 1 and 100 for externalLHEProducer',
                       'SEED=$(($(date +%s) % 100 + 1))',
                       '']

        fragment_name = self.get_fragment_name()
        parsing = []
        for index, sequence_dict in enumerate(sequences):
            sequence = Sequence(data=sequence_dict)
            seq_update = {}
            seq_update['filein'] = self.get_input_file_for_sequence(index)
            seq_update['fileout'] = self.get_output_file_for_sequence(index)
            config_name = f'{prepid}_{index}_cfg.py'
            report_name = f'{prepid}_{index}_{threads}.xml'
            seq_update['python_filename'] = config_name
            # Always add Utils.addMonitoring to customise
            seq_update['customise'] = sequence_dict['customise']
            if seq_update['customise']:
                seq_update['customise'] += ','

            seq_update['customise'] += 'Configuration/DataProcessing/Utils.addMonitoring'
            # If there is wmlhegs in the prepid, add random initial seed
            seq_update['customise_commands'] = sequence_dict['customise_commands']
            if 'wmlhegs' in prepid.lower():
                if seq_update['customise_commands']:
                    seq_update['customise_commands'] += '; '

                seq_update['customise_commands'] += 'process.RandomNumberGeneratorService.externalLHEProducer.initialSeed="int(${SEED})"'
            # If it is a root request and CMSSW release >= 9.3.0, then add
            # events per lumi to customise_commands
            if index == 0 and not self.get('flown_with') and self.release_gte('9_3_0'):
                events_per_lumi = self.get_events_per_lumi(threads)
                events_per_lumi /= self.get_efficiency()
                events_per_lumi = int(events_per_lumi)
                if seq_update['customise_commands']:
                    seq_update['customise_commands'] += '; '

                seq_update['customise_commands'] += f'process.source.numberEventsInLuminosityBlock="cms.untracked.uint32({events_per_lumi})"'

            # Pileup
            pileup_dataset_name = self.get_attribute('pileup_dataset_name')
            # Driver itself
            driver = sequence.get_cmsdriver(fragment_name, pileup_dataset_name, seq_update)

            driver += ' --no_exec --mc -n $EVENTS || exit $? ;'
            script += ['#####################',
                       f'# Sequence {index + 1} driver #',
                       '#####################',
                       '',
                       driver,
                       '']
            if for_validation:
                kill_timeout = self.get_safe_runtime()
                script += ['# Sleeping killer',
                           'export VALIDATION_RUN=1',
                           f'KILL_TIMEOUT={int(kill_timeout)}',
                           'PARENT_PID=$$',
                           'echo "Starting at "$(date)',
                           'echo "Will kill at "$(date -d "+$KILL_TIMEOUT seconds")',
                           '(sleep $KILL_TIMEOUT && CMSRUN_PID=$(ps --ppid $PARENT_PID | grep cmsRun | awk \'{print $1}\') && echo "Killing PID $CMSRUN_PID" && kill -s SIGINT $CMSRUN_PID)&',
                           'SLEEP_PID=$!',
                           '']

            if for_test or for_validation:
                script += ['# Run the cmsRun',
                           f'REPORT_{index+1}={report_name}',
                           f'cmsRun -e -j $REPORT_{index+1} {config_name} || exit $? ;',
                           '']

            if for_validation:
                script += ['kill $SLEEP_PID > /dev/null 2>& 1',
                           '']

            if for_test or for_validation:
                # Parse report
                parsing += ['#####################',
                            f'# Sequence {index+1} report #',
                            '#####################',
                            '',
                            f'processedEvents=$(grep -Po "(?<=<Metric Name=\\"NumberEvents\\" Value=\\")(.*)(?=\\"/>)" $REPORT_{index+1} | tail -n 1)',
                            f'producedEvents=$(grep -Po "(?<=<TotalEvents>)(\\d*)(?=</TotalEvents>)" $REPORT_{index+1} | tail -n 1)',
                            f'threads=$(grep -Po "(?<=<Metric Name=\\"NumberOfThreads\\" Value=\\")(.*)(?=\\"/>)" $REPORT_{index+1} | tail -n 1)',
                            f'peakValueRss=$(grep -Po "(?<=<Metric Name=\\"PeakValueRss\\" Value=\\")(.*)(?=\\"/>)" $REPORT_{index+1} | tail -n 1)',
                            f'peakValueVsize=$(grep -Po "(?<=<Metric Name=\\"PeakValueVsize\\" Value=\\")(.*)(?=\\"/>)" $REPORT_{index+1} | tail -n 1)',
                            f'totalSize=$(grep -Po "(?<=<Metric Name=\\"Timing-tstoragefile-write-totalMegabytes\\" Value=\\")(.*)(?=\\"/>)" $REPORT_{index+1} | tail -n 1)',
                            f'totalSizeAlt=$(grep -Po "(?<=<Metric Name=\\"Timing-file-write-totalMegabytes\\" Value=\\")(.*)(?=\\"/>)" $REPORT_{index+1} | tail -n 1)',
                            f'totalJobTime=$(grep -Po "(?<=<Metric Name=\\"TotalJobTime\\" Value=\\")(.*)(?=\\"/>)" $REPORT_{index+1} | tail -n 1)',
                            f'totalJobCPU=$(grep -Po "(?<=<Metric Name=\\"TotalJobCPU\\" Value=\\")(.*)(?=\\"/>)" $REPORT_{index+1} | tail -n 1)',
                            f'eventThroughput=$(grep -Po "(?<=<Metric Name=\\"EventThroughput\\" Value=\\")(.*)(?=\\"/>)" $REPORT_{index+1} | tail -n 1)',
                            f'avgEventTime=$(grep -Po "(?<=<Metric Name=\\"AvgEventTime\\" Value=\\")(.*)(?=\\"/>)" $REPORT_{index+1} | tail -n 1)',
                            'if [ -z "$threads" ]; then',
                            f'  echo "Could not find NumberOfThreads in report, defaulting to {threads}"',
                            f'  threads={threads}',
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
                            f'echo "Validation report of {prepid} sequence {index+1}/{len(sequences)}"',
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
                            'echo "Filter efficiency fraction: "$(bc -l <<< "scale=10; ($producedEvents) / $processedEvents")',
                            ''
                           ]

        script += parsing
        scram_arch = self.get_scram_arch().lower()
        if scram_arch.startswith('slc6_'):
            script = run_commands_in_singularity(commands=script,
                                                 os_name='SLCern6',
                                                 mount_eos=for_validation,
                                                 mount_home=not for_submission)

        return '\n'.join(bash_file + script)

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

    def get_stats(self):
        """
        Fetch workflows from Stats, save them
        Update output datasets accordingly
        Update completed events accordingly
        """
        prepid = self.get('prepid')
        self.logger.info('Updating Stats for %s', prepid)
        # Make a dictionary of available workflows in stats for request
        workflows_in_stats = get_workflows_from_stats_for_prepid(prepid)
        workflows_in_stats = {w['RequestName']: w for w in workflows_in_stats}
        # Get workflow names of all the workflows - in Stats and in McM
        workflow_names = set(workflows_in_stats)
        workflow_names.update(w['name'] for w in self.get('reqmgr_name'))
        workflow_names = sorted(list(workflow_names), key=lambda w: '_'.join(w.split('_')[-3:]))
        self.logger.info('%s workflow names (%s): %s',
                         prepid,
                         len(workflow_names),
                         ', '.join(workflow_names))
        all_workflows = []
        total_events = 0
        dead_status = {'rejected', 'aborted', 'failed', 'rejected-archived',
                       'aborted-archived', 'failed-archived', 'aborted-completed'}

        for workflow_name in workflow_names:
            workflow = workflows_in_stats.get(workflow_name)
            if not workflow:
                self.logger.warning('Could not find %s', workflow_name)
                continue

            self.logger.info('Found workflow %s', workflow_name)
            workflow_type = workflow.get('RequestType', '')
            total_events = max(total_events, workflow.get('TotalEvents', 0))
            status_history = [x['Status'] for x in workflow.get('RequestTransition', [])]
            dead = len(set(status_history) & dead_status) > 0
            priority = workflow.get('RequestPriority', 0)
            stats_update = workflow.get('LastUpdate', 0)
            new_workflow = {'name': workflow_name,
                            'type': workflow_type,
                            'status_history': status_history,
                            'priority': priority,
                            'stats_update': stats_update,
                            'datasets': [],
                            'dead': dead}

            for output_dataset in workflow.get('OutputDatasets', []):
                for history_entry in reversed(workflow.get('EventNumberHistory', [])):
                    if output_dataset in history_entry['Datasets']:
                        dataset_dict = history_entry['Datasets'][output_dataset]
                        new_workflow['datasets'].append({'name': output_dataset,
                                                         'type': dataset_dict['Type'],
                                                         'events': dataset_dict['Events']})
                        break

            # self.logger.debug(json.dumps(new_workflow, indent=2, sort_keys=True))
            all_workflows.append(new_workflow)

        all_workflows = sort_workflows_by_name(all_workflows, 'name')
        self.logger.info('Saving %s workflows for %s', len(all_workflows), prepid)
        self.set('reqmgr_name', all_workflows)
        if total_events > 0 and total_events != self.get('total_events'):
            self.set('total_events', total_events)
            self.update_history('update', 'total_events')

        if any(self.get('keep_output')):
            output_datasets = self.pick_output_datasets(all_workflows)
            completed_events = self.get_completed_events(all_workflows, output_datasets)
        else:
            output_datasets = []
            completed_events = 0

        self.set('output_dataset', output_datasets)
        self.set('completed_events', completed_events)
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

    def get_processing_strings(self):
        processing_strings = []
        for i in range(len(self.get('sequences'))):
            processing_strings.append(self.get_processing_string(i))

        return processing_strings

    def pick_output_datasets(self, workflows):
        prepid = self.get('prepid')
        processing_strings = set(self.get_processing_strings())
        campaign = self.get('member_of_campaign').replace("-", "\\-")
        dataset_name = self.get('dataset_name').replace("-", "\\-")
        dataset_pattern = f'/{dataset_name}/{campaign}\\-(.*)\\-v([0-9]+)/.*'
        self.logger.info('Picking output for %s from %s workflows, processing strings: %s, pattern: %s',
                         prepid,
                         len(workflows),
                         processing_strings,
                         dataset_pattern)
        dataset_matcher = re.compile(dataset_pattern)
        # Pick only not-dead workflows
        workflows = [w for w in workflows if not w.get('dead') and w.get('type').lower() != 'resubmission']
        dataset_names = [dataset['name'] for w in workflows for dataset in w['datasets']]
        dataset_names = list(set(dataset_names))
        # Expected datatiers
        tiers = list(reversed(self.get_tiers()))
        # Keep only those, which have expected datatiers
        dataset_names = [d for d in dataset_names if d.split('/')[-1] in tiers]
        self.logger.info('Datasets (%s): %s', len(dataset_names), dataset_names)
        # Collect datasets as dictionary or tuples {tier: [(version, name)]}
        datasets = {}
        # Go through dataset names
        for dataset in dataset_names:
            match = dataset_matcher.fullmatch(dataset)
            if not match:
                self.logger.info('No match %s', dataset)
                continue

            groups = match.groups()
            if len(groups) != 2:
                self.logger.warning('Unexpected number of groups for %s: %s', dataset, groups)
                continue

            processing_string = groups[0]
            if processing_string not in processing_strings:
                self.logger.warning('Processing string %s does is not expected: %s', processing_string, processing_strings)
                continue

            tier = dataset.split('/')[-1]
            version = int(groups[1])
            datasets.setdefault(tier, []).append((version, dataset))

        self.logger.debug('Collected datasets: %s', json.dumps(datasets, indent=2))
        # Pick newest version for each datatier
        datasets = [sorted(datasets[tier])[-1][1] for tier in tiers if datasets.get(tier)]
        self.logger.info('Picked datasets for %s: %s', prepid, datasets)
        return datasets

    def get_completed_events(self, workflows, output_datasets):
        """
        Get number of completed events of output dataset in given workflows
        """
        if not output_datasets:
            return 0

        dataset = output_datasets[-1]
        for workflow in reversed(workflows):
            for dataset_info in workflow.get('datasets'):
                if dataset_info['name'] == dataset:
                    return dataset_info['events']

        return 0


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

    def get_efficiency(self):
        """
        Get filter and match efficiency of request
        If there are no generator parameters, efficiency is 1.0
        """
        generator_parameters = self.get('generator_parameters')
        if not generator_parameters:
            return 1.0

        if isinstance(generator_parameters, list):
            generator_parameters = generator_parameters[-1]

        match_eff = float(generator_parameters.get('match_efficiency'))
        filter_eff = float(generator_parameters.get('filter_efficiency'))
        return match_eff * filter_eff

    def get_safe_runtime(self):
        """
        Return maximum number of seconds that job could run with safety margin
        """
        runtime = Settings.get('validation_runtime')
        time_margin = Settings.get('validation_margin')
        multiplier = self.get('validation').get('time_multiplier', 1)
        runtime = (runtime * (1.0 - time_margin)) * multiplier
        return int(runtime)

    def get_validation_event_command(self):
        """
        Return number a list of bash commands that set $EVENTS variable to
        number of events that validation should run
        """
        # Settings
        total_events = self.get('total_events')
        efficiency = self.get_efficiency()
        max_events = Settings.get('validation_max_events')
        runtime = self.get_safe_runtime()
        # Events with efficiency
        events_with_eff = int(max_events / efficiency)
        # Time per event sum for single core
        time_per_event_sum = 0
        for time_per_event, sequence in zip(self.get('time_event'), self.get('sequences')):
            time_per_event_sum += int(sequence.get('nThreads', 1)) * time_per_event

        # Events that can fit into safe runtime
        events = int(runtime / time_per_event_sum)
        clamped_events = int(max(1, min(events, events_with_eff, total_events)))
        estimate_produced = int(clamped_events * efficiency)
        prepid = self.get('prepid')
        self.logger.info('Events to run for %s - %s', prepid, clamped_events)
        cmd = [f'# Duration with safety margin: {runtime}s',
               f'# Efficiency: {efficiency:.4f}',
               f'# Events/efficiency: {max_events} / {efficiency:.4f} = {events_with_eff}',
               f'# Time per event sum for single core: {time_per_event_sum:.2f}s',
               f'# Events that fit: {runtime}s / {time_per_event_sum:.2f}s/evt = {events} events',
               f'# Events to run: {clamped_events} events',
               f'# Estimated output: {estimate_produced} events',
               f'EVENTS={clamped_events}',
               '']
        return cmd

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
            if role < Role.GENERATOR_CONVENER:
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

    def get_events_per_lumi(self, cores):
        """
        Return number of events per lumi for given request
        """
        events_per_lumi = self.get('events_per_lumi')
        if events_per_lumi != 0:
            return events_per_lumi

        campaign = Campaign.fetch(self.get('member_of_campaign'))
        events_per_lumi = campaign.get('events_per_lumi')
        if cores > 1 and 'multicore' in events_per_lumi:
            # Multicore value set for campaign
            return events_per_lumi['multicore']

        return cores * events_per_lumi['singlecore']

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



