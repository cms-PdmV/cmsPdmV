#!/usr/bin/env python

import os
import re
import pprint
import xml.dom.minidom
import hashlib
import copy
import traceback
import time
import logging
from math import sqrt
from simplejson import loads, dumps
from operator import itemgetter

from couchdb_layer.mcm_database import database
from json_layer.json_base import json_base
from json_layer.campaign import campaign
from json_layer.flow import flow
from json_layer.batch import batch
from json_layer.generator_parameters import generator_parameters
from json_layer.sequence import sequence
from json_layer.notification import notification
from tools.ssh_executor import ssh_executor
from tools.locator import locator
from tools.installer import installer
import tools.settings as settings
from tools.locker import locker
from tools.user_management import access_rights
from tools.logger import InjectionLogAdapter


class AFSPermissionError(Exception):
    def __init__(self, message=None):
        self.message = message

    def __str__(self):
        return 'AFS permission error: %s' % (self.message)


class request(json_base):
    class DuplicateApprovalStep(Exception):
        def __init__(self, approval=None):
            self.__approval = repr(approval)
            request.logger.error('Duplicate Approval Step: Request has already been %s approved' % (self.__approval))

        def __str__(self):
            return 'Duplicate Approval Step: Request has already been \'' + self.__approval + '\' approved'

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'history': [],
        'priority': 20000,
        'cmssw_release': '',
        'input_dataset': '',
        'output_dataset': [],
        'pwg': '',
        'validation': {},
        'dataset_name': '',
        'pileup_dataset_name': '',
        'process_string': '',
        'extension': 0,
        'block_black_list': [],
        'block_white_list': [],
        'fragment_tag': '',
        'mcdb_id': -1,
        'notes': '',
        'completed_events': -1,
        'total_events': -1,
        'member_of_chain': [],
        'member_of_campaign': '',
        'flown_with': '',
        'time_event': [float(-1)],
        'size_event': [-1],
        'memory': 2300,  # the default until now
        'name_of_fragment': '',
        'fragment': '',
        'config_id': [],
        'version': 0,
        'status': '',
        'type': '',
        'keep_output': [],  # list of booleans
        'generators': [],
        'sequences': [],
        'generator_parameters': [],
        'reqmgr_name': [],  # list of tuples (req_name, valid)
        'approval': '',
        'analysis_id': [],
        'energy': 0.0,
        'tags': [],
        'transient_output_modules': [[]],
        'cadi_line': '',
        'interested_pwg': [],
        'ppd_tags': [],
        'events_per_lumi': 0
    }

    def __init__(self, json_input=None):

        # detect approval steps
        if not json_input:
            json_input = {}
        self.is_root = False
        cdb = database('campaigns')
        if 'member_of_campaign' in json_input and json_input['member_of_campaign']:
            if cdb.document_exists(json_input['member_of_campaign']):
                __camp = cdb.get(json_input['member_of_campaign'])
                self._json_base__schema['memory'] = __camp['memory']

                if __camp['root'] > 0:  # when is not root
                    self._json_base__approvalsteps = ['none', 'approve', 'submit']
                    self._json_base__status = ['new', 'approved', 'submitted', 'done']
                else:
                    self.is_root = True

            else:
                raise Exception('Campaign %s does not exist in the database' % (json_input['member_of_campaign']))

        else:
            raise Exception('Request is not a member of any campaign')

        self._json_base__schema['status'] = self.get_status_steps()[0]
        self._json_base__schema['approval'] = self.get_approval_steps()[0]

        # update self according to json_input
        self.setup()
        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()

    def approve(self, step=-1, to_approval=None):
        json_base.approve(self, step, to_approval)
        step = self.get_attribute('approval')
        result = True
        # is it allowed to move on
        if step == "validation":
            result = self.ok_to_move_to_approval_validation()
        elif step == "define":
            result = self.ok_to_move_to_approval_define()
        elif step == "approve":
            result = self.ok_to_move_to_approval_approve()
        elif step == "submit":
            result = self.ok_to_move_to_approval_submit()

        return result

    def set_status(self, step=-1, with_notification=False, to_status=None):
        # call the base
        json_base.set_status(self, step)
        new_status = self.get_attribute('status')
        prepid = self.get_attribute('prepid')
        if 'pLHE' in self.get_attribute('prepid'):
            title = 'Status changed for request %s to %s' % (prepid, new_status)
            self.notify(
                title,
                self.textified(),
                accumulate=True)

        from json_layer.chained_request import chained_request
        crdb = database('chained_requests')
        for inchain in self.get_attribute('member_of_chain'):
            if crdb.document_exists(inchain):
                chain = chained_request(crdb.get(inchain))
                a_change = False
                a_change += chain.set_last_status(new_status)
                a_change += chain.set_processing_status(self.get_attribute('prepid'), new_status)
                if a_change:
                    crdb.save(chain.json())
        if self._json_base__status[step] in ['new', 'done']:
            self.remove_from_forcecomplete()

    def remove_from_forcecomplete(self):
        lists_db = database('lists')
        forcecomplete_list = lists_db.get('list_of_forcecomplete')
        prepid = self.get_attribute('prepid')
        if prepid not in forcecomplete_list['value']:
            return
        self.logger.info("Deleting a request %s from forcecomplete" % (prepid))
        forcecomplete_list['value'].remove(prepid)
        if not lists_db.update(forcecomplete_list):
            self.logger.error('Failed to save forcecomplete to DB while removing %s from list' % prepid)

    def get_editable(self):
        editable = {}
        # prevent anything to happen during validation procedure.
        if self.get_attribute('status') == 'new' and self.get_attribute('approval') == 'validation':
            for key in self._json_base__schema:
                editable[key] = False
            return editable

        if self.get_attribute('status') != 'new':  # after being new, very limited can be done on it
            for key in self._json_base__schema:
                # we want to be able to edit total_events untill approved status
                if self._json_base__status.index(self.get_attribute("status")) <= 2 and key == "total_events":
                    editable[key] = True
                else:
                    editable[key] = False

            if self.current_user_level != 0:  # not a simple user
                always_editable = settings.get_value('editable_request')
                for key in always_editable:
                    editable[key] = True
            if self.current_user_level > 3:  # only for admins
                for key in self._json_base__schema:
                    editable[key] = True
        else:
            for key in self._json_base__schema:
                editable[key] = True
            if self.current_user_level <= 3:  # only for not admins
                not_editable = settings.get_value('not_editable_request')
                for key in not_editable:
                    editable[key] = False

        return editable

    def get_events_for_dataset(self, workflows, dataset):
        self.logger.debug("Running num_events search for dataset")
        for elem in workflows:
            if dataset in elem["content"].get("pdmv_dataset_statuses", []):
                return elem["content"]["pdmv_dataset_statuses"][dataset]["pdmv_evts_in_DAS"]
        # TO-DO do we need to put a default return? As all the time there must be a DS

    def check_with_previous(self, previous_id, rdb, what, and_set=False):
        previous_one = rdb.get(previous_id)
        input_ds = ""

        if len(previous_one['reqmgr_name']) > 0:
            input_ds = self.get_ds_input(previous_one['output_dataset'],
                    self.get_attribute('sequences'))

        if input_ds == "":
            # in case our datatier selection failed we back up to default method
            previous_events = previous_one['total_events']
            if previous_one['completed_events'] > 0:
                previous_events = previous_one['completed_events']
        else:
            previous_events = self.get_events_for_dataset(previous_one['reqmgr_name'], input_ds)

        self.logger.debug("Possible input for validation:%s events: %s" % (input_ds, previous_events))
        total_events_should_be = previous_events * self.get_efficiency()
        margin = int(total_events_should_be * 1.2)
        if self.get_attribute('total_events') > margin:  # safety factor of 20%
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                what,
                'The requested number of events (%d > %d) is much larger than what can be obtained (%d = %d*%5.2f) from previous request' % (
                    self.get_attribute('total_events'),
                    margin,
                    total_events_should_be,
                    previous_events,
                    self.get_efficiency()))
        if and_set:
            if self.get_attribute('total_events') > 0:
                # do not overwrite the number for no reason
                return
            from math import log10
            # round to a next 1% unit = 10^(-2) == -2 below
            rounding_unit = 10**int(max(log10(total_events_should_be) - 2, 0))
            self.set_attribute('total_events', int(1 + total_events_should_be / float(rounding_unit)) * int(rounding_unit))

    def ok_to_move_to_approval_validation(self, for_chain=False):
        settingsDB = database('settings')
        if settingsDB.get('validation_stop')['value']:
            self.test_failure(message=None, what='', rewind=True, with_notification=False)
            return {'message': ('validation jobs are halted to allow forthcoming mcm restart - try again later')}

        message = ""
        if self.current_user_level == 0:
            # not allowed to do so
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'bad user admin level %s' % (self.current_user_level))

        if self.get_attribute('memory') < 2300:
            raise self.BadParameterValue('Memory (%sMB) is lower than threshold (2300MB)' % (self.get_attribute('memory')))

        if not self.correct_types():
            raise TypeError("Wrong type of attribute, cannot move to approval validation of request {0}".format(self.get_attribute('prepid')))

        if self.get_attribute('status') != 'new':
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation')

        if not self.get_attribute('cmssw_release') or self.get_attribute('cmssw_release') == 'None':
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation', 'The release version is undefined')

        if self.get_scram_arch() is None:
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'The architecture is invalid, probably has the release %s being deprecated' % (self.get_attribute('cmssw_release')))

        bad_characters = [' ', '?', '/', '.', '+']
        if not self.get_attribute('dataset_name') or any(map(lambda char: char in self.get_attribute('dataset_name'), bad_characters)):
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'The dataset name is invalid: either null string or containing %s' % (','.join(bad_characters)))

        if len(self.get_attribute('dataset_name')) > 99:
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'Dataset name is too long: %s. Max 99 characters' % (len(self.get_attribute('dataset_name'))))

        other_bad_characters = [' ', '-']
        if self.get_attribute('process_string') and any(map(lambda char: char in self.get_attribute('process_string'), other_bad_characters)):
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'The process string (%s) contains a bad character %s' % (self.get_attribute('process_string'), ','.join( other_bad_characters )))

        gen_p = self.get_attribute('generator_parameters')
        if not len(gen_p) or generator_parameters(gen_p[-1]).isInValid():
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'The generator parameters is invalid: either none or negative or null values, or efficiency larger than 1')

        gen_p[-1] = generator_parameters(gen_p[-1]).json()
        self.set_attribute('generator_parameters', gen_p)

        if not len(self.get_attribute('generators')):
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'There should be at least one generator mentioned in the request')

        if self.any_negative_events("time_event") or self.any_negative_events("size_event"):
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'The time per event or size per event are invalid: negative or null')

        if not self.get_attribute('fragment') and (not (self.get_attribute('name_of_fragment') and self.get_attribute('fragment_tag'))):
            if self.get_attribute('mcdb_id') > 0 and not self.get_attribute('input_dataset'):
                # this case is OK
                pass
            else:
                raise self.WrongApprovalSequence(
                    self.get_attribute('status'),
                    'validation',
                    'The configuration fragment is not available. Neither fragment or name_of_fragment are available')

        if self.get_attribute('name_of_fragment') and self.get_attribute('fragment_tag'):
            if re.match('^[\w/.-]+$', self.get_attribute('name_of_fragment')) is None:
                raise self.WrongApprovalSequence(
                    self.get_attribute('status'),
                    'validation',
                    'The configuration fragment {0} name contains illegal characters'.format(self.get_attribute('name_of_fragment')))

            for line in self.parse_fragment():
                if 'This is not the web page you are looking for' in line:
                    raise self.WrongApprovalSequence(
                        self.get_attribute('status'),
                        'validation',
                        'The configuration fragment does not exist in git')

                if 'Exception Has Occurred' in line:
                    raise self.WrongApprovalSequence(
                        self.get_attribute('status'),
                        'validation',
                        'The configuration fragment does not exist in cvs')

        if self.get_attribute('total_events') < 0 and not for_chain:
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'The number of requested event is invalid: Negative')

        if self.get_wmagent_type() == 'LHEStepZero':
            if self.get_attribute('mcdb_id') < 0:
                raise self.WrongApprovalSequence(
                    self.get_attribute('status'),
                    'validation',
                    'The request type: %s should have a positive or null mcdb id' % (self.get_attribute('type')))

        if self.get_core_num() == 1 and int(self.get_attribute("memory")) > 2300:
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'Single core request should use <= 2.3GB memory')

        cdb = database('campaigns')
        mcm_c = cdb.get(self.get_attribute('member_of_campaign'))
        rdb = database('requests')

        __q_params = {'dataset_name': self.get_attribute('dataset_name'), 'member_of_campaign': self.get_attribute('member_of_campaign')}

        if self.get_attribute('process_string'):
            __q_params['process_string'] = self.get_attribute('process_string')

        __query = rdb.construct_lucene_query(__q_params)

        similar_ds = rdb.full_text_search("search", __query, page=-1)

        if len(similar_ds) > 1:
            my_extension = self.get_attribute('extension')
            my_id = self.get_attribute('prepid')
            my_process_strings = self.get_processing_strings()

            for similar in similar_ds:
                if similar['prepid'] == my_id:
                    # ignore itself
                    continue
                if similar['keep_output'].count(True) == 0:
                    # ignore if request kept no output
                    continue
                similar_r = request(similar)
                similar_process_strings = similar_r.get_processing_strings()
                if (int(similar['extension']) == int(my_extension)) and (set(my_process_strings) == set(similar_process_strings)):
                    self.logger.info("ApprovalSequence similar prepid: %s" % (similar["prepid"]))

                    raise self.WrongApprovalSequence(
                        self.get_attribute('status'),
                        'validation',
                        'Request %s with the same dataset name, same process string and they are the same extension number (%s)' % (similar['prepid'], my_extension))

        # this below needs fixing
        if not len(self.get_attribute('member_of_chain')):
            # not part of any chains ...
            if self.get_attribute('mcdb_id') >= 0 and not self.get_attribute('input_dataset'):
                if mcm_c['root'] in [-1, 1]:
                    # only requests belonging to a root==0 campaign can have mcdbid without input before being in a chain
                    raise self.WrongApprovalSequence(
                        self.get_attribute('status'),
                        'validation',
                        'The request has an mcdbid, not input dataset, and not member of a root campaign.')
            if self.get_attribute('mcdb_id') > 0 and self.get_attribute('input_dataset') and self.get_attribute('history')[0]['action'] != 'migrated':
                # not a migrated request, mcdb
                raise self.WrongApprovalSequence(
                    self.get_attribute('status'),
                    'validation',
                    'The request has an mcdbid, an input dataset, not part of a chain, and not a result of a migration.')
        else:
            crdb = database('chained_requests')
            for cr in self.get_attribute('member_of_chain'):
                mcm_cr = crdb.get(cr)
                request_is_at = mcm_cr['chain'].index(self.get_attribute('prepid'))
                if request_is_at != 0:
                    # just remove and_set=for_chain to have the value set automatically
                    # https://github.com/cms-PdmV/cmsPdmV/issues/623
                    self.check_with_previous(mcm_cr['chain'][request_is_at - 1], rdb, 'validation', and_set=for_chain)

                if for_chain:
                    continue

                if request_is_at != 0:
                    if self.get_attribute('mcdb_id') >= 0 and not self.get_attribute('input_dataset'):
                        raise self.WrongApprovalSequence(
                            self.get_attribute('status'),
                            'validation',
                            'The request has an mcdbid, not input dataset, and not considered to be a request at the root of its chains.')

                if request_is_at != mcm_cr['step']:
                    raise self.WrongApprovalSequence(
                        self.get_attribute('status'),
                        'validation',
                        'The request is not the current step of chain %s' % (mcm_cr['prepid']))

        # check on chagnes in the sequences
        if len(self.get_attribute('sequences')) != len(mcm_c['sequences']):
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'The request has a different number of steps than the campaigns it belong to')

        def in_there(seq1, seq2):
            items_that_do_not_matter = ['conditions', 'datatier', 'eventcontent', 'nThreads']
            for (name, item) in seq1.json().items():
                if name in items_that_do_not_matter:
                    # there are parameters which do not require specific processing string to be provided
                    continue
                if name in seq2.json():
                    if item != seq2.json()[name]:
                        return False
                else:
                    if item == '':
                        # do not care about parameters that are absent, with no actual value
                        return True
                    return False
                # arived here, all items of seq1 are identical in seq2
            return True

        matching_labels = set([])
        for (i_seq, seqs) in enumerate(mcm_c['sequences']):
            self_sequence = sequence(self.get_attribute('sequences')[i_seq])
            this_matching = set([])
            for (label, seq_j) in seqs.items():
                seq = sequence(seq_j)
                # label = default , seq = dict
                if in_there(seq, self_sequence) and in_there(self_sequence, seq):
                    # identical sequences
                    self.logger.info('identical sequences %s' % label)
                    this_matching.add(label)
                else:
                    self.logger.info('different sequences %s \n %s \n %s' % (label, seq.json(), self_sequence.json()))

            if len(matching_labels) == 0:
                matching_labels = this_matching
                self.logger.info('Matching labels %s' % matching_labels)
            else:
                # do the intersect
                matching_labels = matching_labels - (matching_labels - this_matching)
                self.logger.info('Matching labels after changes %s' % matching_labels)

        # Here we get flow process_string to check
        __flow_ps = ""
        if self.get_attribute('flown_with'):
            fdb = database('flows')
            f = fdb.get(self.get_attribute('flown_with'))
            if 'process_string' in f['request_parameters']:
                __flow_ps = f['request_parameters']['process_string']

        if len(matching_labels) == 0:
            self.logger.info('The sequences of the request is not the same as any the ones of the campaign')
            # try setting the process string ? or just raise an exception ?
            if not self.get_attribute('process_string') and not __flow_ps:  # if they both are empty
                raise self.WrongApprovalSequence(
                    self.get_attribute('status'),
                    'validation',
                    'The sequences of the request has been changed with respect to the campaign, but no processing string has been provided')

        else:
            if self.get_attribute('process_string') or __flow_ps:  # if both are not empty string
                message = {"message": "Request was put to validation. Process string was provided while the sequences is the same as one of the campaign."}

        if for_chain:
            return

        # select to synchronize status and approval toggling, or run the validation/run test
        validation_disable = settings.get_value('validation_disable')
        do_runtest = not validation_disable

        by_pass = settingsDB.get('validation_bypass')['value']
        if self.get_attribute('prepid') in by_pass:
            do_runtest = False

        # if do_runtest, it will be run by a jenkins job, look for ValidationControl.py in this repo
        if not do_runtest:
            self.set_status()

        self.reset_validations_counter()
        if message:
            return message

    def ok_to_move_to_approval_define(self):
        if self.current_user_level == 0:
            # not allowed to do so
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'define', 'bad user admin level %s' % (self.current_user_level))
            # we could restrict certain step to certain role level
        # if self.current_user_role != 'generator_contact':
        #    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','bad user role %s'%(self.current_user_role))

        if self.get_attribute('status') != 'validation':
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'define')

        # a state machine should come along and create the configuration. check the filter efficiency, and set information back
        # then toggle the status
        self.set_status()

    def ok_to_move_to_approval_approve(self, for_chain=False):
        max_user_level = 1
        PRIMARY_DS_regex = '^[a-zA-Z][a-zA-Z0-9\-_]*$'
        if for_chain:
            max_user_level = 0

        if self.current_user_level <= max_user_level:
            # not allowed to do so
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'approve',
                'bad user admin level %s' % (self.current_user_level))

        if self.is_root:
            if self.get_attribute('status') != 'defined':
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'approve')
        else:
            if self.get_attribute('status') != 'new':
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'approve')

        if re.match(PRIMARY_DS_regex, self.get_attribute('dataset_name')) is None:
                raise self.WrongApprovalSequence(
                    self.get_attribute('status'),
                    'approve',
                    'Dataset name name contains illegal characters')

        if len(self.get_attribute('dataset_name')) > 99:
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'validation',
                'Dataset name is too long: %s. Max 99 characters' % (len(self.get_attribute('dataset_name'))))

        if len(self.get_attribute('time_event')) != len(self.get_attribute("sequences")):
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'approve',
                'Number of time_event entries: %s are different from number of sequences: %s' % (
                    len(self.get_attribute("time_event")),
                    len(self.get_attribute("sequences"))))

        if len(self.get_attribute('size_event')) != len(self.get_attribute("sequences")):
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'approve',
                'Number of size_event entries: %s are different from number of sequences: %s' % (
                    len(self.get_attribute("size_event")),
                    len(self.get_attribute("sequences"))))

        # Check if there are new/announced invalidations for request before approving it.
        # So we would not submit same request to computing until previous is fully reset/invalidated
        idb = database("invalidations")
        __invalidations_query = idb.construct_lucene_query({"prepid": self.get_attribute("prepid")})
        self.logger.debug("len invalidations list %s" % (len(__invalidations_query)))
        res = idb.full_text_search("search", __invalidations_query, page=-1)
        for el in res:
            if el["status"] in ["new", "announced"]:
                raise self.WrongApprovalSequence(
                    self.get_attribute('status'),
                    'approve',
                    'There are unacknowledged invalidations for request: %s' % (self.get_attribute("prepid")))

        crdb = database('chained_requests')
        rdb = database('requests')
        for cr in self.get_attribute('member_of_chain'):
            mcm_cr = crdb.get(cr)
            request_is_at = mcm_cr['chain'].index(self.get_attribute('prepid'))

            if request_is_at != 0:
                self.check_with_previous(
                    mcm_cr['chain'][request_is_at - 1],
                    rdb,
                    'approve',
                    and_set=for_chain)

            if for_chain:
                continue

            if request_is_at != mcm_cr['step']:
                all_good = True
                chain = mcm_cr['chain'][mcm_cr['step']:]
                for r in chain:
                    if r == self.get_attribute('prepid'):
                        # don't self check
                        continue

                    mcm_r = request(rdb.get(r))
                    if mcm_r.is_root:
                        # we check if request needs validation,
                        # so we wont approve a request which is not yet validated
                        all_good &= (mcm_r.get_attribute('status') in ['defined', 'validation', 'approved'])

                if not all_good:
                    raise self.WrongApprovalSequence(
                        self.get_attribute('status'),
                        'approve',
                        'The request is not the current step of chain %s and the remaining of the chain is not in the correct status' % (mcm_cr['prepid']))
        # start uploading the configs ?
        if not for_chain:
            self.set_status()

    def ok_to_move_to_approval_submit(self):
        if self.current_user_level < 3:
            # not allowed to do so
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'submit',
                'bad user admin level %s' % (self.current_user_level))

        if self.get_attribute('status') != 'approved':
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'submit')

        if not len(self.get_attribute('member_of_chain')):
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'submit',
                'This request is not part of any chain yet')

        at_least_an_action = self.has_at_least_an_action()
        if not at_least_an_action:
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'submit',
                'This request does not spawn from any valid action')

        if self.any_negative_events("time_event") or self.any_negative_events("size_event"):
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'submit',
                'The time (%s) or size per event (%s) is inappropriate' % (
                    self.get_attribute('time_event'),
                    self.get_attribute('size_event')))


        if self.get_scram_arch() == None:
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'submit',
                'The architecture is invalid, probably has the release %s being deprecated' % (self.get_attribute('cmssw_release')))

        other_bad_characters = [' ', '-']
        if self.get_attribute('process_string') and any(map(lambda char: char in self.get_attribute('process_string'), other_bad_characters)):
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'submit',
                'The process string (%s) contains a bad character %s' % (
                    self.get_attribute('process_string'),
                    ','.join( other_bad_characters )))

        # do a dataset collision check : remind that it requires the flows to have process_string properly set
        rdb = database('requests')
        __query = rdb.construct_lucene_query({'dataset_name': self.get_attribute('dataset_name')})
        similar_ds = rdb.full_text_search('search', __query, page=-1)
        my_ps_and_t = self.get_camp_plus_ps_and_tiers()
        for (camp, my_ps, my_t) in my_ps_and_t:
            check_ingredients = map(lambda s: s.lower(), my_ps.split('_'))
            __uniq_set = set()
            if any(x in __uniq_set or __uniq_set.add(x) for x in check_ingredients) and self.current_user_level == 4:
                raise self.WrongApprovalSequence(
                    self.get_attribute('status'),
                    'submit',
                    "There is a duplicate string in the constructed processing (%s) string of one of the expected output dataset. Checking %s" % ( my_ps, check_ingredients ))

        self.logger.info('Similar DS to %s are: %s' % (self.get_attribute('prepid'), ', '.join([s['prepid'] for s in similar_ds])))
        if len(similar_ds) == 0:
            raise self.WrongApprovalSequence(
                self.get_attribute('status'),
                'submit',
                "It seems that database is down, could not check for duplicates")

        for similar in similar_ds:
            if similar['prepid'] == self.get_attribute('prepid'):
                continue  # no self check
            similar_r = request(similar)
            similar_ps_and_t = similar_r.get_camp_plus_ps_and_tiers()
            # check for collision
            collisions = filter(lambda ps: ps in my_ps_and_t, similar_ps_and_t)
            if len(collisions) != 0:
                text = str(collisions)
                self.logger.info("Possible collisions prepid: %s" % (similar['prepid']))
                raise self.WrongApprovalSequence(
                    self.get_attribute('status'),
                    'submit',
                    'Output dataset naming collision with %s. Similar id: %s' % (text, similar['prepid']))

        moveon_with_single_submit = True  # for the case of chain request submission
        is_the_current_one = False
        # check on position in chains
        crdb = database('chained_requests')
        rdb = database('requests')
        for c in self.get_attribute('member_of_chain'):
            mcm_cr = crdb.get(c)
            chain = mcm_cr['chain'][mcm_cr['step']:]

            # check everything that comes after for something !=new to block automatic submission.
            for r in chain:
                if r == self.get_attribute('prepid'):
                    continue  # no self checking

                mcm_r = request(rdb.get(r))
                # we can move on to submit if everything coming next in the chain is new
                moveon_with_single_submit &= (mcm_r.get_attribute('status') in ['new'])

        fdb = database('flows')
        ccdb = database('chained_campaigns')
        # Check if any of the requests in any chained requests are new to block automatic submission.
        for c in self.get_attribute('member_of_chain'):
            mcm_cr = crdb.get(c)
            chain = mcm_cr['chain'][mcm_cr['step']:]
            chained_campaign = ccdb.get(mcm_cr['member_of_campaign'])

            # Flag means whether chained campaign is active. If it's not active, ignore it
            if not chained_campaign.get('action_parameters', {}).get('flag', True):
                self.logger.info('Chained campaign %s flag is off, skipping check' % (chained_campaign.get_attribute('prepid')))
                continue

            for r in chain:
                if r == self.get_attribute('prepid'):
                    # No self checking
                    continue

                mcm_r = request(rdb.get(r))
                mcm_r_flow = flow(fdb.get(mcm_r.get_attribute('flown_with')))
                if mcm_r_flow.get_attribute('approval') in ['submit', 'tasksubmit'] and mcm_r.get_attribute('status') in ['new']:
                    raise self.WrongApprovalSequence(
                        self.get_attribute('status'),
                        'submit',
                        'The request %s could not be submitted because following request %s is none-new and flow is "%s". Approve following requests first.' % (
                            self.get_attribute('prepid'),
                            mcm_r.get_attribute('prepid'),
                            mcm_r_flow.get_attribute('approval')))

        for c in self.get_attribute('member_of_chain'):
            mcm_cr = crdb.get(c)
            is_the_current_one = (mcm_cr['chain'].index(self.get_attribute('prepid')) == mcm_cr['step'])
            if not is_the_current_one and moveon_with_single_submit:
                # check that something else in the chain it belongs to is indicating that
                raise self.WrongApprovalSequence(
                    self.get_attribute('status'),
                    'submit',
                    'The request (%s)is not the current step (%s) of its chain (%s)' % (
                        self.get_attribute('prepid'),
                        mcm_cr['step'], c))

        sync_submission = True
        self.logger.debug("sync submission:%s single_submit:%s" % (sync_submission, moveon_with_single_submit))
        if sync_submission and moveon_with_single_submit:
            # remains to the production manager to announce the batch the requests are part of
            self.logger.info("Doing single request submission for:%s" % (self.get_attribute('prepid')))
            from tools.handlers import RequestInjector, submit_pool

            _q_lock = locker.thread_lock(self.get_attribute('prepid'))
            if not locker.thread_acquire(self.get_attribute('prepid'), blocking=False):
                return {
                    "prepid": self.get_attribute('prepid'),
                    "results": False,
                    "message": "The request {0} request is being handled already".format(
                        self.get_attribute('prepid'))}

            threaded_submission = RequestInjector(prepid=self.get_attribute('prepid'),
                    check_approval=False, lock=locker.lock(self.get_attribute('prepid')),
                    queue_lock=_q_lock)

            submit_pool.add_task(threaded_submission.internal_run)
        else:
            # not settting any status forward
            # the production manager would go and submit those by hand via McM : the status is set automatically upon proper injection

            # N.B. send the submission of the chain automatically from submit approval of the request at the processing point of a chain already approved for chain processing : dangerous for commissioning. to be used with care
            if not moveon_with_single_submit and is_the_current_one:
                self.logger.info("Doing TaskChain submission for:%s" % (self.get_attribute('prepid')))
                from tools.handlers import ChainRequestInjector, submit_pool

                _q_lock = locker.thread_lock(self.get_attribute('prepid'))
                if not locker.thread_acquire(self.get_attribute('prepid'), blocking=False):
                    return {
                    "prepid": self.get_attribute('prepid'),
                    "results": False,
                    "message": "The request {0} request is being handled already".format(
                        self.get_attribute('prepid'))}

                threaded_submission = ChainRequestInjector(prepid=self.get_attribute('prepid'),
                        check_approval=False, lock=locker.lock(self.get_attribute('prepid')),
                        queue_lock=_q_lock)

                submit_pool.add_task(threaded_submission.internal_run)
            else:
                self.logger.error("Not doing anything for submission. moveon_with_single_submit:%s is_the_current_one:%s" % (
                        moveon_with_single_submit, is_the_current_one))
                return {
                    "prepid": self.get_attribute('prepid'),
                    "results": False,
                    "message": "The request was not submitted"}

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
                get_me += '--create-dirs -o  Configuration/GenProduction/python/%s ' % (name)
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

        if sequenceindex == len(self.get_attribute('sequences')) - 1:
            # last one
            command += '--fileout file:%s.root ' % (self.get_attribute('prepid'))
        else:
            command += '--fileout file:%s_step%d.root ' % (self.get_attribute('prepid'), sequenceindex + 1)

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

    def set_options(self, can_save=True):
        if self.get_attribute('status') == 'new':
            cdb = database('campaigns')

            flownWith = None
            if self.get_attribute('flown_with'):
                fdb = database('flows')
                flownWith = flow(fdb.get(self.get_attribute('flown_with')))

            camp = campaign(cdb.get(self.get_attribute('member_of_campaign')))
            self.transfer_from(camp)
            # putting things together from the campaign+flow
            freshSeq = []
            freshKeep = []
            freshTransientOutputModules = []
            if flownWith:
                request.put_together(camp, flownWith, self)
            else:
                for i in range(len(camp.get_attribute('sequences'))):
                    fresh = sequence(camp.get_attribute('sequences')[i]["default"])
                    freshSeq.append(fresh.json())
                    freshKeep.append(False)  # dimension keep output to the sequences
                    freshTransientOutputModules.append([])

                if not camp.get_attribute("no_output"):
                    freshKeep[-1] = True  # last output must be kept

                self.set_attribute('sequences', freshSeq)
                self.set_attribute('keep_output', freshKeep)
                self.set_attribute('transient_output_modules', freshTransientOutputModules)
            if can_save:
                self.update_history({'action': 'reset', 'step': 'option'})
                self.reload()

    def reset_options(self, can_save=True):
        self.logger.error("executing code that we shouldnt")
        cdb = database('campaigns')
        camp = campaign(cdb.get(self.get_attribute("member_of_campaign")))
        # a way of resetting the sequence and necessary parameters
        if self.get_attribute('status') == 'new':
            self.set_attribute('cmssw_release', '')
            self.set_attribute('pileup_dataset_name', '')
            self.set_attribute('output_dataset', [])
            freshSeq = []
            freshKeep = []
            freshTransientOutputModules = []
            for i in range(len(self.get_attribute('sequences'))):
                freshSeq.append(sequence().json())
                freshKeep.append(False)
                freshTransientOutputModules.append([])

            if not camp.get_attribute("no_output"):
                freshKeep[-1] = True  # last output must be kept

            freshKeep[-1] = True
            self.set_attribute('sequences', freshSeq)
            self.set_attribute('keep_output', freshKeep)
            self.set_attribute('transient_output_modules', freshTransientOutputModules)
            # then update itself in DB
            if can_save:
                self.reload()

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

    def get_transient_tiers(self):
        transient_output_modules = self.get_attribute('transient_output_modules')
        transient_tiers = []
        for (i, s) in enumerate(self.get_attribute('sequences')):
            if i >= len(transient_output_modules):
                continue

            modules = transient_output_modules[i]
            if len(modules) == 0:
                # If there are no transient output modules,
                # there is no point in looking at datatiers
                continue

            eventcontent = s.get('eventcontent', [])
            datatier = s.get('datatier', [])
            for (ec_index, eventcontent_entry) in enumerate(eventcontent):
                if '%soutput' % (eventcontent_entry) in modules:
                    if ec_index < len(datatier):
                        transient_tiers.append(datatier[ec_index])

        if len(transient_tiers) > 0:
            self.logger.info('Transient tiers for %s are: %s' % (self.get_attribute('prepid'), transient_tiers))

        return transient_tiers

    def get_outputs(self):
        outs = []
        keeps = self.get_attribute('keep_output')

        camp = self.get_attribute('member_of_campaign')
        dsn = self.get_attribute('dataset_name')
        v = self.get_attribute('version')

        for (i, s) in enumerate(self.get_attribute('sequences')):
            if i < len(keeps) and not keeps[i]:
                continue
            proc = self.get_processing_string(i)
            tiers = s['datatier']
            if isinstance(tiers, str):
                # only for non-migrated requests
                tiers = tiers.split(',')
            for t in tiers:
                outs.append('/%s/%s-%s-v%s/%s' % (dsn, camp, proc, v, t))

        return outs

    def get_processing_string(self, i):
        ingredients = []
        if self.get_attribute('flown_with'):
            ccDB = database('chained_campaigns')
            fdb = database('flows')
            # could 2nd chain_req be with different process_string??
            # we dont want to use chained_camp object -> circular dependency :/
            # so we work on json object
            __cc_id = self.get_attribute("member_of_chain")[0].split("-")[1]
            __cc = ccDB.get(__cc_id)
            for camp, mcm_flow in __cc["campaigns"]:
                if mcm_flow != None:
                    f = fdb.get(mcm_flow)
                    if 'process_string' in f['request_parameters']:
                        ingredients.append(f['request_parameters']['process_string'])
                # don't include process_strings from flows which goes after request
                if self.get_attribute('member_of_campaign') == camp:
                    break

        ingredients.append(self.get_attribute('process_string'))
        ingredients.append(self.get_attribute('sequences')[i]['conditions'].replace('::All', ''))
        if self.get_attribute('extension'):
            ingredients.append("ext%s" % self.get_attribute('extension'))
        return "_".join(filter(lambda s: s, ingredients))

    def get_processing_strings(self):
        keeps = self.get_attribute('keep_output')
        ps = []
        for i in range(len(self.get_attribute('sequences'))):
            if i < len(keeps) and not keeps[i]:
                continue
            ps.append(self.get_processing_string(i))
        return ps

    def get_camp_plus_ps_and_tiers(self):
        keeps = self.get_attribute('keep_output')
        # we should compare whole Campaign-Processstring_tag
        campaign = self.get_attribute("member_of_campaign")
        p_and_t = []
        for i in range(len(self.get_attribute('sequences'))):
            if i < len(keeps) and not keeps[i]:
                continue
            p_and_t.extend([(campaign, self.get_processing_string(i), tier) for tier in self.get_tier(i)])
        return p_and_t

    def little_release(self):
        release_to_find = self.get_attribute('cmssw_release')
        return release_to_find.replace('CMSSW_', '').replace('_', '')

    def get_scram_arch(self):
        # economise to call many times.
        if hasattr(self, 'scram_arch'):
            return self.scram_arch

        scram_arch_exceptions = settings.get_value('scram_arch_exceptions')
        prepid = self.get_attribute('prepid')
        campaign = self.get_attribute('member_of_campaign')
        release_to_find = self.get_attribute('cmssw_release')
        if prepid in scram_arch_exceptions:
            self.scram_arch = scram_arch_exceptions.get(prepid)
            self.logger.info('Found %s in scram arch exceptions (%s)' % (prepid, self.scram_arch))
            return self.scram_arch
        elif campaign in scram_arch_exceptions:
            self.scram_arch = scram_arch_exceptions.get(campaign)
            self.logger.info('Found %s in scram arch exceptions (%s)' % (campaign, self.scram_arch))
            return self.scram_arch
        elif release_to_find in scram_arch_exceptions:
            self.scram_arch = scram_arch_exceptions.get(release_to_find)
            self.logger.info('Found %s in scram arch exceptions (%s)' % (release_to_find, self.scram_arch))
            return self.scram_arch

        self.scram_arch = None
        import xml.dom.minidom

        release_announcement = settings.get_value('release_announcement')
        xml_data = xml.dom.minidom.parseString(os.popen('curl -s --insecure %s ' % (release_announcement)).read())

        for arch in xml_data.documentElement.getElementsByTagName("architecture"):
            scram_arch = arch.getAttribute('name')
            for project in arch.getElementsByTagName("project"):
                release = str(project.getAttribute('label'))
                if release == release_to_find:
                    self.scram_arch = scram_arch

        return self.scram_arch

    def make_release(self):
        makeRel = 'export SCRAM_ARCH=%s\n' % (self.get_scram_arch())
        makeRel += 'source /cvmfs/cms.cern.ch/cmsset_default.sh\n'
        makeRel += 'if [ -r %s/src ] ; then \n' % (self.get_attribute('cmssw_release'))
        makeRel += ' echo release %s already exists\n' % (self.get_attribute('cmssw_release'))
        makeRel += 'else\n'
        makeRel += 'scram p CMSSW ' + self.get_attribute('cmssw_release') + '\n'
        makeRel += 'fi\n'
        makeRel += 'cd ' + self.get_attribute('cmssw_release') + '/src\n'
        makeRel += 'eval `scram runtime -sh`\n'  # setup the cmssw

        return makeRel

    def get_setup_file(self, directory='', events=None, run=False, do_valid=False, for_validation=False, gen_script=False):
        # run is for adding cmsRun
        # do_valid id for adding the file upload
        l_type = locator()
        infile = '#!/bin/bash\n'

        first_tiers = ','.join(self.get_tier(0))
        # pLHE, GS and wmLHEGS
        gen_script_tiers = set(['LHE',
                                'GEN-SIM',
                                'LHE,GEN-SIM',
                                'GEN-SIM,LHE',
                                'GEN,LHE',
                                'LHE,GEN',
                                'GEN'])

        sequence_step = self.get_attribute('sequences')[0].get('step', '')
        if first_tiers not in gen_script_tiers and 'RECOBEFMIX' not in sequence_step:
            gen_script = False

        self.logger.info('Tiers for %s are %s' % (self.get_attribute('prepid'), first_tiers))
        # GEN checking script
        if gen_script:
            eos_path = '/eos/cms/store/group/pdmv/mcm_gen_checking_script'
            if l_type.isDev():
                eos_path += '_dev'

            infile += '\n'
            infile += 'REQUEST=%s\n' % self.get_attribute('prepid')
            if for_validation:
                infile += 'REQUEST_NEWEST_FILE=%s_newest.log\n' % self.get_attribute('prepid')
                infile += 'CAMPAIGN=%s\n' % self.get_attribute('member_of_campaign')
                infile += 'EOS_PATH=%s/$CAMPAIGN\n' % (eos_path)

            # Clone gen repo
            infile += 'wget --quiet https://raw.githubusercontent.com/cms-sw/genproductions/master/bin/utils/request_fragment_check.py\n'
            # Run script and write to log file
            if for_validation:
                infile += 'mkdir -p $EOS_PATH\n'

            infile += 'python request_fragment_check.py --bypass_status --prepid $REQUEST'
            if l_type.isDev():
                infile += ' --dev'

            if for_validation:
                infile += '> $EOS_PATH/$REQUEST_NEWEST_FILE\n'
            else:
                infile += '\n'

            # Get exit code
            infile += 'ERRORS=$?\n'
            if for_validation:
                # Add latest log to all logs
                infile += 'cat $EOS_PATH/$REQUEST_NEWEST_FILE >> $EOS_PATH/$REQUEST.log\n'
                # Print newest log
                infile += 'echo --BEGIN GEN Request checking script output--\n'
                infile += 'cat $EOS_PATH/$REQUEST_NEWEST_FILE\n'
                infile += 'echo --END GEN Request checking script output--\n'
                # Write a couple of empty lines to the end of a file
                infile += 'echo "" >> $EOS_PATH/$REQUEST.log\n'
                infile += 'echo "" >> $EOS_PATH/$REQUEST.log\n'

            # Check exit code of script
            infile += 'if [ $ERRORS -ne 0 ]; then\n'
            infile += '    echo "GEN Request Checking Script returned exit code $ERRORS which means there are $ERRORS errors"\n'
            infile += '    echo "Validation WILL NOT RUN"\n'
            infile += '    echo "Please correct errors in the request and run validation again"\n'
            infile += '    exit $ERRORS\n'
            infile += 'fi\n'
            # If error code is zero, continue to validation
            infile += 'echo "Running VALIDATION. GEN Request Checking Script returned no errors"\n'
            infile += '\n'

        if directory or for_validation:
            infile += self.make_release()
        else:
            infile += self.make_release()

        # get the fragment if need be
        infile += self.retrieve_fragment()

        infile += 'export X509_USER_PROXY=$HOME/private/personal/voms_proxy.cert\n'
        fragment_retry_amount = 2
        # copy the fragment directly from the DB into a file
        if self.get_attribute('fragment'):
            infile += 'curl -s --insecure %spublic/restapi/requests/get_fragment/%s --retry %s --create-dirs -o %s \n' % (
                l_type.baseurl(), self.get_attribute('prepid'),
                fragment_retry_amount, self.get_fragment())

            # lets check if downloaded file actually exists and has more than 0 bytes
            infile += '[ -s %s ] || exit $?;\n' % (self.get_fragment())

        ##check if fragment contains gridpack path and that gridpack is in cvmfs when running validation
        if run and self.get_fragment():
            infile += '\n'
            infile += 'if grep -q "gridpacks" %s; then\n' % (self.get_fragment())
            infile += '  if ! grep -q "/cvmfs/cms.cern.ch/phys_generator/gridpacks" %s; then\n ' % (self.get_fragment())
            infile += '    echo "Gridpack inside fragment is not in cvmfs."\n'
            infile += '    exit -1\n'
            infile += '  fi\n'
            infile += 'fi\n'

        # previous counter
        previous = 0

        # validate and build cmsDriver commands
        cmsd_list = ''

        configuration_names = []
        if events is None:
            events = self.get_n_for_test(self.target_for_test())

        for i, cmsd in enumerate(self.build_cmsDrivers()):
            inline_c = ''
            # check if customization is needed to check it out from cvs
            if '--customise ' in cmsd:
                cust = cmsd.split('--customise ')[1].split(' ')[0]
                toks = cust.split('.')
                cname = toks[0] + '.py'
                # add customization
                if 'GenProduction' in cname:
                    # this works for back-ward compatiblity
                    infile += self.retrieve_fragment(name=cname)
                    # force inline the customisation fragment in that case.
                    # if user sets inlinde_custom to 0 we dont set it
                    if int(self.get_attribute("sequences")[-1]["inline_custom"]) != 0:
                        inline_c = '--inline_custom 1 '

            # tweak a bit more finalize cmsDriver command
            res = cmsd
            configuration_names.append(os.path.join(directory,
                    self.get_attribute('prepid') + "_" + str(previous + 1) + '_cfg.py'))

            res += '--python_filename %s --no_exec ' % (configuration_names[-1])
            # add monitoring at all times...
            if '--customise ' in cmsd:
                old_cust = cmsd.split('--customise ')[1].split()[0]
                new_cust = old_cust
                new_cust += ',Configuration/DataProcessing/Utils.addMonitoring'
                res = res.replace('--customise %s' % (old_cust), '--customise %s' % (new_cust))
            else:
                res += '--customise Configuration/DataProcessing/Utils.addMonitoring '

            if 'wmlhegs' in self.get_attribute('prepid').lower():
                random_seed_command = 'process.RandomNumberGeneratorService.externalLHEProducer.initialSeed="int(${seed}%100)"'
                if '--customise_commands ' in cmsd:
                    res = res.replace('--customise_commands ',
                                      '--customise_commands %s\\\\n' % (random_seed_command))
                else:
                    res += '--customise_commands %s ' % (random_seed_command)

            if run and i == 0 and first_tiers in gen_script_tiers:
                cdb = database('campaigns')
                camp = campaign(cdb.get(self.get_attribute("member_of_campaign")))
                if camp.is_release_greater_or_equal_to('CMSSW_9_3_0'):
                    member_of_chains = self.get_attribute('member_of_chain')
                    if len(member_of_chains) > 0:
                        crdb = database('chained_requests')
                        from json_layer.chained_request import chained_request
                        chained_req = chained_request(crdb.get(member_of_chains[0]))
                        chained_req_chain = chained_req.get_attribute('chain')
                        if len(chained_req_chain) > 0 and chained_req_chain[0] == self.get_attribute('prepid'):
                            num_cores = self.get_attribute('sequences')[i].get('nThreads', None)
                            if not num_cores:
                                num_cores = 1

                            events_per_lumi = self.get_events_per_lumi(num_cores)
                            max_forward_eff = self.get_forward_efficiency()
                            events_per_lumi /= self.get_efficiency() # should stay nevertheless as it's in wmcontrol for now
                            events_per_lumi /= max_forward_eff # this does not take its own efficiency
                            events_per_lumi = int(events_per_lumi)
                            events_per_lumi_command = 'process.source.numberEventsInLuminosityBlock="cms.untracked.uint32(%s)"' % (events_per_lumi)
                            if '--customise_commands ' in res:
                                res = res.replace('--customise_commands ',
                                                  '--customise_commands %s\\\\n' % (events_per_lumi_command))
                            else:
                                res += '--customise_commands %s ' % (events_per_lumi_command)

            res += inline_c

            res += '-n ' + str(events) + ' || exit $? ; \n'
            if run:

                if previous:
                    runtest_xml_file = os.path.join(directory, "%s_%s_rt.xml" % (
                            self.get_attribute('prepid'), previous + 1))

                else:
                    runtest_xml_file = os.path.join(directory, "%s_rt.xml" % (
                            self.get_attribute('prepid')))

                res += 'cmsRun -e -j %s %s || exit $? ; \n' % (
                        runtest_xml_file, configuration_names[-1])

                if events >= 0:
                    res += 'echo %d events were ran \n' % events

                res += 'grep "TotalEvents" %s \n' % runtest_xml_file
                res += 'if [ $? -eq 0 ]; then\n'
                res += '    grep "Timing-tstoragefile-write-totalMegabytes" %s \n' % runtest_xml_file
                res += '    if [ $? -eq 0 ]; then\n'
                res += '        events=$(grep "TotalEvents" %s | tail -1 | sed "s/.*>\(.*\)<.*/\\1/")\n' % runtest_xml_file
                res += '        size=$(grep "Timing-tstoragefile-write-totalMegabytes" %s | sed "s/.* Value=\\"\(.*\)\\".*/\\1/")\n' % runtest_xml_file
                res += '        if [ $events -gt 0 ]; then\n'
                res += '            echo "McM Size/event: $(bc -l <<< "scale=4; $size*1024 / $events")"\n'
                res += '        fi\n'
                res += '    fi\n'
                res += 'fi\n'
                res += 'grep "EventThroughput" %s \n' % runtest_xml_file
                res += 'if [ $? -eq 0 ]; then\n'
                res += '  var1=$(grep "EventThroughput" %s | sed "s/.* Value=\\"\(.*\)\\".*/\\1/")\n' % (runtest_xml_file)
                res += '  echo "McM time_event value: $(bc -l <<< "scale=4; 1/$var1")"\n'
                res += 'fi\n'
                res += 'echo CPU efficiency info:\n'
                res += 'grep "TotalJobCPU" %s \n' % runtest_xml_file
                res += 'grep "TotalJobTime" %s \n' % runtest_xml_file
                # TO-DO:
                # 1) add efficiency calc(?)

            cmsd_list += res + '\n'
            previous += 1

        infile += '\nscram b\n'
        infile += 'cd ../../\n'
        if 'wmlhegs' in self.get_attribute('prepid').lower():
            infile += 'seed=$(date +%s)\n'

        infile += cmsd_list
        # since it's all in a subshell, there is
        # no need for directory traversal (parent stays unaffected)

        # if there was a release setup, jsut remove it
        # not in dev
        if (directory or for_validation) and not l_type.isDev():
            infile += 'rm -rf %s' % (self.get_attribute('cmssw_release'))

        return infile

    def modify_priority(self, new_priority):
        self.set_attribute('priority', new_priority)
        self.update_history({'action': 'priority', 'step': new_priority})
        saved = self.reload()
        if not saved:
            self.logger.error('Could not save request {0} with new priority'.format(self.get_attribute('prepid')))
            return False

        self.logger.info('Priority of request {0} was changed to {1}'.format(self.get_attribute('prepid'), new_priority))
        return True

    def change_priority(self, new_priority):
        if not isinstance(new_priority, int):
            self.logger.error('Priority has to be an integer')
            return False
        if self.get_attribute('status') in ['done']:
            return True
        if self.get_attribute('priority') == new_priority:
            return True
        with locker.lock(self.get_attribute('prepid')):
            loc = locator()
            self.logger.info('trying to change priority to %s at %s' % (self.get_attribute('prepid'), new_priority))
            reqmgr_names = [reqmgr['name'] for reqmgr in self.get_attribute('reqmgr_name') if '_ACDC' not in reqmgr['name']]
            self.logger.info('Will change priority to %s for %s' % (new_priority, reqmgr_names))
            if len(reqmgr_names):
                ssh_exec = ssh_executor(server='vocms081.cern.ch')
                cmd = 'export X509_USER_PROXY=/afs/cern.ch/user/p/pdmvserv/private/$HOSTNAME/voms_proxy.cert\n'
                cmd += 'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n'
                test = ""
                if loc.isDev():
                    test = '-u cmsweb-testbed.cern.ch'
                for req_name in reqmgr_names:
                    cmd += 'wmpriority.py {0} {1} {2}\n'.format(req_name, new_priority, test)
                _, stdout, stderr = ssh_exec.execute(cmd)
                self.logger.info(cmd)
                if not stdout and not stderr:
                    self.logger.error('SSH error while changing priority of {0}'.format(
                        self.get_attribute('prepid')))
                    return False
                output_text = stdout.read()
                self.logger.error('wmpriority output:\n{0}'.format(output_text))
                try:
                    __out = loads(output_text)
                    for el in __out["result"]:
                        __id = el.keys()[0]
                        # check if it is the workflow we wanted to change
                        if __id in reqmgr_names:
                            # strangely reqmgr2 changes it's ouput structure alot
                            # let's pray that the key is always reqmgr_name
                            if el[__id].upper() == "OK":
                                self.logger.debug("Change of priority succeeded")
                            else:
                                return False

                except Exception as ex:
                    self.logger.error("Failed parsing wmpriotiry output: %s" % (str(ex)))
                    return False
            return self.modify_priority(new_priority)

    def get_valid_and_n(self):
        val_attributes = self.get_attribute('validation')
        n_to_valid = self.get_n_for_valid()
        yes_to_valid = False
        if n_to_valid:
            yes_to_valid = True
        if 'valid' in val_attributes:
            yes_to_valid = val_attributes['valid']
        else:
            yes_to_valid = False

        bypass = settings.get_value('campaign_valid_bypass')
        if self.get_attribute('member_of_campaign') in bypass:
            yes_to_valid = False

        return (yes_to_valid, n_to_valid)

    def get_first_output(self):
        eventcontentlist = []
        for cmsDriver in self.build_cmsDrivers():
            eventcontent = cmsDriver.split('--eventcontent')[1].split()[0] + 'output'
            if ',' in eventcontent:
                eventcontent = eventcontent.split(',')[0] + 'output'
            eventcontentlist.append(eventcontent)
        return eventcontentlist

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

    def verify_sanity(self):
        # check whether there are missing bits and pieces in the request
        # maybe raise instead of just returning false
        wma_type = self.get_wmagent_type()
        if wma_type in ['MonteCarloFromGEN', 'ReDigi'] and not self.get_attribute('input_dataset'):
            # raise Exception('Input Dataset name is not defined.')
            return True
        if wma_type in ['MonteCarlo', 'MonteCarloFromGEN', 'LHEStepZero']:
            if not self.get_attribute('fragment_tag') and not self.get_attribute('fragment') and not self.get_attribute(
                    'name_of_fragment'):
                if wma_type == 'LHEStepZero' and self.get_attribute('mcdb_id') <= 0:
                    raise Exception('No CVS Production Tag is defined. No fragement name, No fragment text')
        for cmsDriver in self.build_cmsDrivers():
            if 'conditions' not in cmsDriver:
                raise Exception('Conditions are not defined in %s' % (cmsDriver))

        return True

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
            notification(
                subject,
                message,
                [],
                group=notification.REQUEST_OPERATIONS,
                action_objects=[self.get_attribute('prepid')],
                object_type='requests',
                base_object=self
            )
            self.notify(subject, message)

        self.reload()

    def test_success(self, message, what='Submission', with_notification=True):
        if with_notification:
            subject = '%s succeeded for request %s' % (what, self.get_attribute('prepid'))
            notification(
                subject,
                message,
                [],
                group=notification.REQUEST_OPERATIONS,
                action_objects=[self.get_attribute('prepid')],
                object_type='requests',
                base_object=self
            )
            self.notify(subject, message)

    def get_stats(self, limit_to_set=0.05, refresh=False, forced=False):
        stats_db = database('requests', url='http://vocms074.cern.ch:5984/')
        stats_workflows = stats_db.db.loadView(viewname='_design/_designDoc/_view/requests',
                                               options={'include_docs': True,
                                                        'key': '"%s"' % self.get_attribute('prepid')})['rows']
        stats_workflows = [stats_wf['doc'] for stats_wf in stats_workflows]
        mcm_reqmgr_list = self.get_attribute('reqmgr_name')
        mcm_reqmgr_name_list = [x['name'] for x in mcm_reqmgr_list]
        stats_reqmgr_name_list = [stats_wf['RequestName'] for stats_wf in stats_workflows]
        all_reqmgr_name_list = set(mcm_reqmgr_name_list).union(set(stats_reqmgr_name_list))
        self.logger.info('Stats workflows for %s: %s' % (self.get_attribute('prepid'),
                                                         dumps(list(stats_reqmgr_name_list), indent=2)))
        self.logger.info('McM workflows for %s: %s' % (self.get_attribute('prepid'),
                                                       dumps(list(mcm_reqmgr_name_list), indent=2)))
        self.logger.info('All workflows for %s: %s' % (self.get_attribute('prepid'),
                                                       dumps(list(all_reqmgr_name_list), indent=2)))
        new_mcm_reqmgr_list = []
        skippable_transitions = set(['rejected',
                                     'aborted',
                                     'failed',
                                     'rejected-archived',
                                     'aborted-archived',
                                     'failed-archived',
                                     'aborted-completed'])
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

        new_mcm_reqmgr_list = sorted(new_mcm_reqmgr_list, key=lambda workflow: '_'.join(workflow['name'].split('_')[-3]))
        old_mcm_reqmgr_list_string = dumps(mcm_reqmgr_list, indent=4, sort_keys=True)
        new_mcm_reqmgr_list_string = dumps(new_mcm_reqmgr_list, indent=4, sort_keys=True)
        changes_happen = old_mcm_reqmgr_list_string != new_mcm_reqmgr_list_string
        self.logger.info('New workflows: %s' % (dumps(new_mcm_reqmgr_list, indent=4, sort_keys=True)))
        self.set_attribute('reqmgr_name', new_mcm_reqmgr_list)

        if len(new_mcm_reqmgr_list):
            tiers_expected = self.get_tiers()
            self.logger.info('%s tiers expected: %s' % (self.get_attribute('prepid'), tiers_expected))
            collected = self.collect_outputs(new_mcm_reqmgr_list,
                                             tiers_expected,
                                             self.get_processing_strings(),
                                             self.get_attribute('dataset_name'),
                                             self.get_attribute('member_of_campaign'),
                                             skip_check=forced)

            self.logger.info('Collected outputs for %s: %s' % (self.get_attribute('prepid'),
                                                               dumps(collected, indent=4, sort_keys=True)))

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
        chained_requests = crdb.query('contains==%s' % (self.get_attribute('prepid')))
        for cr in chained_requests:
            chain = cr.get('chain', [])
            index_of_this_request = chain.index(self.get_attribute('prepid'))
            if index_of_this_request > -1 and index_of_this_request < len(chain) - 1:
                next_request = request(rdb.get(chain[index_of_this_request + 1]))
                if not next_request.get_attribute('input_dataset'):
                    input_dataset = self.get_ds_input(self.get_attribute('output_dataset'), next_request.get_attribute('sequences'))
                    next_request.set_attribute('input_dataset', input_dataset)
                    next_request.save()

        if (len(new_mcm_reqmgr_list) and
                'content' in new_mcm_reqmgr_list[-1] and
                'pdmv_present_priority' in new_mcm_reqmgr_list[-1]['content'] and
                new_mcm_reqmgr_list[-1]['content']['pdmv_present_priority'] != self.get_attribute('priority')):

            self.set_attribute('priority', new_mcm_reqmgr_list[-1]['content']['pdmv_present_priority'])
            self.update_history({'action': 'wm priority',
                                 'step': new_mcm_reqmgr_list[-1]['content']['pdmv_present_priority']})

        self.logger.info('Changes happen for %s - %s' % (self.get_attribute('prepid'), changes_happen))
        return changes_happen

    def get_stats_old(self, keys_to_import=None, override_id=None, limit_to_set=0.05,
            refresh=False, forced=False):

        # existing rwma
        if not keys_to_import:
            keys_to_import = ['pdmv_dataset_name',
                'pdmv_dataset_list', 'pdmv_status_in_DAS', 'pdmv_dataset_statuses',
                'pdmv_status_from_reqmngr', 'pdmv_evts_in_DAS', 'pdmv_open_evts_in_DAS',
                'pdmv_submission_date', 'pdmv_submission_time', 'pdmv_type',
                'pdmv_present_priority', 'pdmv_prep_id', 'pdmv_status_history_from_reqmngr']

        mcm_rr = self.get_attribute('reqmgr_name')
        __curr_output = self.get_attribute('output_dataset')

        # first trigger an update of the stats itself
        if refresh:
            from tools.stats_updater import stats_updater
            # stats driveUpdate with search option for prepid
            # on cmsdev13 machine
            updater = stats_updater()
            out = updater.update(self.get_attribute('prepid'))

        statsDB = database('stats', url='http://vocms074.cern.ch:5984/')

        changes_happen = False

        # make a connection check to stats ! Get the views
        if not statsDB.document_exists('_design/stats'):
            self.logger.error('Connection to stats DB is down. Cannot get updated statistics')
            return False

        def transfer(stats_r, keys_to_import):
            mcm_content = {}
            if not len(keys_to_import):
                keys_to_import = stats_r.keys()
            for k in keys_to_import:
                if k in stats_r:
                    mcm_content[k] = stats_r[k]
            return mcm_content

        # update all existing
        earliest_date = 0
        earliest_time = 0
        failed_to_find = []
        for (rwma_i, rwma) in enumerate(mcm_rr):
            if not statsDB.document_exists(rwma['name']):
                self.logger.error('the request %s is linked in McM already, but is not in stats DB' % (rwma['name']))
                # very likely, this request was aborted, rejected, or failed
                # connection check was done just above
                if rwma_i != 0:
                    # always keep the original request
                    changes_happen = True
                    failed_to_find.append(rwma['name'])
                stats_r = rwma['content']
            else:
                stats_r = statsDB.get(rwma['name'])

            if ('pdmv_submission_date' in stats_r and earliest_date == 0) or (
                    'pdmv_submission_date' in stats_r and int(earliest_date) > int(stats_r['pdmv_submission_date'])):
                earliest_date = stats_r['pdmv_submission_date']  # yymmdd
            if ('pdmv_submission_time' in stats_r and earliest_time == 0) or (
                    'pdmv_submission_time' in stats_r and int(earliest_time) > int(stats_r['pdmv_submission_time'])):
                earliest_time = stats_r['pdmv_submission_time']

            # no need to copy over if it has just been noticed
            # that it is not taken from stats but the mcm document itself
            if not len(failed_to_find) or rwma['name'] != failed_to_find[-1]:
                mcm_content = transfer(stats_r, keys_to_import)
                if 'content' in mcm_rr[rwma_i] and len(mcm_content) != len(mcm_rr[rwma_i]['content']):
                    changes_happen = True
                mcm_rr[rwma_i]['content'] = mcm_content

        # take out the one which were not found !
        # the original one ([0]) is never removed
        mcm_rr = filter(lambda wmr: not wmr['name'] in failed_to_find, mcm_rr)

        if (not earliest_date or not earliest_time) and len(mcm_rr):
            # this is a problem. probably the inital workflow was rejected even before stats could pick it up
            # work is meant to be <something>_<date>_<time>_<a number>
            # the date and time is UTC, while McM is UTC+2 : hence the need for rewinding two hours

            (d, t) = mcm_rr[0]['name'].split('_')[-3:-1]
            (d, t) = time.strftime(
                "%y%m%d$%H%M%S",
                time.gmtime(time.mktime(time.strptime(d + t,"%y%m%d%H%M%S")))).split('$')

            earliest_date = d
            earliest_time = t

        #
        # look for new ones
        # we could have to de-sync the following with
        # look_for_what = mcm_rr[0]['content']['prepid']
        # to pick up chained requests taskchain clones
        #
        look_for_what = self.get_attribute('prepid')
        if len(mcm_rr):
            if 'pdmv_prep_id' in mcm_rr[0]['content']:
                look_for_what = mcm_rr[0]['content']['pdmv_prep_id']  # which should be adapted on the other end to match

        if override_id:
            look_for_what = override_id
        if look_for_what:
            stats_rr = statsDB.query(query='prepid==%s' % (look_for_what), page_num=-1)
        else:
            stats_rr = []

        # order them from [0] earliest to [n] latest
        def sortRequest(r1, r2):
            if r1['pdmv_submission_date'] == r2['pdmv_submission_date']:
                return cmp(r1['pdmv_request_name'], r2['pdmv_request_name'])
            else:
                return cmp(r1['pdmv_submission_date'], r2['pdmv_submission_date'])

        stats_rr.sort(cmp=sortRequest)

        for stats_r in stats_rr:
            # only add it if not present yet
            if stats_r['pdmv_request_name'] in map(lambda d: d['name'], mcm_rr):
                continue

            # only add if the date is later than the earliest_date
            if 'pdmv_submission_date' not in stats_r:
                continue
            if stats_r['pdmv_submission_date'] and int(stats_r['pdmv_submission_date']) < int(earliest_date):
                continue
            if not override_id and int(earliest_date) == 0 and int(earliest_time) == 0:
                continue
            if (stats_r['pdmv_submission_date'] and
                    int(stats_r['pdmv_submission_date']) == int(earliest_date)):

                if (earliest_time and 'pdmv_submission_time' in stats_r and
                        stats_r['pdmv_submission_time'] and
                        int(stats_r['pdmv_submission_time']) < int(earliest_time)):

                    continue

            mcm_content = transfer(stats_r, keys_to_import)
            mcm_rr.append({'content': mcm_content,
                    'name': stats_r['pdmv_request_name']})

            changes_happen = True

        if len(mcm_rr):
            tiers_expected = self.get_tiers()
            collected = self.collect_outputs(mcm_rr, tiers_expected, self.get_processing_strings(),
                    self.get_attribute("dataset_name"), self.get_attribute("member_of_campaign"),
                    skip_check=forced)

            # 1st element which is not DQMIO
            completed = 0
            if len(collected):
                # we find the first DS not DQMIO, if not possible default to 0th elem
                __ds_to_calc = next((el for el in collected if el.find("DQMIO") == -1), collected[0])
                (valid, completed) = self.collect_status_and_completed_events(mcm_rr, __ds_to_calc)
            else:
                self.logger.error('Could not calculate completed from last request')
                completed = 0
                # above how much change do we update : 5%

            if (((float(completed) > float((1 + limit_to_set) * self.get_attribute('completed_events'))) or forced) and
                    self.get_attribute("keep_output").count(True) > 0):

                self.set_attribute('completed_events', completed)
                changes_happen = True

            # we check if output_dataset managed to change.
            # ussually when request is assigned, but no evts are generated
            # we check for done status so we wouldn't be updating old requests with changed infrastructure
            # also we change it only if we keep any output in request
            if ((__curr_output != collected) and (self.get_attribute('status') != 'done') and
                self.get_attribute("keep_output").count(True) > 0) or forced == True:

                self.logger.info("Stats update, DS differs. for %s" % (self.get_attribute("prepid")))
                self.set_attribute('output_dataset', collected)
                changes_happen = True

        self.set_attribute('reqmgr_name', mcm_rr)

        crdb = database('chained_requests')
        rdb = database('requests')
        chained_requests = crdb.query('contains==%s' % (self.get_attribute('prepid')))
        for cr in chained_requests:
            chain = cr.get('chain', [])
            index_of_this_request = chain.index(self.get_attribute('prepid'))
            if index_of_this_request > -1 and index_of_this_request < len(chain) - 1:
                next_request = request(rdb.get(chain[index_of_this_request + 1]))
                if not next_request.get_attribute('input_dataset'):
                    input_dataset = self.get_ds_input(self.get_attribute('output_dataset'), next_request.get_attribute('sequences'))
                    next_request.set_attribute('input_dataset', input_dataset)
                    next_request.save()

        if (len(mcm_rr) and 'content' in mcm_rr[-1] and
                'pdmv_present_priority' in mcm_rr[-1]['content'] and
                mcm_rr[-1]['content']['pdmv_present_priority'] != self.get_attribute('priority')):

            self.set_attribute('priority', mcm_rr[-1]['content']['pdmv_present_priority'])
            self.update_history({'action': 'wm priority',
                    'step': mcm_rr[-1]['content']['pdmv_present_priority']})

            changes_happen = True

        return changes_happen

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
                    transient_tiers = self.get_transient_tiers()
                    if len(transient_tiers) > 0:
                        tiers_expected = [x for x in tiers_expected if x not in transient_tiers]
                        self.logger.info('Expected tiers of %s after removing transien tiers: %s' % (self.get_attribute('prepid'), tiers_expected))

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
                              'analysis_id',
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
        # could reverse engineer the target
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

    def get_timeout_for_runtest(self):
        fraction = settings.get_value('test_timeout_fraction')
        timeout = settings.get_value('batch_timeout') * 60. * fraction

        # if by default it is not possible to run a test => 0 events in
        if self.get_n_for_test(self.target_for_test(), adjust=False) == 0:
            # adjust the timeout for 10 events !
            timeout = self.get_n_unfold_efficiency(settings.get_value('test_target_fallback')) * self.get_sum_time_events()
        return (fraction, timeout)

    def get_timeout(self):
        default = settings.get_value('batch_timeout') * 60.
        # we multiply the timeout if user wants more events in validation
        multiplier = self.get_attribute('validation').get('time_multiplier', 1)
        default = multiplier * default
        # to get the contribution from runtest
        (fraction, estimate_rt) = self.get_timeout_for_runtest()
        return int(max((estimate_rt) / fraction, default))

    def get_n_for_valid(self):
        n_to_valid = settings.get_value('min_n_to_valid')
        val_attributes = self.get_attribute('validation')
        if 'nEvents' in val_attributes:
            if val_attributes['nEvents'] > n_to_valid:
                n_to_valid = val_attributes['nEvents']

        return self.get_n_unfold_efficiency(n_to_valid)

    def get_n_for_test(self, target=1.0, adjust=True):
        # => correct for the matching and filter efficiencies
        events = self.get_n_unfold_efficiency(target)

        # => estimate how long it will take
        total_test_time = self.get_sum_time_events() * events
        if adjust:
            fraction, timeout = self.get_timeout_for_runtest()
        else:
            fraction = settings.get_value('test_timeout_fraction')
            timeout = settings.get_value('batch_timeout') * 60. * fraction

        # we multiply the timeout if user wants more events in validation
        multiplier = self.get_attribute('validation').get('time_multiplier', 1)
        timeout = multiplier * timeout

        # check that it is not going to time-out
        # either the batch test time-out is set accordingly, or we limit the events
        self.logger.info('running %s means running for %s s, and timeout is %s' % (events, total_test_time, timeout))
        if total_test_time > timeout:
            # reduce the n events for test to fit in 75% of the timeout
            if self.get_sum_time_events():
                events = timeout / self.get_sum_time_events()
                self.logger.info('N for test was lowered to %s to not exceed %s * %s min time-out' % (
                    events, fraction, settings.get_value('batch_timeout')))
            else:
                self.logger.error('time per event is set to 0 !')

        if events >= 1:
            return int(events)
        else:
            # default to 0
            return int(0)

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

    def pickup_all_performance(self, directory):
        return self.pickup_performance(directory, 'perf')

    def pickup_performance(self, directory, what):
        whatToArgs = {'perf': 'rt'}
        try:
            xml = directory + '%s_%s.xml' % (self.get_attribute('prepid'), whatToArgs[what])
            if os.path.exists(xml):
                self.update_performance(open(xml).read(), what)
            return (True, "")
        except self.WrongTimeEvent as wte:
            raise wte
        except Exception:
            trace = traceback.format_exc()
            self.logger.error('Failed to get %s reports for %s \n %s' % (what,
                    self.get_attribute('prepid'), trace))
            return (False, trace)

    def check_gen_efficiency(self, geninfo, events_produced, events_ran):
        measured_efficiency = float(events_produced) / events_ran
        user_efficiency = self.get_efficiency()
        sigma = sqrt((measured_efficiency * (1 - measured_efficiency)) / events_ran)
        if sigma < measured_efficiency * 0.05:
            sigma = measured_efficiency * 0.05

        three_sigma = sigma * 3
        subject = 'Runtest for %s: efficiency is incorrect' % (self.get_attribute('prepid'))
        if measured_efficiency > 1:
            message = ('For the request %s measured efficiency was more than 1.\n'
                       'McM validation test measured %.8f efficiency.\n'
                       'There were %s trial events, of which %s passed filter/matching.\n'
                       'User provided efficiency %.8f * %.8f = %.8f.\n'
                       'Efficiency cannot be more than 1.\n'
                       'Please check, adjust and reset the request if necessary.') % (self.get_attribute('prepid'),
                                                                                      measured_efficiency,
                                                                                      events_ran,
                                                                                      events_produced,
                                                                                      geninfo['filter_efficiency'],
                                                                                      geninfo['match_efficiency'],
                                                                                      user_efficiency)

            self.notify(subject, message, accumulate=True)
            raise Exception(message)

        if measured_efficiency < user_efficiency - three_sigma or measured_efficiency > user_efficiency + three_sigma:
            message = ('For the request %s measured efficiency was not withing set threshold.\n'
                       'McM validation test measured %.8f efficiency.\n'
                       'There were %s trial events, of which %s passed filter/matching.\n'
                       'User provided efficiency %.8f * %.8f = %.8f.\n'
                       'McM threshold is %.8f +- %.8f.\n'
                       'Please check, adjust and reset the request if necessary.') % (self.get_attribute('prepid'),
                                                                                      measured_efficiency,
                                                                                      events_ran,
                                                                                      events_produced,
                                                                                      geninfo['filter_efficiency'],
                                                                                      geninfo['match_efficiency'],
                                                                                      user_efficiency,
                                                                                      user_efficiency,
                                                                                      three_sigma)

            self.notify(subject, message, accumulate=True)
            raise Exception(message)

    def check_time_event(self, evts_pass, evts_ran, measured_time_evt):
        timing_n_limit = settings.get_value('timing_n_limit')
        timing_fraction = settings.get_value('timing_fraction')

        # check if we ran a meaninful number of events and that measured time_event is above threshold
        # makes sense for really long events.
        if evts_pass < timing_n_limit:
            subject = 'Runtest for %s: too few events for estimate' % (self.get_attribute('prepid'))
            message = ('For the request %s, time/event=%s was given.'
                    ' Ran %s - too few to do accurate estimation') % (
                            self.get_attribute('prepid'),
                            self.get_sum_time_events(),
                            evts_pass)

            notification(subject, message, [],
                    group=notification.REQUEST_OPERATIONS,
                    action_objects=[self.get_attribute('prepid')],
                    object_type='requests',
                    base_object=self)

            self.notify(subject, message, accumulate=True)
            raise Exception(message)

        # TO-DO: change the 0.2 to value from settings DB
        if (measured_time_evt <= self.get_sum_time_events() * (1 - timing_fraction)):
            __all_values = self.get_attribute('time_event') + [measured_time_evt]
            __mean_value = float(sum(__all_values)) / max(len(__all_values), 1)

            subject = 'Runtest for %s: time per event over-estimate' % (self.get_attribute('prepid'))
            message = ('For the request %s, time/event=%s was given, %s was'
                    ' measured from %s events (ran %s).'
                    ' Not within %d%%. Setting to: %s.') % (
                        self.get_attribute('prepid'),
                        self.get_sum_time_events(),
                        measured_time_evt,
                        evts_pass,
                        evts_ran,
                        timing_fraction * 100,
                        __mean_value)

            notification(
                subject,
                message,
                [],
                group=notification.REQUEST_OPERATIONS,
                action_objects=[self.get_attribute('prepid')],
                object_type='requests',
                base_object=self)

            self.set_attribute('time_event', [__mean_value])
            self.reload()
            self.notify(subject, message, accumulate=True)
            raise self.WrongTimeEvent(message)

        elif (measured_time_evt >= self.get_sum_time_events() * (1 + timing_fraction)):
            __all_values = self.get_attribute('time_event') + [measured_time_evt]
            __mean_value = float(sum(__all_values)) / max(len(__all_values), 1)
            subject = 'Runtest for %s: time per event under-estimate.' % (self.get_attribute('prepid'))
            message = ('For the request %s, time/event=%s was given, %s was'
                    ' measured from %s events (ran %s).'
                    ' Not within %d%%. Setting to: %s.') % (
                        self.get_attribute('prepid'),
                        self.get_sum_time_events(),
                        measured_time_evt,
                        evts_pass,
                        evts_ran,
                        timing_fraction*100,
                        __mean_value)

            notification(
                subject,
                message,
                [],
                group=notification.REQUEST_OPERATIONS,
                action_objects=[self.get_attribute('prepid')],
                object_type='requests',
                base_object=self)

            self.set_attribute('time_event', [__mean_value])
            self.reload()
            self.notify(subject, message, accumulate=True)
            raise self.WrongTimeEvent(message)

        else:
            # fine tune the value
            self.logger.info("validation_test time_event fine tune. Previously:%s measured:%s, events:%s" % (
                    self.get_sum_time_events(), measured_time_evt, evts_pass))

            self.set_attribute('time_event', [measured_time_evt])

    def check_cpu_efficiency(self, cpu_time, total_time):
        # check if cpu efficiency is < 0.4 (400%) then we fail validation and set nThreads to 1
        # <TotalJobCPU>/(nThreads*<TotalJobTime>) < 0.4
        cpu_eff_threshold = settings.get_value('cpu_efficiency_threshold')
        efficinecy_exceptions = settings.get_value('cpu_eff_threshold_exceptions')
        campaign = self.get_attribute('member_of_campaign')
        prepid = self.get_attribute('prepid')
        if prepid in efficinecy_exceptions:
            cpu_eff_threshold = efficinecy_exceptions.get(prepid, 0.0)
            self.logger.info('Found %s in CPU efficiency exceptions' % (prepid))
        elif campaign in efficinecy_exceptions:
            cpu_eff_threshold = efficinecy_exceptions.get(campaign, 0.0)
            self.logger.info('Found %s in CPU efficiency exceptions' % (campaign))

        self.logger.info("Checking CPU efficinecy. Threshold: %s" % (cpu_eff_threshold))

        __test_eff = cpu_time / (self.get_core_num() * total_time)

        self.logger.info("CPU efficinecy for %s is %s" % (prepid, __test_eff))
        if  __test_eff < cpu_eff_threshold:
            self.logger.error("checking cpu efficinecy. Didnt passed the cpu efficiency check")
            subject = 'Runtest for %s: CPU efficiency too low' % (self.get_attribute('prepid'))
            message = ('For the request %s, with %s cores, CPU efficiency %s < %s.'
                    ' You should lower number of cores and memory accordingly.') % (
                        self.get_attribute('prepid'),
                        self.get_core_num(),
                        __test_eff,
                        cpu_eff_threshold)

            # we do not set the nThreads because we also need a process string in request to be set.
            # seq = self.get_attribute("sequences")
            # for el in seq:
            #     el['nThreads'] = 1

            # self.set_attribute('sequences', seq)
            # self.reload()
            notification(
                subject,
                message,
                [],
                group=notification.REQUEST_OPERATIONS,
                action_objects=[self.get_attribute('prepid')],
                object_type='requests',
                base_object=self)

            self.notify(subject, message, accumulate=True)
            raise Exception(message)

    def check_file_size(self, file_size, events_pass, events_ran):
        # size check
        if file_size > int(1.1 * sum(self.get_attribute('size_event'))):
            # notify if more than 10% discrepancy found !
            subject = 'Runtest for %s: size per event under-estimate.' % (self.get_attribute('prepid'))
            message = ('For the request %s, size/event=%s was given, %s was'
                    ' measured from %s events (ran %s).') % (
                            self.get_attribute('prepid'),
                            sum(self.get_attribute('size_event')),
                            file_size,
                            events_pass,
                            events_ran)

            notification(
                subject,
                message,
                [],
                group=notification.REQUEST_OPERATIONS,
                action_objects=[self.get_attribute('prepid')],
                object_type='requests',
                base_object=self)

            self.notify(subject, message, accumulate=True)

        self.set_attribute('size_event', [file_size])
        self.reload()

        if file_size < int(0.90 * sum(self.get_attribute('size_event'))):
            # size over-estimated
            # warn if over-estimated by more than 10%
            subject = 'Runtest for %s: size per event over-estimate' % (self.get_attribute('prepid'))
            message = ('For the request %s, size/event=%s was given, %s was'
                    ' measured from %s events (ran %s).') % (
                        self.get_attribute('prepid'),
                        sum(self.get_attribute('size_event')),
                        file_size,
                        events_pass,
                        events_ran)

            notification(
                subject,
                message,
                [],
                group=notification.REQUEST_OPERATIONS,
                action_objects=[self.get_attribute('prepid')],
                object_type='requests',
                base_object=self)

            self.notify(subject, message, accumulate=True)
            # correct the value from the runtest.
            self.set_attribute('size_event', [file_size])
            self.reload()

    def check_memory(self, memory, events_pass, events_ran):
        if memory > self.get_attribute('memory'):
            safe_margin = 1.05
            memory *= safe_margin
            if memory > 4000:
                self.logger.error("Request %s has a %s requirement of %s MB in memory exceeding 4GB." % (
                        self.get_attribute('prepid'), safe_margin, memory))

                subject = 'Runtest for %s: memory over-usage' % (self.get_attribute('prepid'))
                message = ('For the request %s, the memory usage is found to be large.'
                        ' Requiring %s MB measured from %s events (ran %s). Setting'
                        ' to high memory queue') % (
                            self.get_attribute('prepid'),
                            memory,
                            events_pass,
                            events_ran)

                notification(
                    subject,
                    message,
                    [],
                    group=notification.REQUEST_OPERATIONS,
                    action_objects=[self.get_attribute('prepid')],
                    object_type='requests',
                    base_object=self)

                self.notify(subject, message, accumulate=True)

            self.set_attribute('memory', memory)
            self.reload()

    def update_performance(self, xml_doc, what):
        total_event_in = self.get_n_for_test(self.target_for_test())

        xml_data = xml.dom.minidom.parseString(xml_doc)

        if not len(xml_data.documentElement.getElementsByTagName("TotalEvents")):
            self.logger.error("There are no TotalEvents reported, bailing out from performnace test")
            total_event = 0
        else:
            total_event = int(float(xml_data.documentElement.getElementsByTagName("TotalEvents")[-1].lastChild.data))

        if len(xml_data.documentElement.getElementsByTagName("InputFile")):
            for infile in xml_data.documentElement.getElementsByTagName("InputFile"):
                if str(infile.getElementsByTagName("InputType")[0].lastChild.data) != 'primaryFiles':
                    continue
                events_read = int(float(infile.getElementsByTagName("EventsRead")[0].lastChild.data))
                total_event_in = events_read
                break

        # check if we produced any events at all. If not there is no point for efficiency calc
        if total_event == 0 and total_event_in != 0:
            # fail it !
            self.logger.error("For %s the total number of events in output of the %s test %s is 0. ran %s" % (
                self.get_attribute('prepid'),
                what,
                total_event,
                total_event_in))
            raise Exception(
                "The test should have ran %s events in input, and produced 0 events: there is certainly something wrong with the request" % (total_event_in ))

        memory = None
        timing = None
        total_job_cpu = None
        total_job_time = None
        timing_dict = {}
        timing_methods = settings.get_value('timing_method')
        file_size = None
        for item in xml_data.documentElement.getElementsByTagName("PerformanceReport"):
            for summary in item.getElementsByTagName("PerformanceSummary"):
                for perf in summary.getElementsByTagName("Metric"):
                    name = perf.getAttribute('Name')
                    if name == 'AvgEventTime' and name in timing_methods:
                        timing_dict['legacy'] = float(perf.getAttribute('Value')) / self.get_core_num()
                    if name == 'AvgEventCPU' and name in timing_methods:
                        timing_dict['legacy'] = float(perf.getAttribute('Value'))
                    if name == 'TotalJobCPU' and name in timing_methods:
                        timing_dict['legacy'] = float(perf.getAttribute('Value'))
                        timing_dict['legacy'] = timing_dict['legacy'] / total_event_in
                    if name == 'EventThroughput' and name in timing_methods:
                        # new timing method as discussed here:
                        # https://github.com/cms-PdmV/cmsPdmV/issues/868
                        timing_dict['current'] = 1 / float(perf.getAttribute('Value'))

                    if name == 'Timing-tstoragefile-write-totalMegabytes':
                        file_size = float(perf.getAttribute('Value')) * 1024.  # MegaBytes -> kBytes
                        file_size = int(file_size / total_event)
                    if name == 'PeakValueRss':
                        memory = float(perf.getAttribute('Value'))
                    # cpu efficiency valued
                    if name == "TotalJobCPU":
                        total_job_cpu = float(perf.getAttribute('Value'))
                    if name == "TotalJobTime":
                        total_job_time = float(perf.getAttribute('Value'))

        if 'current' in timing_dict:
            timing = timing_dict['current']
        else:
            timing = timing_dict['legacy']

        self.logger.info("validation parsing values. events_passed:%s events_ran:%s total_job_cpu:%s total_job_time:%s" % (
            total_event,
            total_event_in,
            total_job_cpu,
            total_job_time))

        geninfo = None
        if len(self.get_attribute('generator_parameters')):
            geninfo = generator_parameters(self.get_attribute('generator_parameters')[-1]).json()

        self.check_gen_efficiency(geninfo, total_event, total_event_in)
        # we check cpu_eff ONLY if request is multicore
        number_of_cores = self.get_core_num()
        if number_of_cores > 1:
            self.check_cpu_efficiency(total_job_cpu, total_job_time)
        else:
            self.logger.debug("Not doing cpu efficiency check for %s core request" % (number_of_cores))

        self.check_time_event(total_event, total_event_in, timing)

        # some checks if we succeeded in parsing the values
        if file_size:
            self.check_file_size(file_size, total_event, total_event_in)

        if memory:
            self.check_memory(memory, total_event, total_event_in)

        self.update_history({'action': 'update', 'step': what})

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
        freshTransientOutputModules = []
        for s in sequences:
            keep.append(False)
            freshTransientOutputModules.append([])

        keep[-1] = True
        new_req.set_attribute('keep_output', keep)
        new_req.set_attribute('transient_output_modules', freshTransientOutputModules)
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
        to_be_transferred = ['dataset_name', 'generators', 'process_string', 'analysis_id', 'mcdb_id', 'notes', 'extension']
        for key in to_be_transferred:
            next_request.set_attribute(key, current_request.get_attribute(key))

    def reset(self, hard=True):
        # check on who's trying to do so
        if self.current_user_level <= access_rights.generator_convener and not self.get_attribute('status') in [
            'validation', 'defined', 'new']:
            raise json_base.WrongStatusSequence(self.get_attribute('status'), self.get_attribute('approval'),
                    'You have not enough karma to reset the request')

        if self.current_user_level <= access_rights.generator_convener and self.get_attribute(
                'approval') == 'validation' and self.get_attribute('status') == 'new':
            raise json_base.WrongStatusSequence(self.get_attribute('status'), self.get_attribute('approval'),
                    'Cannot reset a request when running validation')

        chains = self.get_attribute('member_of_chain')
        from json_layer.chained_request import chained_request

        crdb = database('chained_requests')
        rdb = database('requests')
        for chain in chains:
            cr = chained_request(crdb.get(chain))
            if cr.get_attribute('chain').index(self.get_attribute('prepid')) < cr.get_attribute('step'):
                # inspect the ones that would be further ahead
                for rid in cr.get_attribute('chain')[cr.get_attribute('chain').index(self.get_attribute('prepid')):]:
                    if rid == self.get_attribute('prepid'):
                        continue
                    mcm_r = request(rdb.get(rid))
                    if mcm_r.get_attribute('status') in ['submitted', 'done']:
                    # cannot reset a request that is part of a further on-going chain
                        raise json_base.WrongStatusSequence(self.get_attribute('status'), self.get_attribute('approval'),
                                'The request is part of a chain (%s) that is currently processing another request (%s) with incompatible status (%s)' % (
                                    chain, mcm_r.get_attribute('prepid'), mcm_r.get_attribute('status')))

        # If doing a soft reset, see if current status is submit/approved or submit submitted
        if not hard:
            approval = self.get_attribute('approval')
            status = self.get_attribute('status')
            if approval not in ['submit'] or status not in ['approved', 'submitted']:
                self.logger.error("Trying to soft reset %s/%s request" % (approval, status))
                raise json_base.WrongStatusSequence(status,
                                                    approval,
                                                    "You can soft reset only in submit/approved and submit/submitted")

        if hard:
            self.approve(0)

        # make sure to keep track of what needs to be invalidated in case there is
        invalidation = database('invalidations')
        req_to_invalidate = []
        ds_to_invalidate = []

        # retrieve the latest requests for it
        self.get_stats()
        # increase the revision only if there was a request in req mng, or a dataset already on the table
        increase_revision = False

        # and put them in invalidation
        for wma in self.get_attribute('reqmgr_name'):
            # save the reqname to invalidate
            req_to_invalidate.append(wma['name'])
            new_invalidation = {"object": wma['name'], "type": "request",
                    "status": "new", "prepid": self.get_attribute('prepid')}

            new_invalidation['_id'] = new_invalidation['object']
            invalidation.save(new_invalidation)

            # save all dataset to be invalidated
            if 'content' in wma and 'pdmv_dataset_list' in wma['content']:
                ds_to_invalidate.extend(wma['content']['pdmv_dataset_list'])
            if 'content' in wma and 'pdmv_dataset_name' in wma['content']:
                ds_to_invalidate.append(wma['content']['pdmv_dataset_name'])
            ds_to_invalidate = list(set(ds_to_invalidate))
            increase_revision = True

        # create datset invalidation for those datasets produced by request itself.
        # we check if dataset was produced in our previously reset workflow(-s)
        for ds in self.get_attribute("output_dataset"):
            if ds in ds_to_invalidate:
                self.logger.debug("adding new invalidation for ds: %s" % (ds))
                new_invalidation = {"object": ds, "type": "dataset", "status": "new", "prepid": self.get_attribute('prepid')}
                new_invalidation['_id'] = new_invalidation['object'].replace('/', '')
                invalidation.save(new_invalidation)
                increase_revision = True

        # do not increase version if not in an announced batch
        bdb = database('batches')
        if increase_revision:
            index = 0
            fetched_batches = []
            while len(req_to_invalidate) > index:
                # find the batch it is in
                __query = bdb.construct_lucene_query({'contains': req_to_invalidate[index: index + 20]}, boolean_operator='OR')
                fetched_batches += bdb.full_text_search('search', __query, page=-1)
                index += 20
            for b in fetched_batches:
                mcm_b = batch(b)
                if not mcm_b.get_attribute('status') in ['done', 'announced']:
                    increase_revision = False
                    # we could be done checking, but we'll move along to remove the requests from all existing non announced batches
                    mcm_b.remove_request(self.get_attribute('prepid'))

        # aditionnal value to reset
        self.set_attribute('completed_events', 0)
        self.set_attribute('reqmgr_name', [])
        self.set_attribute('config_id', [])
        self.set_attribute('output_dataset', [])
        if increase_revision:
            self.set_attribute('version', self.get_attribute('version') + 1)

        # remove the configs doc hash in reset
        hash_ids = database('configs')
        for i in range(len(self.get_attribute('sequences'))):
            hash_id = self.configuration_identifier(i)
            if hash_ids.document_exists(hash_id):
                hash_ids.delete(hash_id)

        if hard:
            self.set_status(step=0, with_notification=True)
        else:
            # Doing soft reset: we should go 1 status/approval back if request is not done
            # when done, they need to do hard reset and invalidate wf's
            self.logger.info("Soft resetting request: %s " % (self.get_attribute('prepid')))
            __approval_index = self._json_base__approvalsteps.index(self.get_attribute('approval'))
            __status_index = self._json_base__status.index(self.get_attribute('status'))
            if self.get_attribute('status') == 'submitted':
                __status_index -= 1
            self.set_attribute('approval', self._json_base__approvalsteps[__approval_index - 1])
            self.set_status(step=__status_index, with_notification=True)

    def prepare_upload_command(self, cfgs, test_string):
        directory = installer.build_location(self.get_attribute('prepid'))
        cmd = ''
        scram_arch = self.get_scram_arch()
        executable_file_name = '%supload_script_%s.sh' % (directory, self.get_attribute('prepid'))
        if 'slc7_' in scram_arch:
            cmd += '#!/bin/bash\n'
            cmd += 'cd %s \n' % directory
            cmd += 'cat > %s << \'EOF\'\n' % (executable_file_name)
            cmd += '#!/bin/bash\n'

        cmd += 'cd %s \n' % directory
        cmd += self.get_setup_file(directory, gen_script=False)
        cmd += '\n'
        cmd += 'export X509_USER_PROXY=/afs/cern.ch/user/p/pdmvserv/private/$HOSTNAME/voms_proxy.cert\n'
        cmd += 'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh\n'
        cmd += 'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n'
        cmd += "wmupload.py {1} -u pdmvserv -g ppd {0} || exit $? ;".format(" ".join(cfgs), test_string)
        if 'slc7_' in scram_arch:
            cmd += '\n\nEOF\n'
            cmd += 'chmod +x %s\n' % (executable_file_name)
            cmd += 'export SINGULARITY_CACHEDIR="/tmp/$(whoami)/singularity"\n'
            cmd += 'singularity run -B /afs -B /cvmfs --no-home docker://cmssw/cc7:latest %s\n' % (executable_file_name)

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

                        machine_name = "vocms081.cern.ch"
                        executor = ssh_executor(server=machine_name)
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

    def request_to_tasks(self, base, depend):
        tasks = []
        settings_db = database('settings')
        __DT_prio = settings_db.get('datatier_input')["value"]
        for sequence_index in range(len(self.get_attribute('sequences'))):
            task_dict = {
                "TaskName": "%s_%d" % (self.get_attribute('prepid'), sequence_index),
                "KeepOutput": True,
                "ConfigCacheID": None,
                "GlobalTag": self.get_attribute('sequences')[sequence_index]['conditions'],
                "CMSSWVersion": self.get_attribute('cmssw_release'),
                "ScramArch": self.get_scram_arch(),
                "PrimaryDataset": self.get_attribute('dataset_name'),
                "AcquisitionEra": self.get_attribute('member_of_campaign'),
                "Campaign": self.get_attribute('member_of_campaign'),
                "ProcessingString": self.get_processing_string(sequence_index),
                "TimePerEvent": self.get_attribute("time_event")[sequence_index],
                "SizePerEvent": self.get_attribute('size_event')[sequence_index],
                "Memory": self.get_attribute('memory'),
                "FilterEfficiency": self.get_efficiency(),
                "PrepID": self.get_attribute('prepid')}
            # check if we have multicore an it's not an empty string
            if 'nThreads' in self.get_attribute('sequences')[sequence_index] and self.get_attribute('sequences')[sequence_index]['nThreads']:
                task_dict["Multicore"] = int(self.get_attribute('sequences')[sequence_index]['nThreads'])
            __list_of_steps = self.get_list_of_steps(self.get_attribute('sequences')[sequence_index]['step'])
            if len(self.get_attribute('config_id')) > sequence_index:
                task_dict["ConfigCacheID"] = self.get_attribute('config_id')[sequence_index]
            if len(self.get_attribute('keep_output')) > sequence_index:
                task_dict["KeepOutput"] = self.get_attribute('keep_output')[sequence_index]
            if self.get_attribute('pileup_dataset_name').strip():
                task_dict["MCPileup"] = self.get_attribute('pileup_dataset_name')
            # due to discussion in https://github.com/dmwm/WMCore/issues/7398
            if self.get_attribute('version') > 0:
                task_dict["ProcessingVersion"] = self.get_attribute('version')
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
            task_dict['_output_tiers_'] = self.get_attribute('sequences')[sequence_index]["eventcontent"]
            task_dict['output_'] = "%soutput" % (self.get_attribute('sequences')[sequence_index]['eventcontent'][0])
            task_dict['priority_'] = self.get_attribute('priority')
            task_dict['request_type_'] = self.get_wmagent_type()
            transient_output_modules = self.get_attribute('transient_output_modules')
            if len(transient_output_modules) > sequence_index:
                if transient_output_modules[sequence_index]:
                    task_dict['TransientOutputModules'] = transient_output_modules[sequence_index]

            tasks.append(task_dict)
        return tasks

    def get_sum_time_events(self):
        """
        return sum of time_events for request
        """
        return sum(self.get_attribute("time_event"))

    def any_negative_events(self, field):
        """
        return True if there is a negative or zero value in time_event/size_event list
        """
        return any(n <= 0 for n in self.get_attribute(field))

    def reset_validations_counter(self):
        """
        Set validation.validations_count to 0
        """
        self.get_attribute('validation')['validations_count'] = 0

    def inc_validations_counter(self):
        """
        Increment validation.validations_count by 1
        """
        validations_count = self.get_validations_count() + 1
        self.get_attribute('validation')['validations_count'] = validations_count
        request_db = database('requests')
        saved = request_db.update(self.json())
        if not saved:
            self.logger.error('Could not save ' + self.get_attribute('prepid'))

        self.reload(save_current=False)

    def get_validations_count(self):
        """
        Return validation.validations_count
        """
        validations_count = self.get_attribute('validation').get('validations_count')
        if validations_count is None:
            validations_count = 0

        return validations_count

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
