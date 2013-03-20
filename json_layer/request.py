#!/usr/bin/env python

import copy

from couchdb_layer.prep_database import database

from json import loads,dumps
from json_layer.json_base import json_base
from json_layer.generator_parameters import generator_parameters
from json_layer.sequence import sequence
#from json_layer.action import action

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
                    self._json_base__approvalsteps = ['none','approve', 'submit']
                    self._json_base__status = ['new','approved','submitted','done']
            else:
                raise Exception('Campaign %s does not exist in the database' % (json_input['member_of_campaign']))

        self._json_base__schema = {
            '_id':'', 
            'prepid':'',
            'history':[],  
            'priority':0,
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

      fragment=self.get_attribute('nameorfragment').decode('utf-8')
      ##JR
      if fragment=='':
          fragment='step%d'%(sequenceindex+1)
      command = 'cmsDriver.py %s' % (fragment)

      try:
          seq = sequence(self.get_attribute('sequences')[sequenceindex])
      except Exception:
          self.logger.error('Request %s has less sequences than expected. Missing step: %d' % (self.get_attribute('prepid'), sequenceindex), level='critical')
          return '' 
      
      cmsDriverOptions=seq.build_cmsDriver()
      
      if not cmsDriverOptions.strip():
          return '%s %s' % (command, cmsDriverOptions)

      ##JR
      if self.get_attribute('input_filename'):
          if sequenceindex==0:
              command +=' --filein "dbs:%s" '%(self.get_attribute('input_filename'))
              command +=' --fileout file:step%d.root '%(sequenceindex+1)
          else:
              command+=' --filein file:step%d.root '%(sequenceindex)
              command +=' --fileout file:step%d.root '%(sequenceindex+1)

      elif self.get_attribute('mcdb_id')>0:
          command +=' --filein lhe:%d '%(self.get_attribute('mcdb_id'))

      ##JR
      if self.get_attribute('pileup_dataset_name') and not (seq.get_attribute('pileup') in ['','NoPileUp']):
          command +=' --pileup_input "dbs:%s"'%(self.get_attribute('pileup_dataset_name'))

      return '%s %s' % (command, cmsDriverOptions)

    def build_cmsDrivers(self,cast=0):
      commands = []
      if cast==1:
          cdb = database('campaigns')

          inchains = self.get_attribute('member_of_chain')
          flownWith=None
          if len(inchains) > 1:
              #no flow can be determined
              flownWith=None
          elif len(inchains)==0:
              ## not member of any chain, that's should happen only before one defines
              flownWith=None
          else:
              crdb = database('chained_requests')
              ccdb = database('chained_campaigns')
              fdb = database('flows')
              cr = crdb.get(inchains[0])
              cc = ccdb.get(cr['member_of_campaign'])
              indexInChain = cr['chain'].index(self.get_attribute('prepid'))
              flownWith = fdb.get(cc['campaigns'][indexInChain][1])

          camp = cdb.get(self.get_attribute('member_of_campaign'))
          self.set_attribute('cmssw_release',camp['cmssw_release'])
          self.set_attribute('pileup_dataset_name',camp['pileup_dataset_name'])
          self.set_attribute('type',camp['type'])
          ## putting things together from the campaign+flow
          freshSeq=[]
          
          ##JR
          ## there is a method in the chained_requests that needs to be put in common, as a static method for example: although, this could create circulare dependencies....
          new_req = self.json()
          new_req['sequences']=[]
          def puttogether(nc,fl,new_req):
            # copy the sequences of the flow
            for i, step in enumerate(nc['sequences']):
		flag = False # states that a sequence has been found
		for name in step:
                        if name in fl['request_parameters']['sequences'][i]:
				# if a seq name is defined, store that in the request
				new_req['sequences'].append(step[name])
				
				# if the flow contains any parameters for the sequence,
				# then override the default ones inherited from the campaign
				if fl['request_parameters']['sequences'][i][name]:
					for key in fl['request_parameters']['sequences'][i][name]:
						new_req['sequences'][-1][key] = fl['request_parameters']['sequences'][i][name][key]
				# to avoid multiple sequence selection
				# continue to the next step (if a valid seq is found)
				flag = True
				break

		# if no sequence has been found, use the default
		if not flag:
			new_req['sequences'].append(step['default'])
	
	    # override request's parameters
            for key in fl['request_parameters']:
                if key == 'sequences':
                    continue
		else:
			if key in new_req:
				new_req[key] = fl['request_parameters'][key]
          if flownWith:
              puttogether(camp,flownWith,new_req)
          else:
              for i in range(len(camp['sequences'])):
                      fresh = sequence(camp['sequences'][i]["default"])
                      freshSeq.append(fresh.json())
              self.set_attribute('sequences',freshSeq)
          rdb = database('requests')
          #rdb.update(self.json())
          rdb.update(new_req)
      elif  cast==-1:
          ## a way of resetting the sequence and necessary parameters
          self.set_attribute('cmssw_release','')
          self.set_attribute('pileup_dataset_name','')
          freshSeq=[]
          for i in range(len(self.get_attribute('sequences'))):
              freshSeq.append(sequence().json())
          self.set_attribute('sequences',freshSeq)
          ##then itself in DB
          rdb = database('requests')
          rdb.update(self.json())
          
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

## could not put that method here from RequestActions.py, because of cyclic dependence request <-> action
## maybe we could do something later on 
#    def add_action(self):
#        # Check to see if the request is a root request
#        camp = self.get_attribute('member_of_campaign')
#        
#        cdb = database('campaigns')
#        if not cdb.document_exists(camp):
#            return dumps({"results":'Error: Campaign '+str(camp)+' does not exist.'})
#                
#        # get campaign
#        c = cdb.get(camp)
#        
#        adb = database('actions')
#        if (c['root'] > 0) or (c['root'] <=0 and int(self.get_attribute('mcdb_id')) > -1):
#            ## c['root'] > 0 
#            ##            :: not a possible root --> no action in the table
#            ## c['root'] <=0 and self.request.get_attribute('mcdb_id') > -1 
#            ##            ::a possible root and mcdbid=0 (import from WMLHE) or mcdbid>0 (imported from PLHE) --> no action on the table
#            if adb.document_exists(self.get_attribute('prepid')):
#                ## check that there was no already inserted actions, and remove it in that case
#                adb.delete(self.get_attribute('prepid'))
#            return True
#        
#        # check to see if the action already exists
#        if not adb.document_exists(self.get_attribute('prepid')):
#            # add a new action
#            a= action('automatic')
#            a.set_attribute('prepid',  self.get_attribute('prepid'))
#            a.set_attribute('_id',  a.get_attribute('prepid'))
#            a.set_attribute('member_of_campaign',  self.get_attribute('member_of_campaign'))
#            a.find_chains()
#            adb.save(a.json())
#        return True
