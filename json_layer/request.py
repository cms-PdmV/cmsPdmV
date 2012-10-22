#!/usr/bin/env python

import copy

from json_base import json_base
from generator_parameters import generator_parameters
from comment import comment
from approval import approval
from sequence import sequence
from submission_details import submission_details

class request(json_base):
    class DuplicateApprovalStep(Exception):
        def __init__(self,  approval=None):
            self.__approval = repr(approval)
        def __str__(self):
            return 'Duplicate Approval Step: Request has already been \'' + self.__approval + '\' approved'

    def __init__(self, author_name,  author_cmsid=-1,  author_inst_code='',  author_project='', json_input={}):

        self._json_base__schema = {
            '_id':'', 
            'prepid':'',
            'priority':'',
            'status':'',
            'completion_date':'', 
            'cmssw_release':'',
            'input_filename':'',
            'pwg':'',
            'validation':'',
            'input_filename':'',
            'dataset_name':'',
            'pileup_dataset_name':'',
            'www':'',
            'process_string':'',
            'input_block':'',
            'cvs_tag':'',
            'pvt_flag':'',
            'pvt_comment':'',
            'mcdb_id':'',
            'notes':'',
            'description':'',
            'remarks':'',
            'completed_events':-1,
            'total_events':-1,
            'member_of_chain':[],
            'member_of_campaign':'',
            'time_event':-1,
            'size_event':-1,
            'gen_fragment':'', 
            'version':0,
            'status':'',
            'type':'',
            'root' :False, # flag if request is a root request or not
            'generators':'',
            'comments':[],
            'sequences':[],
            'generator_parameters':[], 
            'submission_details':submission_details().build(author_name,  author_cmsid,  author_inst_code,  author_project), 
            'reqmgr_name':[], # list of tuples (req_name, valid)
            'approvals':[],
            'update_details':[] }
            
        # update self according to json_input
        self.__update(json_input)
        self.__validate()
        
        # detect approval steps
        if self.get_attribute('root'):
            self.__approval_steps = ['new',  'contact_approved',  'gen_approved',  'flow', 'inject', 'approve']
        else:
            self.__approval_steps = ['new', 'flow', 'inject', 'approve']

    def __validate(self):
        if not self._json_base__json:
            return 
        for key in self._json_base__schema:
            if key not in self._json_base__json:
                raise self.IllegalAttributeName(key)
    
    # for all parameters in json_input store their values 
    # in self._json_base__json
    def __update(self,  json_input):
        self._json_base__json = {}
        if not json_input:
            self._json_base__json = self._json_base__schema
        else:
            for key in self._json_base__schema:
                if key in json_input:
                    self._json_base__json[key] = json_input[key]
                else:
                    self._json_base__json[key] = self._json_base__schema[key]
            if '_rev' in json_input:
                self._json_base__json['_rev'] = json_input['_rev']
                    
    def add_comment(author_name, comment, author_cmsid=-1, author_inst_code='', author_project=''):
        comments = self.get_attribute('comments')
        new_comment = comment(author_name,  author_cmsid,  author_inst_code,  author_project).build(comment)
        comments.append(new_comment)
        self.set_attribute('comments',  comments)
    
    def add_sequence(self,  customize_name='', customize_function='', sequenc='',  kcustomize_name='',  kcustomize_function='',  ksequence=''):
        seq = sequence()
        seq.build(customize_name,  customize_function,  sequenc,  kcustomize_name,  kcustomize_function,  ksequence)
        sequences = self.get_attribute('sequences')
        index = len(sequences) + 1
        seq.set_attribute('index', index)
        sequences.append(seq.json())
        self.set_attribute('sequences', sequences)
    
    def approve(self,  index=-1):
        approvals = self.get_attribute('approvals')
        app = approval('')
        app.set_approval_steps(self.__approval_steps)
        
        # if no index is specified, just go one step further
        if index==-1:
            index = len(approvals)
        
        try:
            new_apps = app.approve(index)
            self.set_attribute('approvals',  new_apps)
            return True
        except app.IllegalApprovalStep as ex:
            print str(ex)
            return False
    
    def approve1(self,  author_name,  author_cmsid=-1, author_inst_code='', author_project=''):
        approvals = self.get_attribute('approvals')
        app = approval('')
        index = -1
        step = app.get_approval(0)
        
        # find if approve is legal (and next step)
        if len(approvals) == 0:
            index = -1
        elif len(approvals) == len(app.get_approval_steps()):
            raise app.IllegalApprovalStep()
        else:
            step = approvals[-1]['approval_step']
            index = app.index(step) + 1
            step = app.get_approval(index)

    # build approval 
        try:
            new_approval = approval(author_name, author_cmsid, author_inst_code, author_project).build(step)
        except approval('').IllegalApprovalStep(step) as ex:
            print str(ex)
            return
        
        # make persistent
        approvals.append(new_approval)
        self.set_attribute('approvals',  approvals)
    
    def update_generator_parameters(self, generator_parameters={}):
        if not generator_parameters:
            return
        gens = self.get_attribute('generator_parameters')
        generator_parameters['version']=len(gens)+1
        self.set_attribute('generator_parameters',  gens.append(generator_parameters))
