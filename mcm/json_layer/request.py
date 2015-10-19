#!/usr/bin/env python

import os
import re
import pprint
import xml.dom.minidom
from math import sqrt
import hashlib
import copy
import traceback
import time

from couchdb_layer.mcm_database import database

from json_layer.json_base import json_base
from json_layer.campaign import campaign
from json_layer.flow import flow
from json_layer.batch import batch
from json_layer.generator_parameters import generator_parameters
from json_layer.sequence import sequence
from tools.ssh_executor import ssh_executor
from tools.locator import locator
from tools.installer import installer
from tools.settings import settings
from tools.locker import locker
from tools.user_management import access_rights

class request(json_base):
    class DuplicateApprovalStep(Exception):
        def __init__(self, approval=None):
            self.__approval = repr(approval)
            request.logger.error('Duplicate Approval Step: Request has already been %s approved' % (
                    self.__approval))

        def __str__(self):
            return 'Duplicate Approval Step: Request has already been \'' + self.__approval + '\' approved'

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'history': [],
        'priority': 20000,
        #'completion_date':'',
        'cmssw_release': '',
        'input_dataset': '',
        'output_dataset': [],
        'pwg': '',
        'validation': {},
        'dataset_name': '',
        'pileup_dataset_name': '',
        #'www':'',
        'process_string': '',
        'extension': 0,
        #'input_block':'',
        'block_black_list': [],
        'block_white_list': [],
        'fragment_tag': '',
        #'pvt_flag':'',
        #'pvt_comment':'',
        'mcdb_id': -1,
        'notes': '',
        #'description':'',
        #'remarks':'',
        'completed_events': -1,
        'total_events': -1,
        'member_of_chain': [],
        'member_of_campaign': '',
        'flown_with': '',
        'time_event': float(-1),
        'size_event': -1,
        'memory': 2300, ## the default until now
        #'nameorfragment':'',
        'name_of_fragment': '',
        'fragment': '',
        'config_id': [],
        'version': 0,
        'status': '',
        'type': '',
        'keep_output': [], ## list of booleans
        'generators': [],
        'sequences': [],
        'generator_parameters': [],
        'reqmgr_name': [], # list of tuples (req_name, valid)
        'approval': '',
        'analysis_id': [],
        'energy': 0.0,
        'tags': []
    }

    def __init__(self, json_input=None):

        # detect approval steps
        if not json_input: json_input = {}
        self.is_root = False
        cdb = database('campaigns')
        if 'member_of_campaign' in json_input and json_input['member_of_campaign']:
            if cdb.document_exists(json_input['member_of_campaign']):
                if cdb.get(json_input['member_of_campaign'])['root'] > 0:  # when is not root
                    self._json_base__approvalsteps = ['none', 'approve', 'submit']
                    self._json_base__status = ['new', 'approved', 'submitted', 'done']
                else:
                    self.is_root = True

            else:
                raise Exception('Campaign %s does not exist in the database' % (
                        json_input['member_of_campaign']))

        else:
            raise Exception('Request is not a member of any campaign')

        self._json_base__schema['status'] = self.get_status_steps()[0]
        self._json_base__schema['approval'] = self.get_approval_steps()[0]

        # update self according to json_input
        self.setup()
        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()

    def set_status(self, step=-1, with_notification=False, to_status=None):
        ## call the base
        json_base.set_status(self, step, with_notification)
        ## and set the last_status of each chained_request I am member of, last
        crdb = database('chained_requests')
        for inchain in self.get_attribute('member_of_chain'):
            if crdb.document_exists(inchain):
                from json_layer.chained_request import chained_request

                chain = chained_request(crdb.get(inchain))
                a_change = False
                a_change += chain.set_last_status(self.get_attribute('status'))
                a_change += chain.set_processing_status(self.get_attribute('prepid'),
                        self.get_attribute('status'))

                if a_change:
                    crdb.save(chain.json())

    def get_editable(self):
        editable = {}
        ## prevent anything to happen during validation procedure.
        if self.get_attribute('status') == 'new' and self.get_attribute('approval') == 'validation':
            for key in self._json_base__schema:
                editable[key] = False
            return editable

        if self.get_attribute('status') != 'new': ## after being new, very limited can be done on it
            for key in self._json_base__schema:
                ## we want to be able to edit total_events untill approved status
                if self._json_base__status.index(self.get_attribute("status")) <= 2 and key == "total_events":
                    editable[key] = True
                else:
                    editable[key] = False

            if self.current_user_level != 0: ## not a simple user
                always_editable = settings().get_value('editable_request')
                for key in always_editable:
                    editable[key] = True
            if self.current_user_level > 3: ## only for admins
                for key in self._json_base__schema:
                    editable[key] = True
        else:
            for key in self._json_base__schema:
                editable[key] = True
            if self.current_user_level <= 3: ## only for not admins
                not_editable = settings().get_value('not_editable_request')
                for key in not_editable:
                    editable[key] = False

        return editable

    def check_with_previous(self, previous_id, rdb, what, and_set=False):
        previous_one = request( rdb.get( previous_id ) )
        previous_events = previous_one.get_attribute('total_events')
        if previous_one.get_attribute('completed_events')>0:
            previous_events = previous_one.get_attribute('completed_events')
        total_events_should_be = previous_events * self.get_efficiency()
        margin = int(total_events_should_be *1.2)
        if self.get_attribute('total_events') > margin: ## safety factor of 20%
            raise self.WrongApprovalSequence(self.get_attribute('status'), what,
                    'The requested number of events (%d > %d) is much larger than what can be obtained (%d = %d*%5.2f) from previous request' %(
                        self.get_attribute('total_events'), margin,
                        total_events_should_be, previous_events,
                        self.get_efficiency()))
        if and_set:
            if self.get_attribute('total_events')>0:
                ## do not overwrite the number for no reason
                return
            from math import log10
            # round to a next 1% unit = 10^(-2) == -2 below
            rounding_unit = 10**int( max(log10(total_events_should_be)-2,0))
            self.set_attribute('total_events', int(1+total_events_should_be / float(rounding_unit))*int(rounding_unit))

    def ok_to_move_to_approval_validation(self, for_chain=False):
        message = ""
        if self.current_user_level == 0:
            ##not allowed to do so
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                    'bad user admin level %s' % (self.current_user_level))

        if not self.correct_types():
            raise TypeError("Wrong type of attribute, cannot move to approval validation of request {0}".format(
                self.get_attribute('prepid')))

        if self.get_attribute('status') != 'new':
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation')

        if not self.get_attribute('cmssw_release') or self.get_attribute('cmssw_release') == 'None':
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                    'The release version is undefined')

        if self.get_scram_arch() == None:
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                    'The architecture is invalid, probably has the release %s being deprecated' % (
                            self.get_attribute('cmssw_release')))

        bad_characters = [' ', '?', '/', '.']
        if not self.get_attribute('dataset_name') or any(
                map(lambda char: char in self.get_attribute('dataset_name'), bad_characters)):
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                    'The dataset name is invalid: either null string or containing %s' % (
                            ','.join(bad_characters)))

        other_bad_characters = [' ','-']
        if self.get_attribute('process_string') and any(
            map(lambda char: char in self.get_attribute('process_string'), other_bad_characters)):
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                    'The process string (%s) contains a bad character %s' %(
                            self.get_attribute('process_string'),
                            ','.join( other_bad_characters )))

        gen_p = self.get_attribute('generator_parameters')
        if not len(gen_p) or generator_parameters(gen_p[-1]).isInValid():
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                    'The generator parameters is invalid: either none or negative or null values, or efficiency larger than 1')

        gen_p[-1] = generator_parameters(gen_p[-1]).json()
        self.set_attribute('generator_parameters', gen_p)

        if not len(self.get_attribute('generators')):
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                    'There should be at least one generator mentioned in the request')

        if self.get_attribute('time_event') <= 0 or self.get_attribute('size_event') <= 0:
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                    'The time per event or size per event are invalid: negative or null')

        if not self.get_attribute('fragment') and (
            not ( self.get_attribute('name_of_fragment') and self.get_attribute('fragment_tag'))):
            if self.get_attribute('mcdb_id') > 0 and not self.get_attribute('input_dataset'):
                ##this case is OK
                pass
            else:
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                        'The configuration fragment is not available. Neither fragment or name_of_fragment are available')

        if self.get_attribute('name_of_fragment') and self.get_attribute('fragment_tag'):
            if re.match('^[\w/.-]+$', self.get_attribute('name_of_fragment')) is None:
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                        'The configuration fragment {0} name contains illegal characters'.format(
                                self.get_attribute('name_of_fragment')))

            for line in self.parse_fragment():
                if 'This is not the web page you are looking for' in line:
                    raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                            'The configuration fragment does not exist in git')

                if 'Exception Has Occurred' in line:
                    raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                            'The configuration fragment does not exist in cvs')

        if self.get_attribute('total_events') < 0 and not for_chain:
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                    'The number of requested event is invalid: Negative')

        if self.get_wmagent_type() == 'LHEStepZero':
            if self.get_attribute('mcdb_id') == 0:
                nevents_per_job = self.numberOfEventsPerJob()
                if not nevents_per_job:
                    raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                            'The number of events per job cannot be retrieved for lhe production')

                elif nevents_per_job >= self.get_attribute('total_events'):
                    raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                            'The number of events per job is greater or equal to the number of events requested')

            if self.get_attribute('mcdb_id') < 0:
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                        'The request should have a positive of null mcdb id')

        cdb = database('campaigns')
        mcm_c = cdb.get(self.get_attribute('member_of_campaign'))
        rdb = database('requests')

        ## same thing but using db query => faster
        find_similar = ['dataset_name==%s' % (self.get_attribute('dataset_name')),
                'member_of_campaign==%s' % ( self.get_attribute('member_of_campaign'))]

        if self.get_attribute('process_string'):
            find_similar.append('process_string==%s' % ( self.get_attribute('process_string')))
        similar_ds = rdb.queries(find_similar)

        if len(similar_ds) > 1:
            #if len(similar_ds)>2:
            #    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','Three or more requests with the same dataset name, same process string in the same campaign')
            #if similar_ds[0]['extension'] == similar_ds[1]['extension']:
            #    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','Two requests with the same dataset name, same process string and they are not extension of each other')
            my_extension = self.get_attribute('extension')
            my_id = self.get_attribute('prepid')
            my_process_string = self.get_attribute('process_string')

            for similar in similar_ds:
                if similar['prepid'] == my_id: continue
                if (int(similar['extension']) == int(my_extension)) and (my_process_string == similar["process_string"]):
                    self.logger.log("ApprovalSequence similar prepid: %s" % (similar["prepid"]))
                    raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                            'Two requests with the same dataset name, same process string and they are the same extension mumber (%s)' % (
                            my_extension))
            # check whether there are similar requests (same mcdb_id, campaign and number of events) if the campaign is a root campaign
        #if mcm_c['root'] == 0 and self.get_attribute('mcdb_id') > 0:
        #    rdb.raw_query('mcdb_check', {'key': [mcm_c['prepid'], self.get_attribute('mcdb_id'), self.get_attribute('total_events')], 'group': True})

        ##this below needs fixing
        if not len(self.get_attribute('member_of_chain')):
            #not part of any chains ...
            if self.get_attribute('mcdb_id') >= 0 and not self.get_attribute('input_dataset'):
                if mcm_c['root'] in [-1, 1]:
                    ##only requests belonging to a root==0 campaign can have mcdbid without input before being in a chain
                    raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                            'The request has an mcdbid, not input dataset, and not member of a root campaign.')

            if self.get_attribute('mcdb_id') > 0 and self.get_attribute('input_dataset') and self.get_attribute('history')[0]['action'] != 'migrated':
                ## not a migrated request, mcdb
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                        'The request has an mcdbid, an input dataset, not part of a chain, and not a result of a migration.')

        else:
            crdb = database('chained_requests')
            for cr in self.get_attribute('member_of_chain'):
                mcm_cr = crdb.get(cr)
                request_is_at = mcm_cr['chain'].index(self.get_attribute('prepid'))
                if request_is_at != 0:
                    ## just remove and_set=for_chain to have the value set automatically
                    # https://github.com/cms-PdmV/cmsPdmV/issues/623
                    self.check_with_previous( mcm_cr['chain'][request_is_at-1], rdb, 'validation' , and_set=for_chain) 

                if for_chain:
                    continue

                if request_is_at != 0:
                    if self.get_attribute('mcdb_id') >= 0 and not self.get_attribute('input_dataset'):
                        raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                                'The request has an mcdbid, not input dataset, and not considered to be a request at the root of its chains.')

                if request_is_at != mcm_cr['step']:
                    raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                            'The request is not the current step of chain %s' % (
                                    mcm_cr['prepid']))

        ## check on chagnes in the sequences
        if len(self.get_attribute('sequences')) != len(mcm_c['sequences']):
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                    'The request has a different number of steps than the campaigns it belong to')

        def in_there(seq1, seq2):
            items_that_do_not_matter = ['conditions', 'datatier', 'eventcontent']
            for (name, item) in seq1.json().items():
                if name in items_that_do_not_matter:
                    #there are parameters which do not require specific processing string to be provided
                    continue
                if name in seq2.json():
                    if item != seq2.json()[name]:
                        return False
                else:
                    if item == '':
                        #do not care about parameters that are absent, with no actual value
                        return True
                    return False
                ## arived here, all items of seq1 are identical in seq2
            return True

        matching_labels = set([])
        for (i_seq, seqs) in enumerate(mcm_c['sequences']):
            self_sequence = sequence(self.get_attribute('sequences')[i_seq])
            this_matching = set([])
            for (label, seq_j) in seqs.items():
                seq = sequence(seq_j)
                # label = default , seq = dict
                if in_there(seq, self_sequence) and in_there(self_sequence, seq):
                    ## identical sequences
                    self.logger.log('identical sequences %s' % label)
                    this_matching.add(label)
                else:
                    self.logger.log('different sequences %s \n %s \n %s' % (label,
                            seq.json(), self_sequence.json()))

            if len(matching_labels) == 0:
                matching_labels = this_matching
                self.logger.log('Matching labels %s' % matching_labels)
            else:
                # do the intersect
                matching_labels = matching_labels - (matching_labels - this_matching)
                self.logger.log('Matching labels after changes %s' % matching_labels)

        ## Here we get flow process_string to check
        __flow_ps = ""
        if self.get_attribute('flown_with'):
            fdb = database('flows')
            f = fdb.get(self.get_attribute('flown_with'))
            if 'process_string' in f['request_parameters']:
                __flow_ps = f['request_parameters']['process_string']

        if len(matching_labels) == 0:
            self.logger.log('The sequences of the request is not the same as any the ones of the campaign')
            # try setting the process string ? or just raise an exception ?
            if not self.get_attribute('process_string') and not __flow_ps: ## if they both are empty
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'validation',
                        'The sequences of the request has been changed with respect to the campaign, but no processing string has been provided')
        else:
            if self.get_attribute('process_string') or __flow_ps: ## if both are not empty string
                message = {"message" : "Request was put to validation. Process string was provided while the sequences is the same as one of the campaign."}


        if for_chain:
            return

        ## select to synchronize status and approval toggling, or run the validation/run test
        validation_disable = settings().get_value('validation_disable')
        do_runtest = not validation_disable

        by_pass = settings().get_value('validation_bypass')
        if self.get_attribute('prepid') in by_pass:
            do_runtest = False

        if do_runtest:
            from tools.handlers import RuntestGenvalid, validation_pool
            self.logger.log('Putting request %s: to validation queue' % (
                    self.get_attribute('prepid')))

            threaded_test = RuntestGenvalid(rid=str(self.get_attribute('prepid')))
            validation_pool.add_task(threaded_test.internal_run)

            self.logger.log('Request was put to queue. Queue len: %s' % (
                    validation_pool.tasks.qsize()))

        else:
            self.set_status()

        if message:
            return message

    def ok_to_move_to_approval_define(self):
        if self.current_user_level == 0:
            ##not allowed to do so
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'define',
                    'bad user admin level %s' % (self.current_user_level))
            ## we could restrict certain step to certain role level
        #if self.current_user_role != 'generator_contact':
        #    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','bad user role %s'%(self.current_user_role))

        if self.get_attribute('status') != 'validation':
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'define')

        ## a state machine should come along and create the configuration. check the filter efficiency, and set information back
        # then toggle the status
        self.set_status()

    def ok_to_move_to_approval_approve(self, for_chain=False):
        max_user_level=1
        if for_chain:   max_user_level=0
        if self.current_user_level <= max_user_level:
            ##not allowed to do so
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'approve',
                    'bad user admin level %s' % (self.current_user_level))

        if self.is_root:
            if self.get_attribute('status') != 'defined':
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'approve')
        else:
            if self.get_attribute('status') != 'new':
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'approve')

        crdb = database('chained_requests')
        rdb = database('requests')
        for cr in self.get_attribute('member_of_chain'):
            mcm_cr = crdb.get(cr)
            request_is_at = mcm_cr['chain'].index(self.get_attribute('prepid'))
            if request_is_at != 0:
                self.check_with_previous( mcm_cr['chain'][request_is_at-1],rdb, 'approve', and_set=for_chain)
            if for_chain:
                continue

            if request_is_at != mcm_cr['step']:
                all_good=True
                chain=mcm_cr['chain'][mcm_cr['step']:]
                for r in chain:
                    if r == self.get_attribute('prepid'): continue # don't self check
                    mcm_r = request( rdb.get(r) )
                    all_good &= (mcm_r.get_attribute('status') in ['defined','validation','approved'])
                if not all_good:
                    raise self.WrongApprovalSequence(self.get_attribute('status'), 'approve',
                            'The request is not the current step of chain %s and the remaining of the chain is not in the correct status' % (mcm_cr['prepid']))
        ## start uploading the configs ?
        if not for_chain:
            self.set_status()

    def ok_to_move_to_approval_submit(self):
        if self.current_user_level < 3:
            ##not allowed to do so
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'submit',
                    'bad user admin level %s' % (self.current_user_level))

        if self.get_attribute('status') != 'approved':
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'submit')

        #if not self.is_action_root():
        if not len(self.get_attribute('member_of_chain')):
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'submit',
                    'This request is not part of any chain yet')

        at_least_an_action = self.has_at_least_an_action()
        if not at_least_an_action:
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'submit',
                    'This request does not spawn from any valid action')

        if self.get_attribute('size_event') <= 0 or self.get_attribute('time_event') <= 0:
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'submit',
                    'The time (%s) or size per event (%s) is inappropriate' % (
                    self.get_attribute('time_event'), self.get_attribute('size_event')))

        if self.get_scram_arch() == None:
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'submit',
                    'The architecture is invalid, probably has the release %s being deprecated' % (
                        self.get_attribute('cmssw_release')))
        other_bad_characters = [' ','-']
        if self.get_attribute('process_string') and any(
            map(lambda char: char in self.get_attribute('process_string'), other_bad_characters)):
            raise self.WrongApprovalSequence(self.get_attribute('status'), 'submit',
                    'The process string (%s) contains a bad character %s' %(
                        self.get_attribute('process_string'),
                        ','.join( other_bad_characters )))

        ## do a dataset collision check : remind that it requires the flows to have process_string properly set
        rdb = database('requests')
        similar_ds = rdb.queries(['dataset_name==%s'%(self.get_attribute('dataset_name'))])
        my_ps_and_t = self.get_camp_plus_ps_and_tiers()
        for (camp, my_ps, my_t) in my_ps_and_t:
            check_ingredients = map(lambda s : s.lower() , my_ps.split('_'))
            if any(map(lambda ing1: any(map(lambda ing2: ing1 in ing2 and ing1!=ing2,check_ingredients)), check_ingredients)) and self.current_user_level == 4:
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'submit',
                        "There is a duplicate string in the constructed processing (%s) string of one of the expected output dataset. Checking %s" % ( my_ps, check_ingredients ))
        for similar in similar_ds:
            if similar['prepid'] == self.get_attribute('prepid'): continue # no self check
            similar_r = request(similar)
            similar_ps_and_t = similar_r.get_camp_plus_ps_and_tiers()
            ## check for collision
            collisions = filter( lambda ps : ps in my_ps_and_t, similar_ps_and_t)
            if len(collisions)!=0:
                text=str(collisions)
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'submit',
                        'There is an expected output dataset naming collision with %s' % (
                                text))

        moveon_with_single_submit=True ## for the case of chain request submission
        is_the_current_one=False
        #check on position in chains
        crdb = database('chained_requests')
        rdb = database('requests')
        for c in self.get_attribute('member_of_chain'):
            mcm_cr = crdb.get(c)
            chain = mcm_cr['chain'][mcm_cr['step']:]

            ## check everything that comes after for something !=new to block automatic submission.
            for r in chain:
                if r == self.get_attribute('prepid'): continue # no self checking
                mcm_r = request( rdb.get(r) )
                ## we can move on to submit if everything coming next in the chain is new
                moveon_with_single_submit &=(mcm_r.get_attribute('status') == 'new')

        for c in self.get_attribute('member_of_chain'):
            mcm_cr = crdb.get(c)
            is_the_current_one = (mcm_cr['chain'].index(self.get_attribute('prepid')) == mcm_cr['step'])
            if not is_the_current_one and moveon_with_single_submit:
                ## check that something else in the chain it belongs to is indicating that
                raise self.WrongApprovalSequence(self.get_attribute('status'), 'submit',
                        'The request (%s)is not the current step (%s) of its chain (%s)' % (
                            self.get_attribute('prepid'), mcm_cr['step'], c))

        sync_submission = True
        if sync_submission and moveon_with_single_submit:
            # remains to the production manager to announce the batch the requests are part of
            from tools.handlers import RequestInjector, submit_pool

            _q_lock = locker.thread_lock(self.get_attribute('prepid'))
            if not locker.thread_acquire(self.get_attribute('prepid'), blocking=False):
                return {"prepid": self.get_attribute('prepid'), "results": False,
                        "message": "The request {0} request is being handled already".format(
                                self.get_attribute('prepid'))}

            threaded_submission = RequestInjector(prepid=self.get_attribute('prepid'),
                    check_approval=False, lock=locker.lock(self.get_attribute('prepid')),
                    queue_lock=_q_lock)

            submit_pool.add_task(threaded_submission.internal_run)
        else:
            #### not settting any status forward
            ## the production manager would go and submit those by hand via McM : the status is set automatically upon proper injection

            ### N.B. send the submission of the chain automatically from submit approval of the request at the processing point of a chain already approved for chain processing : dangerous for commissioning. to be used with care
            if not moveon_with_single_submit and is_the_current_one:
                from tools.handlers import ChainRequestInjector, submit_pool

                _q_lock = locker.thread_lock(self.get_attribute('prepid'))
                if not locker.thread_acquire(self.get_attribute('prepid'), blocking=False):
                    return {"prepid": self.get_attribute('prepid'), "results": False,
                            "message": "The request {0} request is being handled already".format(
                                    self.get_attribute('prepid'))}

                threaded_submission = ChainRequestInjector(prepid=self.get_attribute('prepid'),
                        check_approval=False, lock=locker.lock(self.get_attribute('prepid')),
                        queue_lock=_q_lock)

                submit_pool.add_task(threaded_submission.internal_run)
            pass

    def is_action_root(self):
        action_db = database('actions')
        if action_db.document_exists(self.get_attribute('prepid')):
            return True
        return False

    def has_at_least_an_action(self):
        at_least_an_action = False
        crdb = database('chained_requests')
        adb = database('actions')
        for in_chain_id in self.get_attribute('member_of_chain'):
            if not crdb.document_exists(in_chain_id):
                self.logger.error(
                    'for %s there is a chain inconsistency with %s' % (
                            self.get_attribute('prepid'), in_chain_id))

                return False

            in_chain = crdb.get(in_chain_id)
            original_action = adb.get(in_chain['chain'][0])
            my_action_item = original_action['chains'][in_chain['member_of_campaign']]
            ## old convention
            if 'flag' in my_action_item and my_action_item['flag'] == True:
                at_least_an_action = True
                break
                ## new convention
            if type(my_action_item['chains']) == dict:
                for (cr, content) in my_action_item['chains'].items():
                    if content['flag']:
                        at_least_an_action = True
                        break

        return at_least_an_action


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
            #get_me = 'curl -L -s https://raw.github.com/cms-sw/genproductions/%s/python/%s --retry %s ' % (
            get_me = 'curl  -s https://raw.githubusercontent.com/cms-sw/genproductions/%s/python/%s --retry %s ' % (
                self.get_attribute('fragment_tag'), name, fragment_retry_amount )
            # add the part to make it local
            if get:
                get_me += '--create-dirs -o  Configuration/GenProduction/python/%s ' % (name)
                ##lets check if downloaded file actually exists and has more than 0 bytes
                get_me += '\n[ -s Configuration/GenProduction/python/%s ] || exit $?;\n' % (name)

        if get:
            get_me += '\n'
        return get_me

    def get_fragment(self):
        ## provides the name of the fragment depending on
        #fragment=self.get_attribute('name_of_fragment').decode('utf-8')
        fragment = self.get_attribute('name_of_fragment')
        if self.get_attribute('fragment') and not fragment:
            #fragment='Configuration/GenProduction/python/%s_fragment.py'%(self.get_attribute('prepid').replace('-','_'))
            fragment = 'Configuration/GenProduction/python/%s-fragment.py' % (
                    self.get_attribute('prepid'))

        if fragment and not fragment.startswith('Configuration/GenProduction/python/'):
            fragment = 'Configuration/GenProduction/python/' + fragment

        return fragment

    def build_cmsDriver(self, sequenceindex):
        fragment = self.get_fragment()

        ##JR
        if fragment == '':
            fragment = 'step%d' % (sequenceindex + 1)
        command = 'cmsDriver.py %s ' % fragment

        try:
            seq = sequence(self.get_attribute('sequences')[sequenceindex])
        except Exception:
            self.logger.error('Request %s has less sequences than expected. Missing step: %d' % (
                self.get_attribute('prepid'), sequenceindex), level='critical')
            return ''

        cmsDriverOptions = seq.build_cmsDriver()

        if not cmsDriverOptions.strip():
            return '%s %s' % (command, cmsDriverOptions)

        ##JR
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
                if here > 0 and here > cr['step']: # there or not at root
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
        ## last one
            command += '--fileout file:%s.root ' % (self.get_attribute('prepid'))
        else:
            command += '--fileout file:%s_step%d.root ' % (
                    self.get_attribute('prepid'), sequenceindex + 1)

        ##JR
        if self.get_attribute('pileup_dataset_name') and not (seq.get_attribute('pileup') in ['', 'NoPileUp']):
            command += '--pileup_input "dbs:%s" ' % (self.get_attribute('pileup_dataset_name'))
        elif self.get_attribute('pileup_dataset_name') and (seq.get_attribute('pileup') in ['']) and (seq.get_attribute('datamix') in ['PreMix']):
            command +=' --pileup_input "dbs:%s" '%(self.get_attribute('pileup_dataset_name'))
        return '%s%s' % (command, cmsDriverOptions)

    def transfer_from(self, camp):
        keys_to_transfer = ['energy', 'cmssw_release', 'pileup_dataset_name', 'type', 'input_dataset']
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
            ## putting things together from the campaign+flow
            freshSeq = []
            freshKeep = []
            if flownWith:
                request.put_together(camp, flownWith, self)
            else:
                for i in range(len(camp.get_attribute('sequences'))):
                    fresh = sequence(camp.get_attribute('sequences')[i]["default"])
                    freshSeq.append(fresh.json())
                    freshKeep.append(False) #dimension keep output to the sequences
                freshKeep[-1] = True #last output must be kept
                self.set_attribute('sequences', freshSeq)
                self.set_attribute('keep_output', freshKeep)
            if can_save:
                self.update_history({'action' : 'reset', 'step' : 'option'})
                self.reload()

    def reset_options(self, can_save=True):
        # a way of resetting the sequence and necessary parameters
        if self.get_attribute('status') == 'new':
            self.set_attribute('cmssw_release', '')
            self.set_attribute('pileup_dataset_name', '')
            self.set_attribute('output_dataset', [])
            freshSeq = []
            freshKeep = []
            for i in range(len(self.get_attribute('sequences'))):
                freshSeq.append(sequence().json())
                freshKeep.append(False)
            freshKeep[-1] = True
            self.set_attribute('sequences', freshSeq)
            self.set_attribute('keep_output', freshKeep)
            ##then update itself in DB
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

    def get_tier(self,i):
        s = self.get_attribute('sequences')[i]
        tiers = s['datatier']
        if isinstance(tiers, str):
            tiers = tiers.split(',')
        ## the first tier is the main output : reverse it
        return list(reversed(tiers))

    def get_tiers(self):
        r_tiers=[]
        keeps = self.get_attribute('keep_output')
        for (i, s) in enumerate(self.get_attribute('sequences')):
            if i < len(keeps) and not keeps[i]: continue
            r_tiers.extend( self.get_tier(i) )
        ## the last tier is the main output : reverse it
        return list(reversed(r_tiers))

    def get_outputs(self):
        outs = []
        keeps = self.get_attribute('keep_output')

        camp = self.get_attribute('member_of_campaign')
        dsn = self.get_attribute('dataset_name')
        v = self.get_attribute('version')

        for (i, s) in enumerate(self.get_attribute('sequences')):
            if i < len(keeps) and not keeps[i]: continue
            proc = self.get_processing_string(i)
            tiers = s['datatier']
            if isinstance(tiers, str):
                ##only for non-migrated requests
                tiers = tiers.split(',')
            for t in tiers:
                outs.append('/%s/%s-%s-v%s/%s' % (
                        dsn, camp, proc, v,t))

        return outs

    def get_processing_string(self, i):
        ingredients = []
        if self.get_attribute('flown_with'):
            fdb = database('flows')
            f = fdb.get(self.get_attribute('flown_with'))
            if 'process_string' in f['request_parameters']:
                ingredients.append(f['request_parameters']['process_string'])
        ingredients.append(self.get_attribute('process_string'))
        ingredients.append(self.get_attribute('sequences')[i]['conditions'].replace('::All', ''))
        if self.get_attribute('extension'):
            ingredients.append("ext%s" % self.get_attribute('extension'))
        return "_".join(filter(lambda s: s, ingredients))

    def get_processing_strings(self):
        keeps = self.get_attribute('keep_output')
        ps = []
        for i in range(len(self.get_attribute('sequences'))):
            if i<len(keeps) and not keeps[i]: continue
            ps.append( self.get_processing_string(i) )
        return ps

    def get_camp_plus_ps_and_tiers(self):
        keeps = self.get_attribute('keep_output')
        #we should compare whole Campaign-Processstring_tag
        campaign = self.get_attribute("member_of_campaign")
        p_and_t = []
        for i in range(len(self.get_attribute('sequences'))):
            if i<len(keeps) and not keeps[i]: continue
            p_and_t.extend([(campaign, self.get_processing_string(i), tier)
                    for tier in self.get_tier(i)])
        return p_and_t

    def little_release(self):
        release_to_find = self.get_attribute('cmssw_release')
        return release_to_find.replace('CMSSW_', '').replace('_', '')

    def get_scram_arch(self):
        #economise to call many times.
        if hasattr(self, 'scram_arch'):
            return self.scram_arch
        self.scram_arch = None
        release_to_find = self.get_attribute('cmssw_release')
        import xml.dom.minidom

        release_announcement = settings().get_value('release_announcement')
        xml_data = xml.dom.minidom.parseString(os.popen('curl -s --insecure %s ' % (
                release_announcement )).read())

        for arch in xml_data.documentElement.getElementsByTagName("architecture"):
            scram_arch = arch.getAttribute('name')
            for project in arch.getElementsByTagName("project"):
                release = str(project.getAttribute('label'))
                if release == release_to_find:
                    self.scram_arch = scram_arch

        return self.scram_arch

    def make_release(self):
        makeRel = 'source  /afs/cern.ch/cms/cmsset_default.sh\n'
        makeRel += 'export SCRAM_ARCH=%s\n' % (self.get_scram_arch())
        makeRel += 'if [ -r %s/src ] ; then \n' % (self.get_attribute('cmssw_release'))
        makeRel += ' echo release %s already exists\n' % (self.get_attribute('cmssw_release'))
        makeRel += 'else\n'
        makeRel += 'scram p CMSSW ' + self.get_attribute('cmssw_release') + '\n'
        makeRel += 'fi\n'
        makeRel += 'cd ' + self.get_attribute('cmssw_release') + '/src\n'
        makeRel += 'eval `scram runtime -sh`\n' ## setup the cmssw

        return makeRel

    def get_setup_file(self, directory='', events=None, run=False, do_valid=False):
        #run is for adding cmsRun
        #do_valid id for adding the file upload

        l_type = locator()
        infile = '#!/bin/bash\n'

        if directory:
            infile += self.make_release()
        else:
            infile += self.make_release()

        ## get the fragment if need be
        infile += self.retrieve_fragment()

        infile += 'export X509_USER_PROXY=$HOME/private/personal/voms_proxy.cert\n'
        fragment_retry_amount = 2
        ##copy the fragment directly from the DB into a file
        if self.get_attribute('fragment'):
            infile += 'curl -s --insecure %spublic/restapi/requests/get_fragment/%s --retry %s --create-dirs -o %s \n' % (
                    l_type.baseurl(), self.get_attribute('prepid'),
                    fragment_retry_amount, self.get_fragment())

            ##lets check if downloaded file actually exists and has more than 0 bytes
            infile += '[ -s %s ] || exit $?;\n' %(self.get_fragment())

        # previous counter
        previous = 0

        # validate and build cmsDriver commands
        cmsd_list = ''

        configuration_names = []
        if events is None:
            events = self.get_n_for_test(self.target_for_test())

        for cmsd in self.build_cmsDrivers():
            inline_c = ''
            # check if customization is needed to check it out from cvs
            if '--customise ' in cmsd:
                cust = cmsd.split('--customise ')[1].split(' ')[0]
                toks = cust.split('.')
                cname = toks[0] + '.py'
                if len(toks) > 1:
                    cfun = toks[1]

                # add customization

                if 'GenProduction' in cname:
                    ## this works for back-ward compatiblity
                    infile += self.retrieve_fragment(name=cname)
                    ## force inline the customisation fragment in that case.
                    ## if user sets inlinde_custom to 0 we dont set it
                    if int(self.get_attribute("sequences")[-1]["inline_custom"]) != 0:
                        inline_c = '--inline_custom 1 '

            # tweak a bit more finalize cmsDriver command
            res = cmsd
            configuration_names.append(os.path.join(directory,
                    self.get_attribute('prepid') + "_" + str(previous + 1) + '_cfg.py'))

            res += '--python_filename %s --no_exec ' % ( configuration_names[-1] )

            ## add monitoring at all times...
            if '--customise ' in cmsd:
                old_cust = cmsd.split('--customise ')[1].split()[0]
                new_cust = old_cust
                new_cust += ',Configuration/DataProcessing/Utils.addMonitoring'
                res = res.replace('--customise %s' % (old_cust), '--customise %s' % (new_cust))
            else:
                res += '--customise Configuration/DataProcessing/Utils.addMonitoring '
            res += inline_c

            res += '-n ' + str(events) + ' || exit $? ; \n'
            if run:

                if previous :
                    runtest_xml_file = os.path.join(directory, "%s_%s_rt.xml" % (
                            self.get_attribute('prepid'), previous+1))

                else:
                    runtest_xml_file = os.path.join(directory, "%s_rt.xml" % (
                            self.get_attribute('prepid')))

                res += 'cmsRun -e -j %s %s || exit $? ; \n' % (
                        runtest_xml_file, configuration_names[-1])

                if events>=0 : res += 'echo %d events were ran \n' % events
                res += 'grep "TotalEvents" %s \n' % runtest_xml_file
                res += 'grep "Timing-tstoragefile-write-totalMegabytes" %s \n' % runtest_xml_file
                res += 'grep "PeakValueRss" %s \n' % runtest_xml_file
                res += 'grep "AvgEventTime" %s \n' % runtest_xml_file
                res += 'grep "AvgEventCPU" %s \n' % runtest_xml_file
                res += 'grep "TotalJobCPU" %s \n' % runtest_xml_file


            #try create a flash runtest
            if 'lhe:' in cmsd and run and self.get_attribute('mcdb_id') > 0:
                affordable_nevents = settings().get_value('n_per_lhe_test')
                max_tests = settings().get_value('max_lhe_test')
                skip_some = ''
                test_i = 0
                do_wait_for_me = False
                __cond = self.get_attribute("sequences")[0]['conditions']
                while affordable_nevents * test_i < self.get_attribute('total_events') and (max_tests<0 or test_i < max_tests):
                    res += 'cmsDriver.py lhetest --filein lhe:%s:%s --mc  --conditions %s -n %s --python lhetest_%s.py --step NONE --no_exec --no_output\n' % (
                            self.get_attribute('mcdb_id'), affordable_nevents * test_i,
                            __cond, affordable_nevents, test_i)

                    res += 'cmsRun lhetest_%s.py & \n' % ( test_i )
                    #prepare for next test job
                    test_i += 1
                    do_wait_for_me = True
                """
                res += 'cmsDriver.py lhetest --filein lhe:%s --mc --conditions auto:startup -n -1 --python lhetest_%s.py --step NONE --no_exec --no_output \n'%( self.get_attribute('mcdb_id'))
                res += 'cmsRun lhetest.py || exit $? ; \n'
                """
                wait_for_me = '''\

for job in `jobs -p` ; do
    wait $job || exit $? ;
done
            '''
                if do_wait_for_me:
                    res += wait_for_me
                #infile += res
            cmsd_list += res + '\n'

            previous += 1

        (i, c) = self.get_genvalid_setup(directory, run)
        infile += i
        cmsd_list += c

        infile += '\nscram b\n'
        infile += 'cd ../../\n'
        infile += cmsd_list
        # since it's all in a subshell, there is
        # no need for directory traversal (parent stays unaffected)

        if run and do_valid and self.genvalid_driver:
            infile += self.harverting_upload

        ## if there was a release setup, jsut remove it
        #not in dev
        if directory and not l_type.isDev():
            infile += 'rm -rf %s' % ( self.get_attribute('cmssw_release') )

        return infile

    def modify_priority(self, new_priority):
        self.set_attribute('priority', new_priority)
        self.update_history({'action': 'priority', 'step': new_priority})
        saved = self.reload()
        if not saved:
            self.logger.error('Could not save request {0} with new priority'.format(
                    self.get_attribute('prepid')))

            return False

        self.logger.log('Priority of request {0} was changed to {1}'.format(
                self.get_attribute('prepid'), new_priority))

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
            self.logger.log('tryign to change priority to %s at %s' % (
                    self.get_attribute('prepid'), new_priority))

            reqmgr_names = [reqmgr['name'] for reqmgr in self.get_attribute('reqmgr_name')]
            if len(reqmgr_names):
                ssh_exec = ssh_executor(server='cms-pdmv-op.cern.ch')
                cmd = 'export X509_USER_PROXY=/afs/cern.ch/user/p/pdmvserv/private/$HOSTNAME/voms_proxy.cert\n'
                cmd += 'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n'
                test = ""
                if loc.isDev():
                    test = '-u cmsweb-testbed.cern.ch'
                for req_name in reqmgr_names:
                    cmd += 'wmpriority.py {0} {1} {2}\n'.format(req_name, new_priority, test)
                _, stdout, stderr = ssh_exec.execute(cmd)
                self.logger.log(cmd)
                if not stdout and not stderr:
                    self.logger.error('SSH error while changing priority of {0}'.format(
                            self.get_attribute('prepid')))

                    return False
                output_text = stdout.read()
                self.logger.error('wmpriority output:\n{0}'.format(output_text))
                changed = False
                for line in output_text.split("\n"):
                    if 'Unable to change priority of workflow' in line:
                        self.logger.error("Request {0}. {1}".format(
                                self.get_attribute('prepid'), line))

                        changed = False
                    if 'Changed priority for' in line:
                        changed = True
                if not changed:
                    self.logger.error("Could not change priority because %s" % output_text)
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

        bypass = settings().get_value('campaign_valid_bypass')
        if self.get_attribute('member_of_campaign') in bypass:
            yes_to_valid = False

        return (yes_to_valid,n_to_valid)

    def get_genvalid_setup(self, directory, run):
        cmsd_list = ""
        infile = ""

        ############################################################################
        #### HERE starts a big chunk that should be moved somewhere else than here
        ## gen valid configs
        self.genvalid_driver = None
        valid_sequence = None
        (yes_to_valid, n_to_valid) = self.get_valid_and_n()
        l_type = locator()

        if not yes_to_valid:
            return ("", "")

        # to be refined using the information of the campaign
        firstSequence = self.get_attribute('sequences')[0]
        firstStep = firstSequence['step'][0]

        dump_python = ''
        genvalid_request = request(self.json())

        if firstStep == 'GEN':
            gen_valid = settings().get_value('gen_valid')
            if not gen_valid:
                return ("", "")

            cmsd_list += '\n\n'
            valid_sequence = sequence(firstSequence)
            valid_sequence.set_attribute('step', ['GEN', 'VALIDATION:genvalid_all'])
            valid_sequence.set_attribute('eventcontent', ['DQM'])
            valid_sequence.set_attribute('datatier', ['DQM'])
            ## forfeit customisation until they are made fail-safe
            valid_sequence.set_attribute('customise', '')

        elif firstStep in ['LHE', 'NONE']:
            cmsd_list += '\n\n'
            valid_sequence = sequence(firstSequence)
            ## when integrated properly
            if firstStep == 'LHE':
                wlhe_valid = settings().get_value('wlhe_valid')
                if not wlhe_valid:
                    return ("", "")
                if len(firstSequence['step']) > 1:
                    secondStep = firstSequence['step'][1]
                else:
                    secondStep = None
                if secondStep == "GEN": ##when LHE,GENSIM request we don't need
                    valid_sequence.set_attribute('step', [firstStep, #USER attribute
                        'GEN', 'VALIDATION:genvalid_all'])
                else:
                    valid_sequence.set_attribute('step', [firstStep,
                        'USER:GeneratorInterface/LHEInterface/wlhe2HepMCConverter_cff.generator',
                        'GEN', 'VALIDATION:genvalid_all'])
            else:
                lhe_valid = settings().get_value('lhe_valid')
                if not lhe_valid:
                    return "", ""
                    #genvalid_request.set_attribute('name_of_fragment', 'GeneratorInterface/LHEInterface/lhe2HepMCConverter_cff')
                #valid_sequence.set_attribute( 'step', ['GEN','VALIDATION:genvalid_all'])
                valid_sequence.set_attribute('step',
                                             ['USER:GeneratorInterface/LHEInterface/lhe2HepMCConverter_cff.generator',
                                              'GEN', 'VALIDATION:genvalid_all'])
            valid_sequence.set_attribute('eventcontent', ['DQM'])
            valid_sequence.set_attribute('datatier', ['DQM'])
            dump_python = '--dump_python' ### only there until it gets fully integrated in all releases
        if valid_sequence:
            self.setup_harvesting(directory, run)

            ## until we have full integration in the release
            genvalig_config = settings().get_value('genvalid_config')
            cmsd_list += genvalig_config
            #cmsd_list +='addpkg GeneratorInterface/LHEInterface 2> /dev/null \n'
            #cmsd_list +='curl -s http://cmssw.cvs.cern.ch/cgi-bin/cmssw.cgi/CMSSW/GeneratorInterface/LHEInterface/python/lhe2HepMCConverter_cff.py?revision=HEAD -o GeneratorInterface/LHEInterface/python/lhe2HepMCConverter_cff.py \n'
            #cmsd_list +='\nscram b -j5 \n'

            genvalid_request.set_attribute('sequences', [valid_sequence.json()])

            genvalid_python_file = os.path.join(directory, '{0}_genvalid.py'.format(self.get_attribute('prepid')))

            self.genvalid_driver = '%s --fileout file:%s_genvalid.root --mc -n %d --python_filename %s %s --no_exec || exit $? ;\n' % (
                genvalid_request.build_cmsDriver(0),
                self.get_attribute('prepid'),
                int(n_to_valid),
                genvalid_python_file,
                dump_python)
            if run:
                genvalid_xml_file = os.path.join(directory, "%s_gv.xml" % (self.get_attribute('prepid')))

                self.genvalid_driver += 'cmsRun -e -j %s %s || exit $? ; \n' % (genvalid_xml_file, genvalid_python_file)
                self.genvalid_driver += 'echo %d events were ran \n' % ( n_to_valid )
                self.genvalid_driver += 'grep "TotalEvents" %s \n' % genvalid_xml_file
                ## put back the perf report to McM ! wil modify the request object while operating on it.
                # and therefore the saving of the request will fail ...
                #self.genvalid_driver += 'curl -k --cookie /afs/cern.ch/user/v/vlimant/private/dev-cookie.txt https://cms-pdmv-dev.cern.ch/mcm/restapi/requests/perf_report/%s/eff -H "Content-Type: application/xml" -X PUT --data "@%s%s_gv.xml" \n' %(self.get_attribute('prepid'), directory, self.get_attribute('prepid'))

            cmsd_list += self.genvalid_driver + '\n'
            cmsd_list += self.harvesting_driver + '\n'

        ##that's the end of the part for gen-valid that should be somewhere else
        ############################################################################
        return infile, cmsd_list

    def setup_harvesting(self, directory, run):
        genvalid_harvesting_python_file = os.path.join(directory,
                "{0}_genvalid_harvesting.py".format(self.get_attribute('prepid')))

        get_a_GT = 'auto:startup'
        for s in self.get_attribute('sequences'):
            if 'conditions' in s:
                get_a_GT = s['conditions']
                break
        self.harvesting_driver = 'cmsDriver.py step2 --filein file:%s_genvalid.root --conditions %s --mc -s HARVESTING:genHarvesting --harvesting AtJobEnd --python_filename %s --no_exec || exit $? ; \n' % (
                self.get_attribute('prepid'), get_a_GT, genvalid_harvesting_python_file)

        if run:
            self.harvesting_driver += 'cmsRun %s || exit $? ; \n' % genvalid_harvesting_python_file

        dqm_dataset = '/RelVal%s/%s-%s_%s-genvalid-v%s/DQM' % (self.get_attribute('dataset_name'),
                self.get_attribute('cmssw_release'), self.get_attribute('member_of_campaign'),
                self.get_attribute('sequences')[0]['conditions'].replace('::All', ''),
                self.get_attribute('version'))

        dqm_file = 'DQM_V0001_R000000001__RelVal%s__%s_%s-%s-genvalid-v%s__DQM.root' % (
                self.get_attribute('dataset_name'), self.get_attribute('cmssw_release'),
                self.get_attribute('member_of_campaign'),
                self.get_attribute('sequences')[0]['conditions'].replace('::All', ''),
                self.get_attribute('version'))

        where = 'https://cmsweb.cern.ch/dqm/relval'
        l_type = locator()
        if l_type.isDev():
            where = 'https://cmsweb-testbed.cern.ch/dqm/relval'

        self.harverting_upload = ''
        self.harverting_upload += 'mv DQM_V0001_R000000001__Global__CMSSW_X_Y_Z__RECO.root %s \n' % ( dqm_file )
        self.harverting_upload += 'curl -L -s https://raw.github.com/rovere/dqmgui/master/bin/visDQMUpload -o visDQMUpload ;\n'
        self.harverting_upload += 'export X509_USER_PROXY=$HOME/private/personal/voms_proxy.cert ;\n'
        self.harverting_upload += 'python visDQMUpload %s %s &> %s || exit $? ; \n' % (
            where, dqm_file, os.path.join(directory, "dqm_upload_%s.log" % self.get_attribute('prepid')))


        ##then the url back to the validation sample in the gui !!!
        val = self.get_attribute('validation')
        ### please do not put dqm gui url inside, but outside in java view ...
        """
        val+=', %s'%( dqm_dataset )
        """
        val['dqm'] = dqm_dataset
        self.set_attribute('validation', val)


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
        ###check whether there are missing bits and pieces in the request
        ##maybe raise instead of just returning false
        wma_type = self.get_wmagent_type()
        if wma_type in ['MonteCarloFromGEN', 'ReDigi'] and not self.get_attribute('input_dataset'):
            #raise Exception('Input Dataset name is not defined.')
            return True
        if wma_type in ['MonteCarlo', 'MonteCarloFromGEN', 'LHEStepZero']:
            if not self.get_attribute('fragment_tag') and not self.get_attribute('fragment') and not self.get_attribute(
                    'name_of_fragment'):
                if wma_type == 'LHEStepZero' and self.get_attribute('mcdb_id') <= 0:
                    raise Exception('No CVS Production Tag is defined. No fragement name, No fragment text')
        for cmsDriver in self.build_cmsDrivers():
            if not 'conditions' in cmsDriver:
                raise Exception('Conditions are not defined in %s' % (cmsDriver))

        return True

    def get_actors(self, N=-1, what='author_username', Nchild=-1):
        #get the actors from itself, and all others it is related to
        actors = json_base.get_actors(self, N, what)
        crdb = database('chained_requests')
        lookedat = []
        ## initiate the list with myself
        if Nchild == 0:
            return actors

        for cr in self.get_attribute('member_of_chain'):
            ## this protection is bad against malformed db content. it should just fail badly with exception
            if not crdb.document_exists(cr):
                self.logger.error('For requests %s, the chain %s of which it is a member of does not exist.' % (
                        self.get_attribute('prepid'), cr))

                continue

            crr = crdb.get(cr)
            for (other_i, other) in enumerate(crr['chain']):
                ## skip myself
                if other == self.get_attribute('prepid'): continue
                if other in lookedat: continue
                if Nchild > 0 and other_i > Nchild: break
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
            self.notify('%s failed for request %s' % (what, self.get_attribute('prepid')), message)
        self.reload()

    def get_stats(self, keys_to_import=None, override_id=None, limit_to_set=0.05,
            refresh=False, forced=False):

        #existing rwma
        if not keys_to_import: keys_to_import = ['pdmv_dataset_name',
                'pdmv_dataset_list', 'pdmv_status_in_DAS','pdmv_dataset_statuses',
                'pdmv_status_from_reqmngr', 'pdmv_evts_in_DAS', 'pdmv_open_evts_in_DAS',
                'pdmv_submission_date', 'pdmv_submission_time', 'pdmv_type',
                'pdmv_present_priority','pdmv_prep_id']

        mcm_rr = self.get_attribute('reqmgr_name')
        __curr_output = self.get_attribute('output_dataset')

        ### first trigger an update of the stats itself
        if refresh:
            from tools.stats_updater import stats_updater
            ## stats driveUpdate with search option for prepid
            ## on cmsdev04 machine
            updater = stats_updater()
            out = updater.update(self.get_attribute('prepid'))

        statsDB = database('stats', url='http://cms-pdmv-stats.cern.ch:5984/')

        changes_happen = False

        ## make a connection check to stats ! Get the views
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

        ####
        ## update all existing
        earliest_date = 0
        earliest_time = 0
        failed_to_find = []
        for (rwma_i, rwma) in enumerate(mcm_rr):
            if not statsDB.document_exists(rwma['name']):
                self.logger.error('the request %s is linked in McM already, but is not in stats DB' % (
                        rwma['name']))

                ## very likely, this request was aborted, rejected, or failed
                ## connection check was done just above
                if rwma_i != 0:
                    ## always keep the original request
                    changes_happen = True
                    failed_to_find.append(rwma['name'])
                stats_r = rwma['content']
            else:
                stats_r = statsDB.get(rwma['name'])

            if ('pdmv_submission_date' in stats_r and earliest_date == 0) or (
                    'pdmv_submission_date' in stats_r and int(earliest_date) > int(stats_r['pdmv_submission_date'])):
                earliest_date = stats_r['pdmv_submission_date'] #yymmdd
            if ('pdmv_submission_time' in stats_r and earliest_time == 0) or (
                    'pdmv_submission_time' in stats_r and int(earliest_time) > int(stats_r['pdmv_submission_time'])):
                earliest_time = stats_r['pdmv_submission_time']

            ## no need to copy over if it has just been noticed
            ## that it is not taken from stats but the mcm document itself
            if not len(failed_to_find) or rwma['name'] != failed_to_find[-1]:
                mcm_content = transfer(stats_r, keys_to_import)
                mcm_rr[rwma_i]['content'] = mcm_content

        ## take out the one which were not found !
        # the original one ([0]) is never removed
        mcm_rr = filter(lambda wmr: not wmr['name'] in failed_to_find, mcm_rr)

        if (not earliest_date or not earliest_time) and len(mcm_rr):
            ## this is a problem. probably the inital workflow was rejected even before stats could pick it up
            #work is meant to be <something>_<date>_<time>_<a number>
            # the date and time is UTC, while McM is UTC+2 : hence the need for rewinding two hours

            (d,t) = mcm_rr[0]['name'].split('_')[-3:-1]
            (d,t) = time.strftime("%y%m%d$%H%M%S",
                    time.gmtime(time.mktime(time.strptime(
                            d+t,"%y%m%d%H%M%S")))).split('$')

            earliest_date = d
            earliest_time = t

        ####
        ## look for new ones
        ## we could have to de-sync the following with
        ## look_for_what = mcm_rr[0]['content']['prepid']
        ## to pick up chained requests taskchain clones
        ####
        look_for_what = self.get_attribute('prepid')
        if len(mcm_rr):
            if 'pdmv_prep_id' in mcm_rr[0]['content']:
                look_for_what = mcm_rr[0]['content']['pdmv_prep_id'] ## which should be adapted on the other end to match

        if override_id:
            look_for_what = override_id
        if look_for_what:
            stats_rr = statsDB.query(query='prepid==%s' % (look_for_what), page_num=-1)
        else:
            stats_rr = []

        ### order them from [0] earliest to [n] latest
        def sortRequest(r1, r2):
            if r1['pdmv_submission_date'] == r2['pdmv_submission_date']:
                return cmp(r1['pdmv_request_name'], r2['pdmv_request_name'])
            else:
                return cmp(r1['pdmv_submission_date'], r2['pdmv_submission_date'])

        stats_rr.sort(cmp=sortRequest)

        for stats_r in stats_rr:
            ## only add it if not present yet
            if stats_r['pdmv_request_name'] in map(lambda d: d['name'], mcm_rr):
                continue

            ## only add if the date is later than the earliest_date
            if not 'pdmv_submission_date' in stats_r:
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
            collected = self.collect_outputs(mcm_rr, tiers_expected, skip_check=forced)
            completed = 0
            if len(collected):
                (valid,completed) = self.collect_status_and_completed_events(mcm_rr, collected[0])
            else:
                self.logger.error('Could not calculate completed from last request')
                completed = 0
                # above how much change do we update : 5%

            if float(completed) > float((1 + limit_to_set) * self.get_attribute('completed_events')):
                changes_happen = True
            ##we check if output_dataset managed to change.
            ## ussually when request is assigned, but no evts are generated
            if __curr_output != collected:
                self.logger.log("Stats update, DS differs. for %s" % (self.get_attribute("prepid")))
                changes_happen = True
            self.set_attribute('completed_events', completed)
            self.set_attribute('output_dataset', collected)

        self.set_attribute('reqmgr_name', mcm_rr)

        if (len(mcm_rr) and 'content' in mcm_rr[-1] and
                'pdmv_present_priority' in mcm_rr[-1]['content'] and
                mcm_rr[-1]['content']['pdmv_present_priority'] != self.get_attribute('priority')):

            self.set_attribute('priority', mcm_rr[-1]['content']['pdmv_present_priority'])
            self.update_history({'action' : 'wm priority',
                    'step' : mcm_rr[-1]['content']['pdmv_present_priority']})

            changes_happen = True

        return changes_happen

    def inspect(self):
        ### this will look for corresponding wm requests, add them,
        ### check on the last one in date and check the status of the output DS for -> done
        not_good = {"prepid": self.get_attribute('prepid'), "results": False}

        # only if you are in submitted status
        ## later, we could inspect on "approved" and trigger injection
        if self.get_attribute('status') == 'submitted':
            return self.inspect_submitted()
        elif self.get_attribute('status') == 'approved':
            return self.inspect_approved()

        not_good.update({'message': 'cannot inspect a request in %s status'
                % (self.get_attribute('status'))})

        return not_good

    def inspect_approved(self):
        ## try to inject the request
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
            ### this is for automated retries of submissions of requests in approval/status submit/approved
            # this is a remnant of when submission was not done automatically on toggle submit approval
            # in the current paradigm, this automated is probably not necessary, as the failure might be genuine
            # and also, it interferes severly with chain submission
            ##from tools.handlers import RequestInjector
            ##threaded_submission = RequestInjector(prepid=self.get_attribute('prepid'), check_approval=False,
            ##                                      lock=locker.lock(self.get_attribute('prepid')))
            ##threaded_submission.start()
            ##return {"prepid": self.get_attribute('prepid'), "results": True}
            return {"prepid": self.get_attribute('prepid'), "results": False}
        else:
            not_good.update({'message': 'Not implemented yet to inspect a request in %s status and approval %s' % (
                self.get_attribute('status'), self.get_attribute('approval'))})
            return not_good

    def collect_outputs(self, mcm_rr, tiers_expected, skip_check=False):
        procstrings_expected = self.get_processing_strings()
        collected = []
        for wma in reversed(mcm_rr):
            if not 'pdmv_dataset_list' in wma['content']: continue
            those = wma['content']['pdmv_dataset_list']
            goodone = True
            if len(collected):
                for ds in those:
                    (_, dsn, proc, tier) = ds.split('/')
                    for goodds in collected:
                        (_, gdsn, gproc, gtier) = goodds.split('/')
                        if dsn != gdsn or not set(
                            gproc.split("-")).issubset(proc.split("-")):

                            goodone = False #due to #724 we check if expected
                                                        #process_string is subset of generated ones
            if goodone:
                ## reduce to what was expected of it
                those = filter(lambda dn : dn.split('/')[-1] in tiers_expected, those)
                ## reduce to what processing string were expected
                if not skip_check:
                    those = filter(lambda dn : dn.split('/')[-2].split('-')[-2] in procstrings_expected,
                            those)

                ## only add those that are not already there
                collected.extend(filter(lambda dn: not dn in collected, those))
        ## order the collected dataset in order of expected tiers
        collected = sorted(collected, lambda d1,d2 : cmp(tiers_expected.index(d1.split('/')[-1]),
                                                        tiers_expected.index(d2.split('/')[-1])))

        return collected

    def collect_status_and_completed_events(self, mcm_rr, ds_for_accounting):
        counted = 0
        valid = True
        for wma in mcm_rr:
            if not 'pdmv_dataset_statuses' in wma['content']:
                if 'pdmv_dataset_name' in wma['content'] and wma['content']['pdmv_dataset_name'] == ds_for_accounting:
                    counted = max(counted, wma['content']['pdmv_evts_in_DAS'] + wma['content']['pdmv_open_evts_in_DAS'])
                    valid *= (wma['content']['pdmv_status_in_DAS']=='VALID')
                else:
                    continue
            elif ds_for_accounting in wma['content']['pdmv_dataset_statuses']:
                counted = max(counted, wma['content']['pdmv_dataset_statuses'][ds_for_accounting]['pdmv_evts_in_DAS'] + wma['content']['pdmv_dataset_statuses'][ds_for_accounting]['pdmv_open_evts_in_DAS'])
                valid *= (wma['content']['pdmv_dataset_statuses'][ds_for_accounting]['pdmv_status_in_DAS']=='VALID')
        return (valid,counted)

    def inspect_submitted(self):
        not_good = {"prepid": self.get_attribute('prepid'), "results": False}
        ## get fresh up to date stats
        changes_happen = self.get_stats()
        mcm_rr = self.get_attribute('reqmgr_name')
        db = database('requests')
        ignore_for_status = settings().get_value('ignore_for_status')
        if len(mcm_rr):
            wma_r = mcm_rr[-1] ## the one used to check the status
            # pick up the last request of type!='Resubmission'
            for wma in reversed(mcm_rr):
                if ('content' in wma and 'pdmv_type' in wma['content'] and
                        not (wma['content']['pdmv_type'] in ignore_for_status)):
                    wma_r = wma #the one to check the number of events in output
                    break

            if ('pdmv_status_in_DAS' in wma_r['content'] and
                    'pdmv_status_from_reqmngr' in wma_r['content']):

                if wma_r['content']['pdmv_status_from_reqmngr'] in ['announced', 'normal-archived']:
                    ## this is enough to get all datasets
                    tiers_expected = self.get_tiers()
                    collected = self.collect_outputs( mcm_rr , tiers_expected )

                    ## collected as the correct order : in first place, there is what needs to be considered for accounting
                    if not len(collected):
                        not_good.update({
                                'message' : 'No output dataset have been recognized'})
                        saved = db.save(self.json())
                        return not_good

                    ## then pick up the first expected
                    ds_for_accounting = collected[0]
                    ## find its statistics
                    valid,counted= self.collect_status_and_completed_events(mcm_rr, ds_for_accounting)

                    self.set_attribute('output_dataset', collected)
                    self.set_attribute('completed_events', counted )

                    if not valid:
                        not_good.update({'message' : 'Not all outputs are valid'})
                        saved = db.save(self.json())
                        return not_good

                    ## make sure no expected tier was left behind
                    if not all( map( lambda t :  any(map(lambda dn : t==dn.split('/')[-1],
                            collected)), tiers_expected)):

                        not_good.update({'message' : 'One of the expected tiers %s has not been produced'
                                % ( tiers_expected )})

                        saved = db.save(self.json())
                        return not_good


                    if self.get_attribute('completed_events') <= 0:
                        not_good.update({
                            'message': '%s completed but with no statistics. stats DB lag. saving the request anyway.' % (
                                wma_r['content']['pdmv_dataset_name'])})
                        saved = db.save(self.json())
                        return not_good

                    if len(collected) == 0:
                        ## there was no matching tier
                        not_good.update({'message': '%s completed but no tiers match any of %s' % (
                                wma_r['content']['pdmv_dataset_name'], tiers_expected) })

                        saved = db.save(self.json())
                        return not_good
                        ## set next status: which can only be done at this stage

                    self.set_status(with_notification=True)
                    ## save the request back to db
                    saved = db.save(self.json())
                    if saved:
                        return {"prepid": self.get_attribute('prepid'), "results": True}
                    else:
                        not_good.update(
                            {'message': "Set status to %s could not be saved in DB" % (
                                self.get_attribute('status'))})

                        return not_good
                else:
                    if changes_happen: db.save(self.json())
                    not_good.update({'message': "last request %s is not ready" % (wma_r['name'])})
                    return not_good
            else:
                if changes_happen : db.save(self.json())
                not_good.update({'message': "last request %s is malformed %s" % (wma_r['name'],
                        wma_r['content'])})

                return not_good
        else:
            ## add a reset acion here, in case in prod instance ?
            not_good.update({'message': " there are no requests in request manager. Please invsetigate!"})

            return not_good

    def parse_fragment(self):
        if self.get_attribute('fragment'):
            for line in self.get_attribute('fragment').split('\n'):
                yield line
        elif self.get_attribute('name_of_fragment') and self.get_attribute('fragment_tag'):
            #for line in os.popen('curl http://cmssw.cvs.cern.ch/cgi-bin/cmssw.cgi/CMSSW/%s?revision=%s'%(self.get_attribute('name_of_fragment'),self.get_attribute('fragment_tag') )).read().split('\n'):
            for line in os.popen(self.retrieve_fragment(get=False)).read().split('\n'):
                yield line
        else:
            for line in []:
                yield line

    def numberOfEventsPerJob(self):
        fragmnt_lines = self.parse_fragment()
        for line in fragmnt_lines:
            if 'nEvents' in line:
                try:
                    numbers = re.findall(r'[0-9]+', line)
                    return int(numbers[len(numbers) - 1])
                except:
                    return None
        return None

    def textified(self):
        l_type = locator()
        view_in_this_order = ['pwg', 'prepid', 'dataset_name', 'mcdb_id', 'analysis_id', 'notes',
                'total_events', 'validation', 'approval', 'status', 'input_dataset',
                'member_of_chain', 'reqmgr_name', 'completed_events']

        text = ''
        for view in view_in_this_order:
            if self.get_attribute(view):
                if type(self.get_attribute(view)) == list:
                    for (i, item) in enumerate(self.get_attribute(view)):
                        text += '%s[%s] : %s \n' % ( view, i, pprint.pformat(item))
                elif type(self.get_attribute(view)) == int:
                    if self.get_attribute(view) > 0:
                        text += '%s : %s \n' % (view, self.get_attribute(view))
                else:
                    text += '%s : %s \n' % (view, self.get_attribute(view))
        text += '\n'
        text += '%srequests?prepid=%s' % (l_type.baseurl(), self.get_attribute('prepid'))
        return text

    def target_for_test(self):
        #could reverse engineer the target
        return settings().get_value('test_target')

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
        ## use the trick of input_dataset ?
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
            if achain and cr!=achain: continue
            forward_eff = None
            mcm_cr = crdb.get( cr )
            chain = mcm_cr['chain']
            chain = chain[ chain.index( myid):]
            for r in chain:
                if r==myid: continue
                mcm_r = request(rdb.get( r ))
                an_eff = mcm_r.get_efficiency()
                if an_eff >0:
                    if forward_eff:
                        forward_eff *= an_eff
                    else:
                        forward_eff = an_eff
            if forward_eff and forward_eff > max_forward_eff:
                max_forward_eff = forward_eff
        if bool(max_forward_eff): #to check if its not 0. as it might trigger
            return max_forward_eff # division by 0 in request_to_wma
        else:
            return 1

    def get_n_unfold_efficiency(self, target):
        if self.get_attribute('generator_parameters'):
            eff = self.get_efficiency()
            if eff != 0:
                target /= eff
        return int(target)

    def get_timeout_for_runtest(self):
        fraction = settings().get_value('test_timeout_fraction')
        timeout = settings().get_value('batch_timeout') * 60. * fraction
        ## if by default it is not possible to run a test => 0 events in
        if self.get_n_for_test( self.target_for_test(), adjust=False)==0:
            ## adjust the timeout for 10 events !
            timeout = self.get_n_unfold_efficiency( settings().get_value('test_target_fallback') ) * self.get_attribute('time_event')
        return (fraction,timeout)

    def get_timeout(self):
        default = settings().get_value('batch_timeout') * 60.

        ## to get the contribution from runtest
        (fraction, estimate_rt) = self.get_timeout_for_runtest()
        ## to get a contribution from validation is applicable
        estimate_gv = 0.
        (yes_to_valid,n) = self.get_valid_and_n()
        if yes_to_valid:
            time_per_test = settings().get_value('genvalid_time_event')
            estimate_gv = time_per_test * n * self.get_efficiency()

        ## to get a contribution from lhe test if applicable
        estimate_lhe = 0.
        if self.get_attribute('mcdb_id') > 0:
            n_per_test = settings().get_value('n_per_lhe_test')
            n_test = self.get_attribute('total_events') / n_per_test
            max_n = settings().get_value('max_lhe_test')
            time_per_test = settings().get_value('lhe_test_time_event')
            if max_n >=0:
                n_test = min(n_test, max_n)
            estimate_lhe = n_test * (time_per_test * n_per_test)

        return int(max((estimate_rt+estimate_gv+estimate_lhe) / fraction, default))
        #return int((estimate_rt+estimate_gv+estimate_lhe) / fraction)

    def get_n_for_valid(self):
        n_to_valid = settings().get_value('min_n_to_valid')
        val_attributes = self.get_attribute('validation')
        if 'nEvents' in val_attributes:
            if val_attributes['nEvents'] > n_to_valid:
                n_to_valid = val_attributes['nEvents']

        return self.get_n_unfold_efficiency(n_to_valid)

    def get_n_for_test(self, target=1.0, adjust=True):
        #=> correct for the matching and filter efficiencies
        events = self.get_n_unfold_efficiency(target)

        #=> estimate how long it will take
        total_test_time = float(self.get_attribute('time_event')) * events
        if adjust:
            fraction, timeout = self.get_timeout_for_runtest()
        else:
            fraction = settings().get_value('test_timeout_fraction')
            timeout = settings().get_value('batch_timeout') * 60. * fraction

        # check that it is not going to time-out
        ### either the batch test time-out is set accordingly, or we limit the events
        self.logger.log('running %s means running for %s s, and timeout is %s' % ( events, total_test_time, timeout))
        if total_test_time > timeout:
            #reduce the n events for test to fit in 75% of the timeout
            if self.get_attribute('time_event'):
                events = timeout / float(self.get_attribute('time_event'))
                self.logger.log('N for test was lowered to %s to not exceed %s * %s min time-out' % (
                    events, fraction, settings().get_value('batch_timeout') ))
            else:
                self.logger.error('time per event is set to 0 !')

        if events >= 1:
            return int(events)
        else:
            ##default to 0
            return int(0)

    def unique_string(self, step_i):
        ### create a string that supposedly uniquely identifies the request configuration for step
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
        #create a hash value that supposedly uniquely defines the configuration
        hash_id = hashlib.sha224(uniqueString).hexdigest()
        return hash_id

    def pickup_all_performance(self, directory):
        (success,report) = self.pickup_performance(directory, 'perf')
        if not success: return (success,report)
        (success,report) = self.pickup_performance(directory, 'eff')
        return (success,report)
    def pickup_performance(self, directory, what):
        whatToArgs={'eff' : 'gv',
                    'perf' : 'rt'}
        try:
            xml = directory + '%s_%s.xml' %( self.get_attribute('prepid'), whatToArgs[what])
            if os.path.exists(xml):
                self.update_performance(open(xml).read(), what)
            return (True,"")
        except Exception as e:
            #trace=str(e)
            trace = traceback.format_exc()
            self.logger.error('Failed to get %s reports for %s \n %s' % (what,
                    self.get_attribute('prepid'), trace))

            return (False, trace)

    def update_performance(self, xml_doc, what):
        total_event_in = self.get_n_for_test(self.target_for_test())
        total_event_in_valid = self.get_n_for_valid()

        xml_data = xml.dom.minidom.parseString(xml_doc)

        if not len(xml_data.documentElement.getElementsByTagName("TotalEvents")):
            self.logger.error("There are no TotalEvents reported, bailing out from performnace test")
            total_event = 0
        else:
            total_event = int(float(xml_data.documentElement.getElementsByTagName("TotalEvents")[-1].lastChild.data))

        if len(xml_data.documentElement.getElementsByTagName("InputFile")):
            for infile in xml_data.documentElement.getElementsByTagName("InputFile"):
                if str(infile.getElementsByTagName("InputType")[0].lastChild.data) != 'primaryFiles': continue
                events_read = int(float(infile.getElementsByTagName("EventsRead")[0].lastChild.data))
                total_event_in = events_read
                total_event_in_valid = events_read
                break

        if what == 'eff':
            if total_event == 0 and total_event_in_valid != 0:
                self.logger.error("For %s the total number of events in output of the %s test %s is 0. ran %s" % (
                    self.get_attribute('prepid'), what, total_event, total_event_in_valid))
                raise Exception(
                    "The test should have ran %s events in input, and produced 0 events: there is certainly something wrong with the request" % (
                        total_event_in_valid ))
        else:
            if total_event == 0 and total_event_in != 0:
                ##fail it !
                self.logger.error("For %s the total number of events in output of the %s test %s is 0. ran %s" % (
                    self.get_attribute('prepid'), what, total_event, total_event_in))
                raise Exception(
                    "The test should have ran %s events in input, and produced 0 events: there is certainly something wrong with the request" % (
                        total_event_in ))

        memory = None
        timing = None
        timing_method = settings().get_value('timing_method')
# Here be dragons

        file_size = None
        for item in xml_data.documentElement.getElementsByTagName("PerformanceReport"):
            for summary in item.getElementsByTagName("PerformanceSummary"):
                for perf in summary.getElementsByTagName("Metric"):
                    name = perf.getAttribute('Name')
                    if name == 'AvgEventTime' and name == timing_method:
                        timing = float(perf.getAttribute('Value'))
                    if name == 'AvgEventCPU' and name == timing_method:
                        timing = float(perf.getAttribute('Value'))
                    if name == 'TotalJobCPU' and name == timing_method:
                        timing = float(perf.getAttribute('Value'))
                        timing = timing / total_event_in
                    if name == 'Timing-tstoragefile-write-totalMegabytes':
                        file_size = float(perf.getAttribute('Value')) * 1024. # MegaBytes -> kBytes
                        file_size = int(file_size / total_event)
                    if name == 'PeakValueRss':
                        memory = float(perf.getAttribute('Value'))

        efficiency = float(total_event) / total_event_in_valid
        efficiency_error = efficiency * sqrt(1. / total_event + 1. / total_event_in_valid)

        geninfo = None
        if len(self.get_attribute('generator_parameters')):
            geninfo = generator_parameters( self.get_attribute('generator_parameters')[-1] ).json()

        to_be_saved = False

        self.logger.error("Calculated all eff: %s eff_err: %s timing: %s size: %s" % (
            efficiency, efficiency_error, timing, file_size ))

        if what == 'eff':
            do_update = False
            do_inform = False
            if not geninfo:
                do_update = True

            if do_update:
                self.update_generator_parameters()
                to_be_saved = True

            if geninfo and geninfo['filter_efficiency'] and geninfo['match_efficiency'] and efficiency:
                _eff_ratio_error = sqrt(
                    (geninfo['filter_efficiency_error'] / geninfo['filter_efficiency'])**2+
                    (geninfo['match_efficiency_error'] / geninfo['match_efficiency'])**2)
                if _eff_ratio_error > (efficiency_error / efficiency):
                    do_infom = True  ##Inform user to update the efficiencies by himself

            #efficiency_fraction = settings().get_value('efficiency_fraction')
            if geninfo:
                __eff_check = abs(geninfo["filter_efficiency"] * geninfo["match_efficiency"] - efficiency) / efficiency
                __eff_relative_error = 2*sqrt((efficiency_error/efficiency)**2 + _eff_ratio_error**2)
                if do_inform:
                    message = ('For the request %s,\n%s=%s +/- %s\n%s=%s +/- %s were given;\n'
                        ' the mcm validation test measured %.4f +/- %.4f\n'
                        '(there were %s trial events, of which %s passed the filter/matching),\n'
                        ' which has a smaller relative error. Please set new values in the'
                        ' request for efficiencies and errors.') % (
                            self.get_attribute('prepid'),
                            'filter_efficiency',
                            geninfo['filter_efficiency'],
                            geninfo['filter_efficiency_error'],
                            'match_efficiency',
                            geninfo['match_efficiency'],
                            geninfo['match_efficiency_error'],
                            efficiency,
                            efficiency_error,
                            total_event_in_valid,
                            total_event)
                    self.notify(
                        'Runtest for %s: efficiencies has improved.' % (
                            self.get_attribute('prepid')), message, accumulate=True)
                elif efficiency == 0.:
                    ## the efficiency, although we have ran events is exactly zero ! 
                    ## should have failed a few lines above anyways
                    message = ('For the request %s,\n%s=%s\n%s=%s were given;\n'
                        '%.4f was measured from %s trial events, of which %s'
                        ' passed the filter/matching.\nPlease check efficiencies'
                        ' and reset the request if necessary.') % (
                            self.get_attribute('prepid'),
                            'filter_efficiency',
                            geninfo['filter_efficiency'],
                            'match_efficiency',
                            geninfo['match_efficiency'],
                            efficiency,
                            total_event_in_valid,
                            total_event)
                    self.notify('Runtest for %s: efficiencies seems very wrong.' % ( self.get_attribute('prepid')),
                                message, accumulate=True)
                    #raise Exception(message)
                #elif __eff_check > efficiency_fraction:
                elif __eff_check > __eff_relative_error:
                    ## efficiency is wrong by more than 0.05=efficiency_fraction : notify.
                    ## The indicated efficiency error is most likely too small or zero
                    message = ('For the request %s,\n%s=%s +/- %s\n%s=%s +/- %s'
                        ' were given; %.4f  +/- %.4f was measured'
                        ' from %s trial events, of which %s passed the filter/matching.\n'
                        ' Please check efficiencies and reset the request'
                        ' if necessary.') % (
                            self.get_attribute('prepid'),
                            'filter_efficiency',
                            geninfo['filter_efficiency'],
                            geninfo['filter_efficiency_error'],
                            'match_efficiency',
                            geninfo['match_efficiency'],
                            geninfo['match_efficiency_error'],
                            efficiency,
                            efficiency_error,
                            total_event_in_valid,
                            total_event)
                    self.notify('Runtest for %s: efficiencies seems incorrect.' % ( self.get_attribute('prepid')),
                                message, accumulate=True)
                    raise Exception(message)

        elif what == 'perf':
            rough_efficiency = float(total_event) / total_event_in
            rough_efficiency_error = rough_efficiency * sqrt(1. / total_event + 1. / total_event_in)

            ## do a rough efficiency measurements anyways if the request is not valid enable
            if geninfo and (
                    not 'valid' in self.get_attribute('validation') or not self.get_attribute('validation')['valid']):
                #efficiency_fraction = settings().get_value('efficiency_fraction')
                __eff_check = abs(geninfo["filter_efficiency"] * geninfo["match_efficiency"] - rough_efficiency) / rough_efficiency
                _eff_ratio_error = sqrt(
                    (geninfo['filter_efficiency_error'] / geninfo['filter_efficiency'])**2+
                    (geninfo['match_efficiency_error'] / geninfo['match_efficiency'])**2)
                __eff_error = 2*sqrt((rough_efficiency_error/rough_efficiency)**2 + _eff_ratio_error**2)
                if __eff_check > __eff_error:
                    self.notify('Runtest for %s: efficiency seems incorrect from rough estimate.' % (
                        self.get_attribute('prepid')),
                        ('For the request %s,\n%s=%s +/- %s\n%s=%s +/- %s were given;\n'
                        ' the mcm validation test measured %.4f +/- %.4f\n'
                        '(there were %s trial events, of which %s passed the filter/matching),'
                        ' which has a smaller relative error.\n'
                        'Please check and reset the request if necessary.') % (
                            self.get_attribute('prepid'),
                            'filter_efficiency',
                            geninfo['filter_efficiency'],
                            geninfo['filter_efficiency_error'],
                            'match_efficiency',
                            geninfo['match_efficiency'],
                            geninfo['match_efficiency_error'],
                            rough_efficiency,
                            rough_efficiency_error,
                            total_event_in,
                            total_event),
                    accumulate=True)

            ## timing checks
            timing_fraction = settings().get_value('timing_fraction')
            timing_threshold = settings().get_value('timing_threshold')
            timing_n_limit = settings().get_value('timing_n_limit')
            if timing and timing > self.get_attribute('time_event'):
                ## timing under-estimated
                if timing * timing_fraction > self.get_attribute('time_event'):
                    ## notify if more than 20% discrepancy found !
                    self.notify(
                        'Runtest for %s: time per event under-estimate.' % (
                            self.get_attribute('prepid')),
                        ('For the request %s, time/event=%s was given, %s was measured'
                        ' and set to the request from %s events (ran %s).') % (
                            self.get_attribute('prepid'),
                            self.get_attribute('time_event'),
                            timing, total_event,
                            total_event_in),
                        accumulate=True)

                self.set_attribute('time_event', timing)
                to_be_saved = True
            if timing and timing < (timing_fraction * self.get_attribute('time_event')):
                ## timing over-estimated
                ## warn if over-estimated by more than 10%
                subject = 'Runtest for %s: time per event over-estimate.' % (self.get_attribute('prepid'))
                if total_event > timing_n_limit or timing < timing_threshold:
                    message = ('For the request %s, time/event=%s was given, %s was'
                        ' measured and set to the request from %s events (ran %s).') % (
                            self.get_attribute('prepid'),
                            self.get_attribute('time_event'),
                            timing,
                            total_event,
                            total_event_in)

                    self.set_attribute('time_event', timing)
                    to_be_saved = True
                else:
                    message = ('For the request %s, time/event=%s was given, %s was'
                        ' measured from %s events (ran %s). Not within %d%%.') % (
                            self.get_attribute('prepid'),
                            self.get_attribute('time_event'),
                            timing,
                            total_event,
                            total_event_in,
                            timing_fraction*100)
                    ## we should fail these requests because of wrong timing by >10% !
                    raise Exception(message)

                self.notify(subject, message, accumulate=True)

            ## size check
            if file_size and file_size > self.get_attribute('size_event'):
                ## size under-estimated
                if file_size * 0.90 > self.get_attribute('size_event'):
                    ## notify if more than 10% discrepancy found !
                    self.notify(
                        'Runtest for %s: size per event under-estimate.' % (
                            self.get_attribute('prepid')),
                        ('For the request %s, size/event=%s was given, %s was'
                        ' measured from %s events (ran %s).') % (
                            self.get_attribute('prepid'),
                            self.get_attribute('size_event'),
                            file_size,
                            total_event,
                            total_event_in),
                        accumulate=True)
                self.set_attribute('size_event', file_size)
                to_be_saved = True

            if file_size and file_size < int(0.90 * self.get_attribute('size_event')):
                ## size over-estimated
                ## warn if over-estimated by more than 10%
                self.notify(
                    'Runtest for %s: size per event over-estimate.' % (
                        self.get_attribute('prepid')),
                    ('For the request %s, size/event=%s was given, %s was'
                    ' measured from %s events (ran %s).') % (
                        self.get_attribute('prepid'),
                        self.get_attribute('size_event'),
                        file_size,
                        total_event,
                        total_event_in),
                    accumulate=True)
                ## correct the value from the runtest.
                self.set_attribute('size_event', file_size)
                to_be_saved = True

            if memory and memory > self.get_attribute('memory'):
                safe_margin = 1.05
                memory *= safe_margin
                if memory > 4000:
                    self.logger.error("Request %s has a %s requirement of %s MB in memory exceeding 4GB." % (
                        self.get_attribute('prepid'), safe_margin, memory))
                    self.notify(
                        'Runtest for %s: memory over-usage' % (
                            self.get_attribute('prepid')),
                        ('For the request %s, the memory usage is found to be large.'
                        ' Requiring %s MB measured from %s events (ran %s). Setting'
                        ' to high memory queue') % (
                            self.get_attribute('prepid'),
                            memory,
                            total_event,
                            total_event_in),
                    accumulate=True)
                    #truncate to 4G, or catch it in ->define step ?
                self.set_attribute('memory', memory)
                to_be_saved = True

        if to_be_saved:
            self.update_history({'action': 'update', 'step': what})

        return to_be_saved

    @staticmethod
    ## another copy/paste
    def put_together(nc, fl, new_req):
        # copy the sequences of the flow
        sequences = []
        for i, step in enumerate(nc.get_attribute('sequences')):
            flag = False # states that a sequence has been found
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
        ## setup the keep output parameter
        keep = []
        for s in sequences:
            keep.append(False)
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
        to_be_transferred = ['dataset_name', 'generators', 'process_string', 'analysis_id', 'mcdb_id', 'notes', 'tags', 'extension']
        for key in to_be_transferred:
            next_request.set_attribute(key, current_request.get_attribute(key))

    def reset(self, hard=True):
        ## check on who's trying to do so
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
                ## inspect the ones that would be further ahead
                for rid in cr.get_attribute('chain')[cr.get_attribute('chain').index(self.get_attribute('prepid')):]:
                    if rid == self.get_attribute('prepid'): continue
                    mcm_r = request(rdb.get( rid ))
                    if mcm_r.get_attribute('status') in ['submitted','done']:
                    ## cannot reset a request that is part of a further on-going chain
                        raise json_base.WrongStatusSequence(self.get_attribute('status'), self.get_attribute('approval'),
                                'The request is part of a chain (%s) that is currently processing another request (%s) with incompatible status (%s)' % (
                                    chain, mcm_r.get_attribute('prepid'), mcm_r.get_attribute('status')))

        if hard:
            self.approve(0)

        ## make sure to keep track of what needs to be invalidated in case there is
        invalidation = database('invalidations')
        req_to_invalidate = []
        ds_to_invalidate = []

        # retrieve the latest requests for it
        self.get_stats()
        # increase the revision only if there was a request in req mng, or a dataset already on the table
        increase_revision = False
        __ps_values = self.get_camp_plus_ps_and_tiers()

        # and put them in invalidation
        for wma in self.get_attribute('reqmgr_name'):
            ## save the reqname to invalidate
            req_to_invalidate.append(wma['name'])
            new_invalidation = {"object": wma['name'], "type": "request",
                    "status": "new", "prepid": self.get_attribute('prepid')}

            new_invalidation['_id'] = new_invalidation['object']
            invalidation.save(new_invalidation)

            ## save all dataset to be invalidated
            if 'content' in wma and 'pdmv_dataset_list' in wma['content']:
                ds_to_invalidate.extend(wma['content']['pdmv_dataset_list'])
            if 'content' in wma and 'pdmv_dataset_name' in wma['content']:
                ds_to_invalidate.append(wma['content']['pdmv_dataset_name'])
            ds_to_invalidate = list(set(ds_to_invalidate))
            increase_revision = True

        for ds in ds_to_invalidate:
            __to_invalidate = True
            ##lets check whether the rqmngr ds matches all ouput ds params.
            for p in __ps_values:
                __to_invalidate = all(ps in ds for ps in p)

                if __to_invalidate:
                    new_invalidation = {"object": ds, "type": "dataset", "status": "new", "prepid": self.get_attribute('prepid')}
                    new_invalidation['_id'] = new_invalidation['object'].replace('/', '')
                    invalidation.save(new_invalidation)
                    increase_revision = True
                    break

        ##do not increase version if not in an announced batch
        bdb = database('batches')
        if increase_revision:
            for req in req_to_invalidate:
                # find the batch it is in
                bs = bdb.queries(['contains==%s' % ( req )])
                for b in bs:
                    mcm_b = batch(b)
                    if not mcm_b.get_attribute('status') in ['done', 'announced']:
                        increase_revision = False
                        ## we could be done checking, but we'll move along to remove the requests from all existing non announced batches
                        mcm_b.remove_request(self.get_attribute('prepid'))

        ## aditionnal value to reset
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
            self.set_attribute('approval', 'approve')
            self.set_status(step=self._json_base__status.index('approved'), with_notification=True)

    def prepare_upload_command(self, cfgs, test_string):
        directory = installer.build_location(self.get_attribute('prepid'))
        cmd = 'cd %s \n' % directory
        cmd += self.get_setup_file(directory)
        cmd += '\n'
        cmd += 'export X509_USER_PROXY=/afs/cern.ch/user/p/pdmvserv/private/$HOSTNAME/voms_proxy.cert\n'
        cmd += 'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh\n'
        cmd += 'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n'
        cmd += "wmupload.py {1} -u pdmvserv -g ppd {0} || exit $? ;".format(" ".join(cfgs), test_string)
        return cmd

    def prepare_and_upload_config(self, execute=True):
        to_release = []
        config_db = database("configs")
        prepid = self.get_attribute('prepid')
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
                            self.logger.error('the release %s architecture is invalid'% self.get_attribute('member_of_campaign'))
                            self.test_failure('Problem with uploading the configurations. The release %s architecture is invalid'%self.get_attribute('member_of_campaign'), what='Configuration upload')
                            return False

                        machine_name = "cms-pdmv-op.cern.ch"
                        executor = ssh_executor(server=machine_name)
                        _, stdout, stderr = executor.execute(command)
                        if not stdout and not stderr:
                            self.logger.error('SSH error for request {0}. Could not retrieve outputs.'.format(prepid))
                            self.logger.inject('SSH error for request {0}. Could not retrieve outputs.'.format(prepid),
                                               level='error', handler=prepid)
                            self.test_failure('SSH error for request {0}. Could not retrieve outputs.'.format(prepid),
                                              what='Configuration upload')
                            return False
                        output = stdout.read()
                        error = stderr.read()
                        if error and not output:  # money on the table that it will break
                            self.logger.error('Error in wmupload: {0}'.format(error))
                            self.test_failure('Error in wmupload: {0}'.format(error), what='Configuration upload')
                            return False
                        cfgs_uploaded = [l for l in output.split("\n") if 'DocID:' in l]

                        if len(cfgs_to_upload) != len(cfgs_uploaded):
                            self.logger.error(
                                'Problem with uploading the configurations. To upload: {0}, received doc_ids: {1}\nOutput:\n{2}\nError:\n{3}'.format(
                                    cfgs_to_upload, cfgs_uploaded, output, error))
                            self.logger.inject(
                                'Problem with uploading the configurations. To upload: {0}, received doc_ids: {1}\nOutput:\n{2}\nError:\n{3}'.format(
                                    cfgs_to_upload, cfgs_uploaded, output, error), level='error', handler=prepid)
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
                                self.logger.inject(
                                    'Could not save the configuration {0}'.format(self.configuration_identifier(i)),
                                    level='warning', handler=prepid)

                        self.logger.inject("Full upload result: {0}".format(output), handler=prepid)
            if execute:
                sorted_additional_config_ids = [additional_config_ids[i] for i in additional_config_ids]
                self.logger.inject("New configs for request {0} : {1}".format(prepid, sorted_additional_config_ids),
                                   handler=prepid)
                self.overwrite( {'config_id' : sorted_additional_config_ids} )
            return command
        finally:
            for i in to_release:
                locker.release(i)

    def prepare_submit_command(self, batch_name):
        from tools.request_to_wma import request_to_wmcontrol

        batch_number = batch_name.split("-")[-1]
        cmd = request_to_wmcontrol().get_command(self, batch_number, to_execute=True)
        return cmd
