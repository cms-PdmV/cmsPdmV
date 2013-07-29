#!/usr/bin/env python

import copy
import os 
import re
import pprint
import time 
import xml.dom.minidom
from math import sqrt
import hashlib
import traceback

from couchdb_layer.prep_database import database

from json import loads,dumps
from json_layer.json_base import json_base
from json_layer.generator_parameters import generator_parameters
from json_layer.sequence import sequence
from tools.locator import locator
from tools.batch_control import batch_control
from tools.installer import installer
from tools.handler import handler

class request(json_base):
    class DuplicateApprovalStep(Exception):
        def __init__(self,  approval=None):
            self.__approval = repr(approval)
            request.logger.error('Duplicate Approval Step: Request has already been %s approved' % (self.__approval))
        def __str__(self):
            return 'Duplicate Approval Step: Request has already been \'' + self.__approval + '\' approved'

    def __init__(self, json_input={}):

        # detect approval steps
        self.is_root = False
        cdb = database('campaigns')
        if 'member_of_campaign' in json_input and json_input['member_of_campaign']:
            if cdb.document_exists(json_input['member_of_campaign']):
                if cdb.get(json_input['member_of_campaign'])['root'] > 0:
                    self._json_base__approvalsteps = ['none','approve', 'submit']
                    self._json_base__status = ['new','approved','submitted','done']
                else:
                    self.is_root = True
            else:
                raise Exception('Campaign %s does not exist in the database' % (json_input['member_of_campaign']))

        self._json_base__schema = {
            '_id':'', 
            'prepid':'',
            'history':[],  
            'priority':0,
            #'completion_date':'', 
            'cmssw_release':'',
            'input_filename':'',
            'pwg':'',
            'validation':{},
            'dataset_name':'',
            'pileup_dataset_name':'',
            #'www':'',
            'process_string':'',
            'extension': 0,
            #'input_block':'',
            'block_black_list':[], 
            'block_white_list':[], 
            'cvs_tag':'',
            'fragment_tag':'',
            #'pvt_flag':'',
            #'pvt_comment':'',
            'mcdb_id':-1,
            'notes':'',
            #'description':'',
            #'remarks':'',
            'notes':'',
            'completed_events':-1,
            'total_events':-1,
            'member_of_chain':[],
            'member_of_campaign':'',
            'flown_with':'',
            'time_event':-1,
            'size_event':-1,
            #'nameorfragment':'', 
            'name_of_fragment':'',
            'fragment':'',
            'config_id':[],
            'version':0,
            'status':self.get_status_steps()[0],
            'type':'',
            'keep_output':[], ## list of booleans
            'generators':[],
            'sequences':[],
            'generator_parameters':[], 
            'reqmgr_name':[], # list of tuples (req_name, valid)
            'approval':self.get_approval_steps()[0],
            'analysis_id':[],
            'energy' : 0,
            }
        # update self according to json_input
        self.setup()
        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()

##JR: not used and not necessary
    #def add_sequence(self,
    #          steps=[],
    #          nameorfragment='',
    #          conditions='',
    #          eventcontent=[],
    #          datatier=[],
    #          beamspot='',
    #          customise=[],
    #          filtername='',
    #          geometry='',
    #          magField='',
    #          pileup='NoPileUp',
    #          datamix='NODATAMIXER',
    #          scenario='',
    #          processName='',
    #          harvesting='',
    #          particle_table='',
    #          inputCommands='',
    #          dropDescendant=False,
    #          donotDropOnInput=True,
    #          restoreRNDSeeds='',
    #          slhc=''):
    #    seq = sequence()
    #    seq.build(steps, nameorfragment, conditions, eventcontent, datatier, beamspot, customise, filtername, geometry, magField, pileup, datamix, scenario, processName, harvesting, particle_table, inputCommands, dropDescendant, donotDropOnInput, restoreRNDSeeds, slhc)
    #    sequences = self.get_attribute('sequences')
    #    index = len(sequences) + 1
    #    seq.set_attribute('index', index)
    #    sequences.append(seq.json())
    #    self.set_attribute('sequences', sequences)


    def set_status(self, step=-1,with_notification=False,to_status=None):
        ## call the base
        json_base.set_status(self,step,with_notification)
        ## and set the last_status of each chained_request I am member of, last
        crdb= database('chained_requests')
        for inchain in self.get_attribute('member_of_chain'):
            if crdb.document_exists(inchain):
                from json_layer.chained_request import chained_request
                chain=chained_request(crdb.get(inchain))
                a_change=False
                a_change += chain.set_last_status( self.get_attribute('status') )
                a_change += chain.set_processing_status( self.get_attribute('prepid'), self.get_attribute('status') )
                if a_change:
                    crdb.save(chain.json())
        
    def get_editable(self):
        editable= {}
        if self.get_attribute('status')!='new': ## after being new, very limited can be done on it
            for key in self._json_base__schema:
                editable[key]=False
            if self.current_user_level!=0: ## not a simple user
                for key in ['generator_parameters','notes','history','generators']:
                    editable[key]=True
            if self.current_user_level>3: ## only for admins
                for key in ['completed_events','reqmgr_name','member_of_chain','config_id','validation']:
                    editable[key]=True
        else:
            for key in self._json_base__schema:
                editable[key]=True

        return editable

    def ok_to_move_to_approval_validation(self):
        if self.current_user_level==0:
            ##not allowed to do so
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','bad user admin level %s'%(self.current_user_level))

        if self.get_attribute('status')!='new':
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation')

        if self.get_attribute('cmssw_release')==None or self.get_attribute('cmssw_release')=='None':
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The release version is undefined')

        if not self.get_attribute('dataset_name') or ' ' in self.get_attribute('dataset_name'):
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The dataset name is invalid: either null string or containing blanks')

        gen_p = self.get_attribute('generator_parameters')
        if not len(gen_p) or generator_parameters(gen_p[-1]).isInValid():
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The generator parameters is invalid: either none or negative or null values, or efficiency larger than 1')

        if not len(self.get_attribute('generators')):
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','There should be at least one generator mentioned in the request')

        if self.get_attribute('time_event') <=0 or self.get_attribute('size_event')<=0:
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The time per event or size per event are invalid: negative or null')

        if not self.get_attribute('fragment') and (not ( self.get_attribute('name_of_fragment') and self.get_attribute('fragment_tag'))):
            if self.get_attribute('mcdb_id')>0 and not self.get_attribute('input_filename'):
                ##this case is OK
                pass
            else:
                raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The configuration fragment is not available. Neither fragment or name_of_fragment are available')

        if self.get_attribute('name_of_fragment') and self.get_attribute('fragment_tag'):
            for line in self.parse_fragment():
                if 'This is not the web page you are looking for' in line:
                    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The configuration fragment does not exist in git')
                if 'Exception Has Occurred' in line:
                    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The configuration fragment does not exist in cvs')

        if self.get_attribute('total_events') < 0:
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The number of requested event is invalid: Negative')

        if self.get_attribute('mcdb_id') <= 0 and self.get_wmagent_type()=='LHEStepZero':
            nevents_per_job = self.numberOfEventsPerJob()
            if not nevents_per_job:
                raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The number of events per job cannot be retrieved for lhe production')
            elif nevents_per_job == self.get_attribute('total_events'):
                raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The number of events per job is equal to the number of events requested')
            

        rdb=database('requests')
        ## same thing but using db query => faster
        find_similar = ['dataset_name==%s'%(self.get_attribute('dataset_name')),
                        'member_of_campaign==%s'%( self.get_attribute('member_of_campaign'))]
        if self.get_attribute('process_string'):
            find_similar.append( 'process_string==%s'%( self.get_attribute('process_string')) )
        similar_ds  = rdb.queries(find_similar)

        if len(similar_ds)>1:
            #if len(similar_ds)>2:
            #    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','Three or more requests with the same dataset name, same process string in the same campaign')
            #if similar_ds[0]['extension'] == similar_ds[1]['extension']:
            #    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','Two requests with the same dataset name, same process string and they are not extension of each other')
            my_extension = self.get_attribute('extension')
            my_id = self.get_attribute('prepid')
            for similar in similar_ds:
                if similar['prepid'] == my_id: continue
                if int(similar['extension']) == int(my_extension):
                    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','Two requests with the same dataset name, same process string and they are the same extension mumber (%s)'( my_extension))
        
        cdb = database('campaigns')
        ##this below needs fixing
        if not len(self.get_attribute('member_of_chain')):
            #not part of any chains ...
            if self.get_attribute('mcdb_id')>0 and not self.get_attribute('input_filename'):
                if cdb.get(self.get_attribute('member_of_campaign'))['root'] in [-1,1]:
                    ##only requests belonging to a root==0 campaign can have mcdbid
                    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The request has an mcdbid, not input dataset, and not member of a root campaign')

        else:
            crdb = database('chained_requests')
            for cr in self.get_attribute('member_of_chain'):
                mcm_cr = crdb.get(cr)
                if mcm_cr['chain'].index( self.get_attribute('prepid') ) ==0:
                    if self.get_attribute('mcdb_id')>0 and not self.get_attribute('input_filename'):
                        raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The request has an mcdbid, not input dataset, and is considered to be a request at the root of its chains.')


        ## check on chagnes in the sequences
        mcm_c = cdb.get( self.get_attribute('member_of_campaign') )
        if len(self.get_attribute('sequences')) != len(mcm_c['sequences']):
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The request has a different number of steps than the campaigns it belog to')


        def in_there( seq1, seq2):
            for (name,item) in seq1.items():
                if name in seq2:
                    if item!=seq2[name]:
                        return False
                else:
                    if item=='':
                        #do not care about parameters that are absent, with no actual value
                        return True
                    return False
            ## arived here, all items of seq1 are identical in seq2
            return True
        matching_labels=set([])
        for (i_seq,seqs) in enumerate(mcm_c['sequences']):
            self_sequence = self.get_attribute('sequences')[i_seq]
            this_matching=set([])
            for (label,seq) in seqs.items():
                # label = default , seq = dict
                if in_there( seq, self_sequence ) and in_there( self_sequence, seq ):
                    ## identical sequences
                    self.logger.log('identical sequences %s'% label)
                    this_matching.add(label)
                else:
                    self.logger.log('different sequences %s \n %s \n %s'%(label, seq, self_sequence))
            if len(matching_labels)==0:
                matching_labels=this_matching
                self.logger.log('Matching labels %s'% matching_labels)
            else:
                # do the intersect
                matching_labels = matching_labels - (matching_labels - this_matching) 
                self.logger.log('Matching labels after changes %s'% matching_labels)
                

        if len(matching_labels)==0:
            self.logger.log('The sequences of the request is not the same as any the ones of the campaign')
            # try setting the process string ? or just raise an exception ?
            if not self.get_attribute('process_string'):
                raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The sequences of the request has been changed with respect to the campaign, but no processing string has been provided')
                    
                    

        ## select to synchronize status and approval toggling, or run the validation/run test
        de_synchronized=True
        if de_synchronized:
            threaded_test = runtest_genvalid( rid=str(self.get_attribute('prepid')))
            ## this will set the status on completion, or reset the request.
            threaded_test.start()
        else:
            self.set_status()

    def ok_to_move_to_approval_define(self):
        if self.current_user_level==0:
            ##not allowed to do so 
            raise self.WrongApprovalSequence(self.get_attribute('status'),'define','bad user admin level %s'%(self.current_user_level))
        ## we could restrict certain step to certain role level
        #if self.current_user_role != 'generator_contact':
        #    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','bad user role %s'%(self.current_user_role))

        if self.get_attribute('status')!='validation':
            raise self.WrongApprovalSequence(self.get_attribute('status'),'define')

        ## a state machine should come along and create the configuration. check the filter efficiency, and set information back
        # then toggle the status
        self.set_status()

    def ok_to_move_to_approval_approve(self):
        if self.current_user_level<=1:
            ##not allowed to do so 
            raise self.WrongApprovalSequence(self.get_attribute('status'),'approve','bad user admin level %s'%(self.current_user_level))

        if 'defined' in self._json_base__status:
            if self.get_attribute('status')!='defined':
                raise self.WrongApprovalSequence(self.get_attribute('status'),'approve')
        else:
            if self.get_attribute('status')!='new':
                raise self.WrongApprovalSequence(self.get_attribute('status'),'approve')
        
        # maybe too early in the chain of approvals
        #if not len(self.get_attribute('member_of_chain')):
        #    raise self.WrongApprovalSequence(self.get_attribute('status'),'approve','This request is not part of any chain yet')

        ## from defined status, with generator convener approval (?should this be removed???)
        # this one will probably stay hard-wired, unless we decide on something very specific, like resource estimation: a state machine would come along, check, raise alarms, or set to approved
        self.set_status()

    def ok_to_move_to_approval_submit(self):
        if self.current_user_level<3:
            ##not allowed to do so                                                                                                      
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','bad user admin level %s'%(self.current_user_level))

        if self.get_attribute('status')!='approved':
            raise self.WrongApprovalSequence(self.get_attribute('status'),'submit')
        
        if not len(self.get_attribute('member_of_chain')):
            raise self.WrongApprovalSequence(self.get_attribute('status'),'submit','This request is not part of any chain yet')

        at_least_an_action = self.has_at_least_an_action()
        if not at_least_an_action:
            raise self.WrongApprovalSequence(self.get_attribute('status'),'submit','This request does not spawn from any valid action')

        ## the request manager could pull out those requests approved to be submitted
        ## the production manager would go and submit those by hand via McM : the status is set automatically upon proper injection
        # remains to the production manager to announce the batch the requests are part of
        #### not settting any status forward
        
    def has_at_least_an_action(self):
        at_least_an_action=False
        crdb = database('chained_requests')
        adb = database('actions')
        for in_chain_id in self.get_attribute('member_of_chain'):
            if not crdb.document_exists(in_chain_id):
                self.logger.error('for %s there is a chain inconsistency with %s' %( self.get_attribute('prepid'), in_chain_id))
                return False
            in_chain = crdb.get(in_chain_id)
            original_action = adb.get( in_chain['chain'][0] )
            my_action_item = original_action['chains'][in_chain['member_of_campaign']]
            ## old convention
            if 'flag' in my_action_item and my_action_item['flag'] == True:
                at_least_an_action=True
                break
            ## new convention
            if type(my_action_item['chains'])==dict:
                for (cr,content) in my_action_item['chains'].items():
                    if content['flag']== True:
                        at_least_an_action=True
                        break
            
        return at_least_an_action
        

    def retrieve_fragment(self,name=None,get=True):
        if not name:
            name=self.get_attribute('name_of_fragment')
        get_me=''
        tag=self.get_attribute('fragment_tag')
        if not tag:
            tag = self.get_attribute('cvs_tag')
        if tag:
            # remove this to allow back-ward compatibility of fragments/requests placed with PREP
            name=name.replace('Configuration/GenProduction/python/','')
            name=name.replace('Configuration/GenProduction/','')
            # curl from git hub which has all history tags
            get_me='curl -s https://raw.github.com/cms-sw/genproductions/%s/python/%s '%( self.get_attribute('fragment_tag'), name )
            # add the part to make it local
            if get:
                get_me+='--create-dirs -o  Configuration/GenProduction/python/%s '%( name )

        if get:
            get_me+='\n'
        return get_me

    def get_fragment(self):
        ## provides the name of the fragment depending on 
        #fragment=self.get_attribute('name_of_fragment').decode('utf-8')
        fragment=self.get_attribute('name_of_fragment')
        if self.get_attribute('fragment') and not fragment:
            #fragment='Configuration/GenProduction/python/%s_fragment.py'%(self.get_attribute('prepid').replace('-','_'))
            fragment='Configuration/GenProduction/python/%s-fragment.py'%(self.get_attribute('prepid'))
        return fragment

    def build_cmsDriver(self, sequenceindex):

      fragment=self.get_fragment()
          
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

    def build_cmsDrivers(self,cast=0, can_save=True):
      commands = []
      if cast==1 and self.get_attribute('status')=='new':
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
              fdb = database('flows')
              if not self.get_attribute('flown_with'):
                  ##legacy to be removed once all request have a flown with parameter
                  crdb = database('chained_requests')
                  ccdb = database('chained_campaigns')
                  cr = crdb.get(inchains[0])
                  cc = ccdb.get(cr['member_of_campaign'])
                  indexInChain = cr['chain'].index(self.get_attribute('prepid'))
                  flownWith = fdb.get(cc['campaigns'][indexInChain][1])
                  self.set_attribute('flown_with',cc['campaigns'][indexInChain][1])
              flownWith = fdb.get(self.get_attribute('flown_with'))

          camp = cdb.get(self.get_attribute('member_of_campaign'))
          self.set_attribute('cmssw_release',camp['cmssw_release'])
          self.set_attribute('pileup_dataset_name',camp['pileup_dataset_name'])
          self.set_attribute('type',camp['type'])
          ## putting things together from the campaign+flow
          freshSeq=[]
          freshKeep=[]
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
              #self.logger.error('Using a flow: %s and a campaign %s , to recast %s'%(flownWith['prepid'],
              #                                                                       camp['prepid'],
              #                                                                       new_req['prepid']))
              puttogether(camp,flownWith,new_req)
          else:
              for i in range(len(camp['sequences'])):
                      fresh = sequence(camp['sequences'][i]["default"])
                      freshSeq.append(fresh.json())
              self.set_attribute('sequences',freshSeq)
          for i in range(len(camp['sequences'])):
                      freshKeep.append(False)
          freshKeep[-1]=True
          self.set_attribute('keep_output',freshKeep)              
          if can_save:
              rdb = database('requests')
              rdb.update(new_req)
          else:
              ## could re-assign the new_req to itself
              pass

      elif  cast==-1 and self.get_attribute('status')=='new':
          ## a way of resetting the sequence and necessary parameters
          self.set_attribute('cmssw_release','')
          self.set_attribute('pileup_dataset_name','')
          freshSeq=[]
          freshKeep=[]
          for i in range(len(self.get_attribute('sequences'))):
              freshSeq.append(sequence().json())
              freshKeep.append(False)
          freshKeep[-1]=True
          self.set_attribute('sequences',freshSeq)
          self.set_attribute('keep_output',freshKeep)
          ##then update itself in DB
          if can_save:
              rdb = database('requests')
              rdb.update(self.json())
          else:
              ## could re-assign the new_req to itself
              pass

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
        if not len (gens):
            genInfo = generator_parameters()
        else:
            genInfo = generator_parameters(gens[-1])
            genInfo.set_attribute('submission_details', self._json_base__get_submission_details())
            genInfo.set_attribute('version', genInfo.get_attribute('version')+1)

        gens.append(genInfo.json())
        self.set_attribute('generator_parameters',  gens)

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

    def little_release(self):
        release_to_find=self.get_attribute('cmssw_release')
        return release_to_find.replace('CMSSW_','').replace('_','')

    def get_scram_arch(self):
        #economise to call many times.
        if hasattr(self,'scram_arch'):
            return self.scram_arch
        self.scram_arch=None
        release_to_find=self.get_attribute('cmssw_release')
        import xml.dom.minidom
        xml_data = xml.dom.minidom.parseString(os.popen('curl -s --insecure https://cmstags.cern.ch/tc/ReleasesXML/?anytype=1').read())
        
        for arch in xml_data.documentElement.getElementsByTagName("architecture"):
            scram_arch = arch.getAttribute('name')
            for project in arch.getElementsByTagName("project"):
                release = str(project.getAttribute('label'))
                if release == release_to_find:
                    self.scram_arch = scram_arch
        return self.scram_arch

    def make_release(self):
        makeRel =''
        makeRel += 'if [ -r %s ] ; then \n'%(self.get_attribute('cmssw_release'))
        makeRel += ' echo release %s already exists\n'%(self.get_attribute('cmssw_release'))
        makeRel += 'else\n'
        makeRel += 'scram p CMSSW ' + self.get_attribute('cmssw_release') + '\n'
        makeRel += 'fi\n'
        makeRel += 'cd ' + self.get_attribute('cmssw_release') + '/src\n'
        return makeRel

    def get_setup_file(self,directory='',events=None):
        l_type = locator()
        infile = ''
        infile += '#!/bin/bash\n'
        if directory:
            ## go into the request directory itself to setup the release, since we cannot submit more than one at a time ...
            infile += 'cd ' + os.path.abspath(directory + '../') + '\n'

        infile += 'source  /afs/cern.ch/cms/cmsset_default.sh\n'
        infile += 'export SCRAM_ARCH=%s\n'%(self.get_scram_arch())

        ##create a release directory "at the root" if not already existing
        infile += self.make_release()
        if directory:
            ##create a release directory "in the request" directory if not already existing 
            infile += 'cd ' + os.path.abspath(directory) + '\n'
            infile += self.make_release()

        ## setup from the last release directory used
        infile += 'eval `scram runtime -sh`\n'

        ## get the fragment if need be
        infile += self.retrieve_fragment()
        
        ##copy the fragment directly from the DB into a file
        if self.get_attribute('fragment'):
            infile += 'curl -s --insecure %spublic/restapi/requests/get_fragment/%s --create-dirs -o %s \n'%(l_type.baseurl(),self.get_attribute('prepid'),self.get_fragment())

        # previous counter
        previous = 0

        # validate and build cmsDriver commands
        cmsd_list = ''
        
        configuration_names = []
        if events:
            run = True
        else:
            run= False

        for cmsd in self.build_cmsDrivers():

            # check if customization is needed to check it out from cvs
            if '--customise' in cmsd:
                cust = cmsd.split('--customise ')[1].split(' ')[0]
                toks = cust.split('.')
                cname = toks[0]+'.py'
                if len(toks)>1:
                    cfun = toks[1]

                # add customization

                if 'GenProduction' in cname:
                    ## this works for back-ward compatiblity
                    #infile+= self.retrieve_fragment(name=cname.split('/')[-1])
                    infile+= self.retrieve_fragment(name=cname)
                    
            # tweak a bit more finalize cmsDriver command
            res = cmsd
            #res += ' --python_filename '+directory+'config_0_'+str(previous+1)+'_cfg.py '
            configuration_names.append( directory+self.get_attribute('prepid')+"_"+str(previous+1)+'_cfg.py')
            res += ' --python_filename %s --no_exec '%( configuration_names[-1] )
            #JR res += '--fileout step'+str(previous+1)+'.root '
            ## seems that we do not need that anymore
            #if previous > 0:
            #    #JR res += '--filein file:step'+str(previous)+'.root '
            #    res += '--lazy_download '

            if run:
                ## with a back port of number_out that would be much better
                res += '-n '+str(events)+ ' '
                #what if there was already a customise ?
                monitor_location='Utils'
                if self.little_release() < '420':
                    infile+='addpkg Configuration/DataProcessing\n'
                    infile+='cvs co -r 1.3 Configuration/DataProcessing/python/Utils.py \n'

                #if self.little_release() > '420': 
                if '--customise' in cmsd:
                    cust = cmsd.split('--customise ')[1].split()[0]
                    cust+=',Configuration/DataProcessing/%s.addMonitoring'%( monitor_location )
                    res +='--customise %s'%( cust )
                else:
                    res += '--customise Configuration/DataProcessing/%s.addMonitoring'%( monitor_location )
                #else:
                    ## cannot have addMonitoring :-(
                    #pass

                res += ' || exit $? ; \n'
                res += 'cmsRun -e -j %s%s_rt.xml %s || exit $? ; \n'%( directory, self.get_attribute('prepid'), configuration_names[-1] )
                #res += 'curl -k --cookie /afs/cern.ch/user/v/vlimant/private/dev-cookie.txt https://cms-pdmv-dev.cern.ch/mcm/restapi/requests/perf_report/%s/perf -H "Content-Type: application/xml" -X PUT --data "@%s%s_rt.xml" \n' %( self.get_attribute('prepid'),directory, self.get_attribute('prepid'))
            else:
                res += '-n 10 || exit $? ; \n'
            #infile += res
            cmsd_list += res + '\n'

            previous += 1


        (i,c) = self.get_genvalid_setup(directory, run)
        infile+=i
        cmsd_list+=c
        
        infile += '\nscram b\n'
        infile += cmsd_list
        # since it's all in a subshell, there is
        # no need for directory traversal (parent stays unaffected)

        if run and self.genvalid_driver:
            infile += self.harverting_upload

        infile += 'cd ../../\n'
        ## if there was a release setup, jsut remove it
        #not in dev
        if directory and not l_type.isDev():
            infile += 'rm -rf %s' %( self.get_attribute('cmssw_release') )
            

        return infile

    def get_genvalid_setup(self,directory,run):
        cmsd_list =""
        infile =""

        ############################################################################
        #### HERE starts a big chunk that should be moved somewhere else than here
        ## gen valid configs
        self.genvalid_driver = None
        valid_sequence = None
        n_to_valid=1000 #get it differently than that
        yes_to_valid=False
        val_attributes = self.get_attribute('validation')
        if 'nEvents' in val_attributes:
            n_to_valid=val_attributes['nEvents']
            if not n_to_valid:
                yes_to_valid=False
            else:
                yes_to_valid=True
        if 'valid' in val_attributes:
            yes_to_valid=val_attributes['valid']

        """
        val_sentence=self.get_attribute('validation')
        if len(val_sentence):
            val_spec=val_sentence.split(',')
            for spec in val_spec:
                spec_s = spec.split(':')
                k = spec_s[0]
                if k == 'nEvents':
                    n_to_valid = int(spec_s[1])
                    yes_to_valid = True
                if k == 'valid':
                    yes_to_valid = bool( spec_s[1] )
        """

        l_type=locator()
        if self.little_release() < '530':# or (not l_type.isDev()):
            yes_to_valid= False        

        if not yes_to_valid:
            return ("","")

        # to be refined using the information of the campaign
        firstSequence = self.get_attribute('sequences')[0]
        firstStep = firstSequence['step'][0]

        dump_python=''
        if firstStep == 'GEN':

            cmsd_list += '\n\n'
            valid_sequence = sequence( firstSequence )
            valid_sequence.set_attribute( 'step', ['GEN','VALIDATION:genvalid_all'])
            valid_sequence.set_attribute( 'eventcontent' , ['DQM'])
            valid_sequence.set_attribute( 'datatier' , ['DQM'])

        elif firstStep in ['LHE','NONE']:
            cmsd_list += '\n\n'
            valid_sequence = sequence( firstSequence )
            ## when integrated properly
            if firstStep=='LHE':
                valid_sequence.set_attribute( 'step', [firstStep,'USER:GeneratorInterface/LHEInterface/lhe2HepMCConverter_cff.generator','GEN','VALIDATION:genvalid_all'])
            else:
                valid_sequence.set_attribute( 'step', ['USER:GeneratorInterface/LHEInterface/lhe2HepMCConverter_cff.generator','GEN','VALIDATION:genvalid_all'])
            valid_sequence.set_attribute( 'eventcontent' , ['DQM'])
            valid_sequence.set_attribute( 'datatier' , ['DQM'])
            dump_python= '--dump_python' ### only there until it gets fully integrated in all releases
        if valid_sequence:
            self.setup_harvesting(directory,run)

            ## until we have full integration in the release
            cmsd_list +='addpkg GeneratorInterface/LHEInterface 2> /dev/null \n'
            cmsd_list +='curl -s http://cmssw.cvs.cern.ch/cgi-bin/cmssw.cgi/CMSSW/GeneratorInterface/LHEInterface/python/lhe2HepMCConverter_cff.py?revision=HEAD -o GeneratorInterface/LHEInterface/python/lhe2HepMCConverter_cff.py \n'
            cmsd_list +='\nscram b -j5 \n'

            genvalid_request = request( self.json() )
            genvalid_request.set_attribute( 'sequences' , [valid_sequence.json()])

            self.genvalid_driver = '%s --fileout file:genvalid.root --mc -n %d --python_filename %sgenvalid.py %s --no_exec \n'%(genvalid_request.build_cmsDriver(0),
                                                                                                                                 int(n_to_valid),
                                                                                                                                 directory,
                                                                                                                                 dump_python)
            if run:
                self.genvalid_driver += 'cmsRun -e -j %s%s_gv.xml %sgenvalid.py || exit $? ; \n'%( directory, self.get_attribute('prepid'),
                                                                                               directory)
                ## put back the perf report to McM ! wil modify the request object while operating on it.
                # and therefore the saving of the request will fail ...
                #self.genvalid_driver += 'curl -k --cookie /afs/cern.ch/user/v/vlimant/private/dev-cookie.txt https://cms-pdmv-dev.cern.ch/mcm/restapi/requests/perf_report/%s/eff -H "Content-Type: application/xml" -X PUT --data "@%s%s_gv.xml" \n' %(self.get_attribute('prepid'), directory, self.get_attribute('prepid'))

            cmsd_list += self.genvalid_driver +'\n'
            ###self.logger.log( 'valid request %s'%( genvalid_request.json() ))
            cmsd_list += self.harvesting_driver + '\n'

        ##that's the end of the part for gen-valid that should be somewhere else
        ############################################################################
        return (infile,cmsd_list)

    def setup_harvesting(self,directory,run):
        self.harvesting_driver = 'cmsDriver.py step2 --filein file:genvalid.root --conditions auto:startup --mc -s HARVESTING:genHarvesting --harvesting AtJobEnd --python_filename %sgenvalid_harvesting.py --no_exec \n'%(directory)
        if run:
            self.harvesting_driver +='cmsRun %sgenvalid_harvesting.py  || exit $? ; \n'%(directory)

        dqm_dataset = '/RelVal%s/%s-%s-genvalid-v%s/DQM'%(self.get_attribute('dataset_name'),
                                                          self.get_attribute('cmssw_release'),
                                                          self.get_attribute('sequences')[0]['conditions'].replace('::All',''),
                                                          self.get_attribute('version')
                                                          )
        dqm_file = 'DQM_V0001_R000000001__RelVal%s__%s-%s-genvalid-v%s__DQM.root'%( self.get_attribute('dataset_name'),
                                                                                    self.get_attribute('cmssw_release'),
                                                                                    self.get_attribute('sequences')[0]['conditions'].replace('::All',''),
                                                                                    self.get_attribute('version')
                                                                                    )

        
        where ='https://cmsweb.cern.ch/dqm/relval'
        l_type = locator()
        if l_type.isDev():
            where ='https://cmsweb-testbed.cern.ch/dqm/dev'
        where ='https://cmsweb-testbed.cern.ch/dqm/dev'
        self.harverting_upload = ''        
        self.harverting_upload += 'mv DQM_V0001_R000000001__Global__CMSSW_X_Y_Z__RECO.root %s \n' %( dqm_file ) 
        self.harverting_upload += 'curl -s https://raw.github.com/rovere/dqmgui/master/bin/visDQMUpload -o visDQMUpload \n'
        self.harverting_upload += 'source /afs/cern.ch/cms/LCG/LCG-2/UI/cms_ui_env.sh \n'
        self.harverting_upload += 'cat /afs/cern.ch/user/p/pdmvserv/private/PdmVService.txt | voms-proxy-init -voms cms --valid 240:00 -pwstdin \n'
        self.harverting_upload += 'python visDQMUpload %s %s &> run.log || exit $? ; \n'%( where, dqm_file )
        
        ##then the url back to the validation sample in the gui !!!
        val=self.get_attribute('validation')
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
                if self.get_attribute('input_filename'):
                    return 'MonteCarloFromGEN'
                else:
                    return 'MonteCarlo'
            else:
                return 'MonteCarloFromGEN'
        elif  self.get_attribute('type') in ['LHE','LHEStepZero']:
            return 'LHEStepZero' 
        elif self.get_attribute('type') == 'MCReproc':
            return 'ReDigi'

        return ''


    def verify_sanity(self):
        ###check whether there are missing bits and pieces in the request
        ##maybe raise instead of just returning false
        wma_type= self.get_wmagent_type()
        if wma_type in ['MonteCarloFromGEN','ReDigi'] and not self.get_attribute('input_filename'):
            #raise Exception('Input Dataset name is not defined.')
            return True
        if wma_type in ['MonteCarlo','MonteCarloFromGEN','LHEStepZero']:
            if not self.get_attribute('fragment_tag') and not self.get_attribute('fragment') and not self.get_attribute('name_of_fragment'):
                if wma_type=='LHEStepZero' and self.get_attribute('mcdb_id')<=0:
                    raise Exception('No CVS Production Tag is defined. No fragement name, No fragment text')
                    #return False
        for cmsDriver in self.build_cmsDrivers():
            if not 'conditions' in cmsDriver:
                raise Exception('Conditions are not defined in %s'%(cmsDriver))
                #return False

        return True


    def get_actors(self,N=-1,what='author_username'):
        #get the actors from itself, and all others it is related to
        actors=json_base.get_actors(self,N,what)
        crdb=database('chained_requests')
        lookedat=[]
        for cr in self.get_attribute('member_of_chain'):
            ## this protection is bad against malformed db content. it should just fail badly with exception
            if not crdb.document_exists(cr):
                self.logger.error('For requests %s, the chain %s of which it is a member of does not exist.'%( self.get_attribute('prepid'), cr))
                continue
            crr = crdb.get(cr)
            for other in crr['chain']:
            #limit to those before this one ? NO, the comment could go backward as it could go "forward"
            #for other in crr['chain'][0:crr['chain'].index(self.get_attribute('prepid'))]:
                rdb = database('requests')
                other_r = request(rdb.get(other))
                lookedat.append(other_r.get_attribute('prepid'))
                actors.extend(json_base.get_actors(other_r,N,what))
        #self.logger.log('Looked at %s'%(str(lookedat)))
        actors = list(set(actors))
        return actors

    def test_failure(self,message,what='Submission',rewind=False):
        if rewind:
            self.set_status(0)
            self.approve(0)
        self.update_history({'action':'failed'})
        self.notify('%s failed for request %s'%(what,self.get_attribute('prepid')), message)
        rdb = database('requests')
        rdb.update(self.json())

    def get_stats(self,
                  keys_to_import = ['pdmv_dataset_name','pdmv_dataset_list','pdmv_status_in_DAS','pdmv_status_from_reqmngr','pdmv_evts_in_DAS'],
                  override_id=None):
        #existing rwma
        mcm_rr=self.get_attribute('reqmgr_name')
        statsDB = database('stats',url='http://cms-pdmv-stats.cern.ch:5984/')

        def transfer( stats_r , keys_to_import):
            mcm_content={}
            if not len(keys_to_import):
                keys_to_import = stats_r.keys()
            for k in keys_to_import:
                mcm_content[k] = stats_r[k]            
            return mcm_content

        ####
        ## update all existing
        earliest_date=None
        if not len(mcm_rr):
            earliest_date=0
        for rwma_i in range(len(mcm_rr)):
            rwma = mcm_rr[rwma_i]
            if not statsDB.document_exists( rwma['name'] ):
                self.logger.error('the request %s is linked in McM already, but is not in stats DB'%(rwma['name']))
                ## very likely, this request was aborted, rejected, or failed
                ## should we be removing it ?
                continue
            stats_r = statsDB.get( rwma['name'] )
            if not earliest_date or int(earliest_date)> int(stats_r['pdmv_submission_date']):
                earliest_date = stats_r['pdmv_submission_date'] #yymmdd
            mcm_content=transfer( stats_r , keys_to_import )
            mcm_rr[rwma_i]['content'] = mcm_content

        ####
        ## look for new ones
        look_for_what = self.get_attribute('prepid')
        if override_id:
            look_for_what = override_id
        stats_rr = statsDB.query(query='prepid==%s'%(look_for_what) ,page_num=-1)
        ### order them from [0] earliest to [n] latest
        def sortRequest(r1 , r2):
            if r1['pdmv_submission_date'] == r2['pdmv_submission_date']:
                return cmp(r1['pdmv_request_name'] , r2['pdmv_request_name'])
            else:
                return cmp(r1['pdmv_submission_date'] , r2['pdmv_submission_date'])
        stats_rr.sort( cmp = sortRequest )

        self.logger.error(' get stats with date %s , %s existings and %s matching'%( earliest_date, len(mcm_rr), len(stats_rr) ))

        #self.logger.error('found %s'%(stats_rr))
        one_new=False
        for stats_r in stats_rr:
            ## only add it if not present yet
            if stats_r['pdmv_request_name'] in map(lambda d : d['name'], mcm_rr):
                continue
            
            ## only add if the date is later than the earliest_date
            if not 'pdmv_submission_date' in stats_r:
                continue
            if  int(stats_r['pdmv_submission_date']) < int(earliest_date):
                continue
                
            mcm_content=transfer( stats_r , keys_to_import)
            mcm_rr.append( { 'content' : mcm_content,
                             'name' : stats_r['pdmv_request_name']})
            one_new=True

        #if one_new:
            # order those requests properly
            ### FIXME
            #then set it back if at least one new    
        self.set_attribute('reqmgr_name', mcm_rr)
        return one_new

    def inspect(self):
        ### this will look for corresponding wm requests, add them, check on the last one in date and check the status of the output DS for ->done
        not_good = {"prepid": self.get_attribute('prepid'), "results":False}

        # only if you are in submitted status
        ## later, we could inspect on "approved" and trigger injection
        if self.get_attribute('status') == 'submitted':
            return self.inspect_submitted()
        elif self.get_attribute('status') == 'approved':
            return self.inspect_approved()
        
        not_good.update( {'message' : 'cannot inspect a request in %s status'%(self.get_attribute('status'))} )
        return not_good

    def inspect_approved(self):
        ## try to inject the request
        not_good = {"prepid": self.get_attribute('prepid'), "results":False} 
        not_good.update( {'message' : 'Not implemented yet to inspect a request in %s status'%(self.get_attribute('status'))} ) 
        return not_good 

    def inspect_submitted(self):
        not_good = {"prepid": self.get_attribute('prepid'), "results":False}
        ## get fresh up to date stats
        one_new = self.get_stats()
        mcm_rr = self.get_attribute('reqmgr_name')
        db = database( 'requests')
        if len(mcm_rr):
            if ('pdmv_status_in_DAS' in mcm_rr[-1]['content'] and 'pdmv_status_from_reqmngr' in mcm_rr[-1]['content']):
                if mcm_rr[-1]['content']['pdmv_status_in_DAS'] == 'VALID' and mcm_rr[-1]['content']['pdmv_status_from_reqmngr'] == 'announced':
                    ## how many events got completed for real
                    self.set_attribute('completed_events' , mcm_rr[-1]['content']['pdmv_evts_in_DAS'] )

                    if self.get_attribute('completed_events') <=0:
                        not_good.update( {'message' : '%s completed but with no statistics. stats DB lag. saving the request anyway.'%( mcm_rr[-1]['content']['pdmv_dataset_name'])})
                        saved = db.save( self.json() )
                        return not_good
                    ## set next status: which can only be done at this stage
                    self.set_status(with_notification=True)
                    ## save the request back to db
                    saved = db.save( self.json() )
                    if saved:
                        return {"prepid": self.get_attribute('prepid'), "results":True}
                    else:
                        not_good.update( {'message' : "Set status to %s could not be saved in DB"%(self.get_attribute('status'))})
                        return not_good
                else:
                    if one_new: db.save( self.json() )
                    not_good.update( {'message' : "last request %s is not ready"%(mcm_rr[-1]['name'])})
                    return not_good
            else:
                if one_new: db.save( self.json() )
                not_good.update( {'message' : "last request %s is malformed %s"%(mcm_rr[-1]['name'],
                                                                                 mcm_rr[-1]['content'])})
                return not_good
        else:
            ## add a reset acion here, in case in prod instance ?
            not_good.update( {'message' : " there are no requests in request manager. Please invsetigate!"})
            return not_good

    def parse_fragment(self):
        if  self.get_attribute('fragment'):
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
                     return  int(numbers[len(numbers)-1])
                 except:
                     return None
        return None

    def textified(self):
        l_type = locator()
        view_in_this_order=['pwg','prepid','dataset_name','mcdb_id','analysis_id','notes','total_events','validation','approval','status','input_filename','member_of_chain','reqmgr_name','completed_events']
        text=''
        for view in view_in_this_order:
            if self.get_attribute(view):
                if type(self.get_attribute(view)) == list:
                    for (i,item) in enumerate(self.get_attribute(view)):
                        text += '%s[%s] : %s \n' %( view, i, pprint.pformat(item))
                elif type(self.get_attribute(view)) == int:
                    if self.get_attribute(view) > 0:
                        text += '%s : %s \n'%(view, self.get_attribute(view))
                else:
                    text += '%s : %s \n'%(view, self.get_attribute(view))
        text+='\n'
        text+='%srequests?prepid=%s'%(l_type.baseurl(), self.get_attribute('prepid'))
        return text

    def get_n_for_test(self):
        events = 10.0
        # the matching and filter efficiencies
        if self.get_attribute('generator_parameters'):
            ## get the last entry of generator parameters
            match = float(self.get_attribute('generator_parameters')[-1]['match_efficiency'])
            filter_eff = float(self.get_attribute('generator_parameters')[-1]['filter_efficiency'])
            if match > -1 and filter_eff > -1:
                events /=  (match*filter_eff)


        if events>1000:
            return int(50)
        elif events>=1:
            return int(events)
        else:
            ##default to 5
            return int(5)

    def unique_string(self, step_i):
        ### create a string that supposedly uniquely identifies the request configuration for step 
        uniqueString=''
        if self.get_attribute('fragment'):
            fragment_hash = hashlib.sha224(self.get_attribute('fragment')).hexdigest()
            uniqueString+=fragment_hash
        if self.get_attribute('fragment_tag'):
            uniqueString+=self.get_attribute('fragment_tag')
        if self.get_attribute('name_of_fragment'):
            uniqueString+=self.get_attribute('name_of_fragment')
        if self.get_attribute('mcdb_id')>=0:
            uniqueString+='mcdb%s'%(self.get_attribute('mcdb_id'))
        uniqueString+= self.get_attribute('cmssw_release')
        seq=sequence(self.get_attribute('sequences')[step_i])
        uniqueString+=seq.to_string()
        return uniqueString

    def configuration_identifier(self, step_i):
        uniqueString=self.unique_string(step_i)
        #create a hash value that supposedly uniquely defines the configuration
        hash_id=hashlib.sha224(uniqueString).hexdigest()
        return hash_id

    def update_performance(self, xml_doc, what):
        total_event_in = self.get_n_for_test()
        
        xml_data = xml.dom.minidom.parseString( xml_doc )
        
        total_event= float(xml_data.documentElement.getElementsByTagName("TotalEvents")[-1].lastChild.data)
        if total_event==0:
            self.logger.error("For % the total number of events in output of the test is 0"%( self.get_attribute('prepid')))
            return

        timing = None
        file_size = None
        for item in xml_data.documentElement.getElementsByTagName("PerformanceReport"):
            for summary in item.getElementsByTagName("PerformanceSummary"):
                for perf in summary.getElementsByTagName("Metric"):
                    name=perf.getAttribute('Name')
                    if name == 'AvgEventTime':
                        timing = float( perf.getAttribute('Value'))
                    if name == 'Timing-tstoragefile-write-totalMegabytes':
                        file_size = float( perf.getAttribute('Value')) 
        
        if timing:
            timing = int( timing/ total_event)
        if file_size:
            file_size = int(  file_size / total_event)

        efficiency = total_event / total_event_in
        efficiency_error = efficiency * sqrt( 1./total_event + 1./total_event_in )

        geninfo=None
        if len(self.get_attribute('generator_parameters')):
            geninfo = self.get_attribute('generator_parameters')[-1]
               
        to_be_saved= False

        to_be_changed='filter_efficiency'
        if self.get_attribute('input_filename'):
            to_be_changed='match_efficiency'

        self.logger.error("Calculated all eff: %s eff_err: %s timing: %s size: %s" % ( efficiency, efficiency_error, timing, file_size ))

        if what =='eff':
            if not geninfo or geninfo[to_be_changed+'_error'] > efficiency_error:
                ## we have a better error on the efficiency: combine or replace: replace for now
                self.update_generator_parameters()
                added_geninfo = self.get_attribute('generator_parameters')[-1]
                added_geninfo[to_be_changed] = efficiency
                added_geninfo[to_be_changed+'_error'] = efficiency_error
                to_be_saved=True
        elif what =='perf':
            if timing:
                self.set_attribute('time_event', timing)
                to_be_saved=True
            if file_size:
                self.set_attribute('size_event', file_size)
                to_be_saved=True

        if to_be_saved:
            self.update_history({'action':'update','step':what})

        return to_be_saved

    def reset(self):
        self.approve(0)
        ## make sure to keep track of what needs to be invalidated in case there is
        invalidation = database('invalidations')
        ds_to_invalidate=[]
        # retrieve the latest requests for it
        self.get_stats()
        # increase the revision only if there was a request in req mng, or a dataset already on the table
        increase_revision=False
        # and put them in invalidation
        for wma in self.get_attribute('reqmgr_name'):
            new_invalidation={"object" : wma['name'], "type" : "request", "status" : "new" , "prepid" : self.get_attribute('prepid')}
            new_invalidation['_id'] = new_invalidation['object']
            invalidation.save( new_invalidation )
            if 'content' in wma and 'pdmv_dataset_list' in wma['content']:
                ds_to_invalidate.extend( wma['content']['pdmv_dataset_list'])
            if 'content' in wma and 'pdmv_dataset_name' in wma['content']:
                ds_to_invalidate.append( wma['content']['pdmv_dataset_name'])
            ds_to_invalidate=list(set(ds_to_invalidate))
            increase_revision=True
        for ds in ds_to_invalidate:
            new_invalidation={"object" : ds, "type" : "dataset", "status" : "new" , "prepid" : self.get_attribute('prepid')}
            new_invalidation['_id'] = new_invalidation['object'].replace('/','')
            invalidation.save( new_invalidation )
            increase_revision=True
        self.set_attribute('completed_events', 0)
        self.set_attribute('reqmgr_name',[])
        self.set_attribute('config_id',[])
        if increase_revision:
            self.set_attribute('version', self.get_attribute('version')+1)
        self.set_status(step=0,with_notification=True)
        


class runtest_genvalid(handler):
    """
    operate the run test, operate the gen_valid, upload to the gui and toggles the status to validation
    """
    def __init__(self, **kwargs):
        handler.__init__(self, **kwargs)
        self.rid = kwargs['rid']
        self.db = database('requests')
        
    def run(self):
        location = installer( self.rid, care_on_existing=False, clean_on_exit=False)
        
        test_script = location.location()+'validation_run_test.sh'
        there = open( test_script ,'w')
        ## one has to wait just a bit, so that the approval change operates, and the get retrieves the latest greatest _rev number
        #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
        time.sleep( 10 )
        mcm_r = request(self.db.get(self.rid))
        #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
        n_for_test = mcm_r.get_n_for_test()
        ## the following does change something on the request object, to be propagated in case of success
        there.write( mcm_r.get_setup_file( location.location() , n_for_test) )        
        there.close()
        
        batch_test = batch_control( self.rid, test_script )
        success = batch_test.test()
        self.logger.log("batch_test result is %s" % success)
        try:
            #suck in run-test if present
            rt_xml=location.location()+'%s_rt.xml'%( self.rid )
            if os.path.exists( rt_xml ):
                mcm_r.update_performance( open(rt_xml).read(), 'perf')
        except:
            self.logger.error('Failed to get perf reports \n %s'%(traceback.format_exc()))
            success = False
        try:
            gv_xml=location.location()+'%s_gv.xml'%( self.rid )
            if os.path.exists( gv_xml ):
                mcm_r.update_performance( open(gv_xml).read(), 'eff')
        except:
            self.logger.error('Failed to get gen valid reports \n %s'%(traceback.format_exc()))
            success = False


        self.logger.error('I came all the way to here and %s'%( success ))
        if not success:
            ## need to provide all the information back
            the_logs='\t .out \n%s\n\t .err \n%s\n '% ( batch_test.log_out, batch_test.log_err)
            #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
            # reset the content of the request
            mcm_r = request(self.db.get(self.rid))
            mcm_r.test_failure(message=the_logs,what='Validation run test',rewind=True)
            #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
        else:
            #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))
            ## change the status with notification
            mcm_current = request(self.db.get(self.rid))
            if mcm_current.json()['_rev']==mcm_r.json()['_rev']:
                ## it's fine to push it through
                mcm_r.set_status(with_notification=True)
                saved = self.db.update( mcm_r.json() )
                if not saved:
                    mcm_current.test_failure(message='The request could not be saved after the run test procedure',what='Validation run test',rewind=True)
            else:
                mcm_current.test_failure(message='The request has changed during the run test procedure, preventing from being saved',what='Validation run test',rewind=True)
            #self.logger.error('Revision %s'%( self.db.get(self.rid)['_rev']))

        location.close()


