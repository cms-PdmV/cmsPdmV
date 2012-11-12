#!/usr/bin/env python

from json_base import json_base
from submission_details import submission_details

class approval(json_base):
    class IllegalApprovalStep(Exception):
        def __init__(self,  step=None):
            self.__step = repr(step)
        def __str__(self):
            return 'Illegal Approval Step: ' + self.__step

    def __init__(self, author_name,  author_cmsid=-1 ,  author_inst_code='',  author_project='',json_input={}):
        
        self._json_base__approvalsteps = ['new',  'flow',  'inject',  'approve']
        
        self._json_base__schema = {
            'index':-1,
            'approval_step':'',
            'approver':submission_details().build(author_name,  author_cmsid,  author_inst_code,  author_project) 
        }

        # update self according to json_input
        self.__update(json_input)
        self.__validate()

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
    
    def __clone(self):
        new={}
        for att in self._json_base__schema:
           new[att] = self._json_base__schema[att]
        return new
    
    def  build(self, approval_step):
        if approval_step not in self._json_base__approvalsteps:
            raise self.IllegalApprovalStep(approval_step)
        
        new = self.__clone()
        
        new['approval_step'] = approval_step
        new['index'] = self._json_base__approvalsteps.index(approval_step)
        return new
    
    def approve(self,  index):
        if index >= len(self._json_base__approvalsteps):
            raise self.IllegalApprovalStep(index)
        
        approvals = []
        
        for i in range(index+1):
            approvals.append(self.build(self._json_base__approvalsteps[i]))
        
        return approvals
    
    def get_approval(self,  index):
        if index < 0 or index > len(self._json_base__approvalsteps):
            raise self.IllegalApprovalStep(index)
        return self._json_base__approvalsteps[index]
    
    def index(self,  approval):
        if approval not in self._json_base__approvalsteps:
            raise self.IllegalApprovalStep(approval)
        return self._json_base__approvalsteps.index(approval)
    
    def get_approval_steps(self):
        return self._json_base__approvalsteps
    
    def set_approval_steps(self,  approvals):
        if approvals:
            self._json_base__approvalsteps = approvals
            
if __name__=='__main__':
    a = approval(' ')
    a.print_self()
