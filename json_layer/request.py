#!/usr/bin/env python

import copy
import os 

from couchdb_layer.prep_database import database

from json import loads,dumps
from json_layer.json_base import json_base
from json_layer.generator_parameters import generator_parameters
from json_layer.sequence import sequence
#from json_layer.action import action
#from tools.authenticator import authenticator

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
            #'completion_date':'', 
            'cmssw_release':'',
            'input_filename':'',
            'pwg':'',
            'validation':'',
            'dataset_name':'',
            'pileup_dataset_name':'',
            #'www':'',
            'process_string':'',
            'extension': False,
            #'input_block':'',
            'block_black_list':[], 
            'block_white_list':[], 
            'cvs_tag':'',
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
            'generators':'',
            'sequences':[],
            'generator_parameters':[], 
            'reqmgr_name':[], # list of tuples (req_name, valid)
            'approval':self.get_approval_steps()[0],
            'analysis_id':[],
            }
        # update self according to json_input
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

    def get_editable(self):
        editable= {}
        if self.get_attribute('status')!='new': ## after being new, very limited can be done on it
            for key in self._json_base__schema:
                editable[key]=False
            if self.current_user_level!=0: ## not a simple user
                for key in ['generator_parameters','notes','history']:
                    editable[key]=True
            if self.current_user_level>3: ## only for admins
                for key in ['completed_events','reqmgr_name','member_of_chain','config_id']:
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
        ## a state machine should come along and submit jobs for validation, then set the status to validation once on-going
        # for now: hard-wire the toggling
        self.set_status()

    def ok_to_move_to_approval_define(self):
        if self.current_user_level==0:
            ##not allowed to do so 
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','bad user admin level %s'%(self.current_user_level))
        ## we could restrict certain step to certain role level
        #if self.current_user_role != 'generator_contact':
        #    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','bad user role %s'%(self.current_user_role))

        if self.get_attribute('status')!='validation':
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation')
        ## a state machine should come along and create the configuration. check the filter efficiency, and set information back
        # then toggle the status
        self.set_status()

    def ok_to_move_to_approval_approve(self):
        if self.current_user_level<=1:
            ##not allowed to do so 
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','bad user admin level %s'%(self.current_user_level))

        if self.get_attribute('status')!='defined':
            raise self.WrongApprovalSequence(self.get_attribute('status'),'approve')
        
        ## from defined status, with generator convener approval (?should this be removed???)
        # this one will probably stay hard-wired, unless we decide on something very specific, like resource estimation: a state machine would come along, check, raise alarms, or set to approved
        self.set_status()

    def ok_to_move_to_approval_submit(self):
        if self.current_user_level<=2:
            ##not allowed to do so                                                                                                                                                                                                                                                  
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','bad user admin level %s'%(self.current_user_level))

        if self.get_attribute('status')!='approved':
            raise self.WrongApprovalSequence(self.get_attribute('status'),'submit')
        
        ## the request manager could pull out those requests approved to be submitted
        ## the production manager would go and submit those by hand via McM : the status is set automatically upon proper injection
        # remains to the production manager to announce the batch the requests are part of
        #### not settting any status forward
        

    def get_fragment(self):
        #fragment=self.get_attribute('name_of_fragment').decode('utf-8')
        fragment=self.get_attribute('name_of_fragment')
        if self.get_attribute('fragment') and not fragment:
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

    def build_cmsDrivers(self,cast=0):
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
          rdb = database('requests')
          #rdb.update(self.json())
          rdb.update(new_req)
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
          rdb = database('requests')
          rdb.update(self.json())
          
      for i in range(len(self.get_attribute('sequences'))):
        cd = self.build_cmsDriver(i)
        if cd:
            commands.append(cd)

      return commands  

    
    def update_generator_parameters(self):#, generator_parameters={}):
        #if not generator_parameters:
        #    return
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

    def get_scram_arch(self):
        scram_arch='slc5_amd64_gcc434'
        releasesplit=self.get_attribute('cmssw_release').split("_")
        nrelease=releasesplit[1]+releasesplit[2]+releasesplit[3]
        if int(nrelease)>=510:
            scram_arch='slc5_amd64_gcc462'
        return scram_arch
    
    def get_setup_file(self,directory='',events=10):
        
        infile = ''
        infile += '#!/bin/bash\n'
        if self.get_attribute('fragment'):
            infile += 'cern-get-sso-cookie -u https://cms-pdmv-dev.cern.ch/mcm/ -o ~/private/cookie.txt --krb\n'
        if directory:
            infile += 'cd ' + os.path.abspath(directory + '../') + '\n'
        infile += 'source  /afs/cern.ch/cms/cmsset_default.sh\n'
        infile += 'export SCRAM_ARCH=%s\n'%(self.get_scram_arch())
        infile += 'scram p CMSSW ' + self.get_attribute('cmssw_release') + '\n'
        infile += 'cd ' + self.get_attribute('cmssw_release') + '/src\n'
        infile += 'eval `scram runtime -sh`\n'

        infile += 'export CVSROOT=:pserver:anonymous@cmscvs.cern.ch:/local/reps/CMSSW\n'
        infile += "echo '/1 :pserver:anonymous@cmscvs.cern.ch:2401/local/reps/CMSSW AA_:yZZ3e' > cvspass\n"
        infile += "export CVS_PASSFILE=`pwd`/cvspass\n"

        # checkout from cvs (if needed)
        if self.get_attribute('name_of_fragment') and self.get_attribute('cvs_tag'):
            infile += 'cvs co -r ' + self.get_attribute('cvs_tag') + ' ' + self.get_attribute('name_of_fragment') + '\n'
        
        ##copy the fragment directly from the DB into a file
        if self.get_attribute('fragment'):
            infile += 'curl -k -L -s --cookie-jar ~/private/cookie.txt --cookie ~/private/cookie.txt https://cms-pdmv-dev.cern.ch/mcm/restapi/requests/get_fragment/%s/0 --create-dirs -o %s \n'%(self.get_attribute('prepid'),self.get_fragment())

        # previous counter
        previous = 0

        # validate and build cmsDriver commands
        cmsd_list = ''
        for cmsd in self.build_cmsDrivers():

            # check if customization is needed to check it out from cvs
            if '--customise' in cmsd:
                cust = cmsd.split('--customise=')[1].split(' ')[0]
                toks = cust.split('.')
                cname = toks[0]
                cfun = toks[1]

                # add customization
                if 'GenProduction' in cname:
                    infile += 'cvs co -r ' + self.get_attribute('cvs_tag') + ' Configuration/GenProduction/python/' + cname.split('/')[-1]
            # tweak a bit more finalize cmsDriver command
            res = cmsd
            res += ' --python_filename '+directory+'config_0_'+str(previous+1)+'_cfg.py '
            #JR res += '--fileout step'+str(previous+1)+'.root '
            if previous > 0:
                #JR res += '--filein file:step'+str(previous)+'.root '
                res += '--lazy_download '

            ##JR it's going to be easier to look at things with no dump_python
            #res += '--no_exec --dump_python -n '+str(self.events)#str(self.request.get_attribute('total_events'))
            res += '--no_exec -n '+str(events)#str(self.request.get_attribute('total_events'))
            #infile += res
            cmsd_list += res + '\n'

            previous += 1

        infile += '\nscram b\n'
        infile += cmsd_list
        # since it's all in a subshell, there is
        # no need for directory traversal (parent stays unaffected)
        infile += 'cd ../../\n'
        return infile

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
            raise Exception('Input Dataset name is not defined.')
            #return False
        if wma_type in ['MonteCarlo','MonteCarloFromGEN','LHEStepZero']:
            if not self.get_attribute('cvs_tag') and not self.get_attribute('fragment') and not self.get_attribute('name_of_fragment'):
                if wma_type=='LHEStepZero' and self.get_attribute('mcdb_id')<=0:
                    raise Exception('No CVS Production Tag is defined. No fragement name, No fragment text')
                    #return False
        for cmsDriver in self.build_cmsDrivers():
            if not 'conditions' in cmsDriver:
                raise Exception('Conditions are not defined in %s'%(cmsDriver))
                #return False

        return True
