#!/usr/bin/env python

import copy

from couchdb_layer.prep_database import database

from json_layer.json_base import json_base
from json_layer.generator_parameters import generator_parameters
from json_layer.sequence import sequence

class request(json_base):
    class DuplicateApprovalStep(Exception):
        def __init__(self,  approval=None):
            self.__approval = repr(approval)
            request.logger.error('Duplicate Approval Step: Request has already been %s approved' % (self.__approval))
        def __str__(self):
            return 'Duplicate Approval Step: Request has already been \'' + self.__approval + '\' approved'

    def __init__(self, json_input={}):

        # detect approval steps
        root = False
        cdb = database('campaigns')
        
        if 'member_of_campaign' in json_input and json_input['member_of_campaign']:
            if cdb.document_exists(json_input['member_of_campaign']):
                if cdb.get(json_input['member_of_campaign'])['root'] > 0:
                    self._json_base__approvalsteps = ['approve', 'submit']
            else:
                raise Exception('Campaign %s does not exist in the database' % (json_input['member_of_campaign']))

        self._json_base__schema = {
            '_id':'', 
            'prepid':'',
            'history':[],  
            'priority':'',
            'completion_date':'', 
            'cmssw_release':'',
            'input_filename':'',
            'pwg':'',
            'validation':'',
            'dataset_name':'',
            'pileup_dataset_name':'',
            'www':'',
            'process_string':'',
            'input_block':'',
            'block_black_list':[], 
            'block_white_list':[], 
            'cvs_tag':'',
            'pvt_flag':'',
            'pvt_comment':'',
            'mcdb_id':-1,
            'notes':'',
            'description':'',
            'remarks':'',
            'completed_events':-1,
            'total_events':-1,
            'member_of_chain':[],
            'member_of_campaign':'',
            'time_event':-1,
            'size_event':-1,
            'nameorfragment':'', 
            'version':0,
            'status':self.get_status_steps()[0],
            'type':'',
            'generators':'',
            'sequences':[],
            'generator_parameters':[], 
            'reqmgr_name':[], # list of tuples (req_name, valid)
            'approval':self.get_approval_steps()[0]
            }
            
        # update self according to json_input
        self.update(json_input)
        self.validate()
        
    def add_sequence(self,
              steps=[],
              nameorfragment='',
              conditions='',
              eventcontent=[],
              datatier=[],
              beamspot='',
              customise=[],
              filtername='',
              geometry='',
              magField='',
              pileup='NoPileUp',
              datamix='NODATAMIXER',
              scenario='',
              processName='',
              harvesting='',
              particle_table='',
              inputCommands='',
              dropDescendant=False,
              donotDropOnInput=True,
              restoreRNDSeeds='',
              slhc=''):
        seq = sequence()
        seq.build(steps, nameorfragment, conditions, eventcontent, datatier, beamspot, customise, filtername, geometry, magField, pileup, datamix, scenario, processName, harvesting, particle_table, inputCommands, dropDescendant, donotDropOnInput, restoreRNDSeeds, slhc)
        sequences = self.get_attribute('sequences')
        index = len(sequences) + 1
        seq.set_attribute('index', index)
        sequences.append(seq.json())
        self.set_attribute('sequences', sequences)
   
    def build_cmsDriver(self, sequenceindex):
      command = 'cmsDriver.py %s' % (self.get_attribute('nameorfragment').decode('utf-8'))
      try:
          seq = sequence(self.get_attribute('sequences')[sequenceindex])
      except Exception:
          self.logger.error('Request %s has less sequences than expected. Missing step: %d' % (self.get_attribute('prepid'), sequenceindex), level='critical')
          return '' 
      
      return '%s %s' % (command, seq.build_cmsDriver())

    def build_cmsDrivers(self):
      commands = []
      for i in range(len(self.get_attribute('sequences'))):
        cd = self.build_cmsDriver(i)
        if cd:
            commands.append(cd)
      return commands  

    
    def update_generator_parameters(self, generator_parameters={}):
        if not generator_parameters:
            return
        gens = self.get_attribute('generator_parameters')
        generator_parameters['version']=len(gens)+1
        self.set_attribute('generator_parameters',  gens.append(generator_parameters))
