#!/usr/bin/env python

#from couchdb_layer.prep_database import database
from json_base import json_base
from sequence import sequence
import re

class campaign(json_base):
    class DuplicateApprovalStep(Exception):
        def __init__(self,  approval=None):
            self.__approval = repr(approval)
            campaign.logger.error('Duplicate Approval Step: Request has already been \'' + self.__approval + '\' approved')

        def __str__(self):
            return 'Duplicate Approval Step: Request has already been \'' + self.__approval + '\' approved'
    
    class CampaignExistsException(Exception):
        def __init__(self,  cid):
            self.c = cid
            campaign.logger.error('Error: Campaign '+  self.c +  ' already in "next" list.')

        def __str__(self):
            return 'Error: Campaign '+  self.c +  ' already in "next" list.'

    def __init__(self, json_input={}):

        # set campaign approval steps
        self._json_base__approvalsteps = ['stop',  'start']
        
        # set campaign status
        self._json_base__status = ['stopped','started']

        self._json_base__schema = {
                                 '_id': '',
                                 'prepid': '',
                                 #'start_date':'', 
                                 #'end_date':'', 
                                 'energy': -1.0,
                                 'type': '',
                                 'next': [],
                                 #'production_type':'', 
                                 'cmssw_release': '',
                                 'input_dataset': '',
                                 #'description':'', 
                                 'notes' : '',
                                 #'remarks':'', 
                                 #'notes':'',
                                 'status':self.get_status_steps()[0], 
                                 'validation':'',
                                 'pileup_dataset_name':'', 
                                 #'process_string':[], 
                                 'generators': [],
                                 'www': '',
                                 #'completed_events': -1,
                                 #'total_events': -1,
                                 'root': 1, # -1: possible root, 0: root, 1: non-root
                                 'sequences': [], # list of jsons of jsons
                                 'approval': self.get_approval_steps()[0],
                                 'history': []
                                 }

        # update self according to json_input
        self.update(json_input)
        self.validate()
        
    def add_sequence(self, seq_json={},  step=-1, name='default'):
        seq = sequence(json_input=seq_json)
        sequences = self.get_attribute('sequences')
        
        if step == -1:
            index = len(sequences) + 1
        elif step <= len(sequences):
            index = step
        else:
            return
            
        sequences[index].update({name : seq.json()})
        self.set_attribute('sequences', sequences)

    def build_cmsDrivers(self):
        cds = []
        for (stepindex,step) in enumerate(self.get_attribute('sequences')):
             stepcd = {}
             for key in step:
                 cdarg = sequence(step[key]).build_cmsDriver()
                 fragment='NameOfFragment'
                 if self.get_attribute('root')==1:
                     fragment='step%d'%(stepindex+1)
                 cd='cmsDriver.py %s %s'%(fragment, cdarg)
                 if cd:
                     stepcd[key] = cd
             cds.append(stepcd)
        return cds
    
    def add_request(self,  req_json={}):
        try:
            from request import request
            req = request(json_input=req_json)
        except ImportError as ex:
            self.logger.error('Could not import \'request\' module. Reason: %s' %(ex))
            return {}
        except self.IllegalAttributeName() as ex:
            return {}

        req.transfer_from(self)
        return req.json()

    def toggle_approval(self):
        appsteps = self.get_approval_steps()
        app = self.get_attribute('approval')

        if appsteps.index(app) == 1:
            self.approve(0)
        elif appsteps.index(app) == 0:
            self.approve(1)
        else:
            raise NotImplementedError('Could not toggle approval for object %s' % (self.get_attribute('_id')))

    def toggle_status(self):
       ststeps = self.get_status_steps()
       st = self.get_attribute('status')

       if ststeps.index(st) == 1:
            self.set_status(0)
       elif ststeps.index(st) == 0:
           ## make a few checks here
           if self.get_attribute('energy')<0:
               raise Exception('Cannot start a campaign with negative energy')
           if not self.get_attribute('cmssw_release'):
               raise Exception('Cannot start a campaign with no release')
           if not self.get_attribute('type'):
               raise Exception('Cannot start a campaign with no type')
           
           self.set_status(1)
       else:
           raise NotImplementedError('Could not toggle status for object %s' % (self.get_attribute('_id')))

    def add_next(self,  cid):
        if cid not in self.get_attribute('next'):
            new_next = self.get_attribute('next')
            new_next.append(cid)
            new_next.sort()
            self.set_attribute('next',  new_next)
        else:
            raise self.CampaignExistsException(cid)

    def is_release_greater_or_equal_to(self, cmssw_release):
        my_release = filter(None, re.sub("[^0-9_]", "", self.get_attribute('cmssw_release')).split('_'))
        other_release = filter(None, re.sub("[^0-9_]", "", cmssw_release).split('_'))
        try:
            for i in range(len(my_release)):
                if int(my_release[i]) < int(other_release[i]):
                    return False
        except IndexError:
            return True
        return True

