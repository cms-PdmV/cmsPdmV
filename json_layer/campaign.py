#!/usr/bin/env python

#from couchdb_layer.prep_database import database
from json_base import json_base
from submission_details import submission_details
from approval import approval
from comment import comment
from sequence import sequence

class campaign(json_base):
    class DuplicateApprovalStep(Exception):
        def __init__(self,  approval=None):
            self.__approval = repr(approval)
        def __str__(self):
            return 'Duplicate Approval Step: Request has already been \'' + self.__approval + '\' approved'
    
    class CampaignExistsException(Exception):
        def __init__(self,  cid):
            self.c = cid
        def __str__(self):
            return 'Error: Campaign '+  self.c +  ' already in "next" list.'

    def __init__(self, author_name,  author_cmsid=-1,   author_inst_code='',  author_project='', json_input={}):
        self._json_base__schema = {
                                 '_id':'', 
                                 'prepid':'', 
                                 'start_date':'', 
                                 'end_date':'', 
                                 'energy':-1.0, 
                                 'type':'', 
                                 'next':[], 
                                 'production_type':'', 
                                 'cmssw_release':'', 
                                 'description':'', 
                                 'remarks':'', 
                                 'status':'', 
                                 'validation':'',
                                 'pileup_dataset_name':[], 
                                 'process_string':[], 
                                 'generators':[], 
                                 'www':'', 
                                 'completed_events':-1, 
                                 'total_events':-1, 
                                 'root':-1, # -1: possible root, 0: root, 1: non-root 
                                 'sequences':[], 
                                 'submission_details':submission_details().build(author_name,  author_cmsid,  author_inst_code,  author_project), 
                                 'approvals':[], 
                                 'comments':[]
                                 }
        # update self according to json_input
        self.__update(json_input)
        self.__validate()
        
        # set campaign approval steps
        self._json_base__approvalsteps = ['start',  'stop']

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

    def add_sequence(self, seq_json={},  step=-1):
        seq = sequence(json_input=seq_json)
        sequences = self.get_attribute('sequences')
        
        if step == -1:
            index = len(sequences) + 1
        elif step <= len(sequences):
            index = step
        else:
            return
            
        sequences[index].append(seq.json())
        self.set_attribute('sequences', sequences)
    
    def add_comment(author_name, comment, author_cmsid=-1, author_inst_code='', author_project=''):
        comments = self.get_attribute('comments')
        new_comment = comment(author_name,  author_cmsid,  author_inst_code,  author_project).build(comment)
        comments.append(new_comment)
        self.set_attribute('comments',  comments)
    
    def add_request(self,  req_json={}):
        try:
            from request import request
            req = request('', request_json=req_json)
        except ImportError as ex:
            print 'Error while trying to import \'request\' module.'
            print 'Returned: ' + str(ex)
            return {}
        except self.IllegalAttributeName() as ex:
            return {}
        
        for key in self._json_base__json:
            if key not in req.schema():
                continue
            if 'prepid' == key or '_id' == key or '_date' in key or 'description' == key or 'remarks' == key or 'validation' == key or '_events' in key or 'approvals' == key or 'comments' == key or 'submission_details' == key:
                continue
            req.set_attribute(key, self.get_attribute(key))
        req.set_attribute('member_of_campaign', self.get_attribute('_id'))
        return req.json()
    
    def toggle_approval(self):
        apps = self.get_attribute('approvals')
        a = approval('')
        a.set_approval_steps(self._json_base__approvalsteps)
        
        if not apps:
            self.set_attribute('approvals',  [a.build('start')])
            return
        
        if len(apps) == 1:
            apps.append(a.build('stop'))
            self.set_attribute('approvals',  apps)
            return
        else:
            self.set_attribute('approvals',  [apps[0]])

    def approve(self,  index=-1):
        approvals = self.get_attribute('approvals')
        app = approval('')
        app.set_approval_steps(self._json_base__approvalsteps)

        # if no index is specified, just go one step further
        if index==-1:
            index = len(approvals)
        
        try:
            new_apps = app.approve(index)
            self.set_attribute('approvals',  new_apps)
            return True
        except app.IllegalApprovalStep as ex:
            print 'Error: ', str(ex)
            return False
    
    def add_next(self,  cid):
        if cid not in self.get_attribute('next'):
            new_next = self.get_attribute('next')
            new_next.append(cid)
            self.set_attribute('next',  new_next)
        else:
            raise self.CampaignExistsException(cid)
        
if __name__=='__main__':
    cp = campaign(' ')
    cp.print_self()
