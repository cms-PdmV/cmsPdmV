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
                chain=crdb.get(inchain)
                if chain['chain'][-1] == self.get_attribute('prepid'):
                    chain['last_status'] = self.get_attribute('status')
                    crdb.save(chain)
        
    def get_editable(self):
        editable= {}
        if self.get_attribute('status')!='new': ## after being new, very limited can be done on it
            for key in self._json_base__schema:
                editable[key]=False
            if self.current_user_level!=0: ## not a simple user
                for key in ['generator_parameters','notes','history']:
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

        if not self.get_attribute('dataset_name') or ' ' in self.get_attribute('dataset_name'):
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The dataset name is invalid: either null string or containing blanks')

        gen_p = self.get_attribute('generator_parameters')
        if not len(gen_p) or generator_parameters(gen_p[-1]).isInValid():
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The generator parameters is invalid: either none or negative or null values, or efficiency larger than 1')

        if self.get_attribute('time_event') <=0 or self.get_attribute('size_event')<=0:
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The time per event or size per event are invalid: negative or null')

        if not self.get_attribute('fragment') and (not ( self.get_attribute('name_of_fragment') and self.get_attribute('cvs_tag'))):
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The configuration fragment is not available. Neither fragment or name_of_fragment are available')

        if self.get_attribute('total_events') < 0:
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The number of requested event is invalid: Negative')


        rdb=database('requests')
        similar_ds = filter(lambda doc : doc['member_of_campaign'] == self.get_attribute('member_of_campaign'), map(lambda x: x['value'],  rdb.query('dataset_name==%s'%(self.get_attribute('dataset_name')))))
        
        if len(similar_ds)>1:
            if len(similar_ds)>2:
                raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','Three or more requests with the same dataset name in that campaign')
            if similar_ds[0]['extension'] == similar_ds[1]['extension']:
                raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','Two requests with the same dataset name, and they are not extension of each other')
        

        ##this below needs fixing
        if not len(self.get_attribute('member_of_chain')):
            #not part of any chains ...
            if self.get_attribute('mcdb_id')>0 and not self.get_attribute('input_filename'):
                self.logger.error(self.get_attribute('status')+' validation'+'The request has an mcdbid, not input dataset, and not member of chained request: this is not allowed')
                ##do not make it a n exception yet
                #raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The request has an mcdbid, not input dataset, and not member of chained request: this is not allowed')

        else:
            crdb = database('chained_requests')
            for cr in self.get_attribute('member_of_chain'):
                mcm_cr = crdb.get(cr)
                if mcm_cr['chain'].index( self.get_attribute('prepid') ) ==0:
                    if self.get_attribute('mcdb_id')>0 and not self.get_attribute('input_filename'):
                        raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The request has an mcdbid, not input dataset, and is considered to be a request at the root of its chains; this is not allowed')

        ## a state machine should come along and submit jobs for validation, then set the status to validation once on-going
        # for now: hard-wire the toggling
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
        if self.current_user_level<=2:
            ##not allowed to do so                                                                                                                                                                                                                                                  
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','bad user admin level %s'%(self.current_user_level))


        if self.get_attribute('status')!='approved':
            raise self.WrongApprovalSequence(self.get_attribute('status'),'submit')
        
        if not len(self.get_attribute('member_of_chain')):
            raise self.WrongApprovalSequence(self.get_attribute('status'),'submit','This request is not part of any chain yet')

        ## the request manager could pull out those requests approved to be submitted
        ## the production manager would go and submit those by hand via McM : the status is set automatically upon proper injection
        # remains to the production manager to announce the batch the requests are part of
        #### not settting any status forward
        

    def get_fragment(self):
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
    
    def get_setup_file(self,directory='',events=10):
        infile = ''
        infile += '#!/bin/bash\n'
        #if self.get_attribute('fragment'):
        #    infile += 'cern-get-sso-cookie -u https://cms-pdmv-dev.cern.ch/mcm/ -o ~/private/cookie.txt --krb\n'
        if directory:
            infile += 'cd ' + os.path.abspath(directory + '../') + '\n'
        infile += 'source  /afs/cern.ch/cms/cmsset_default.sh\n'
        infile += 'export SCRAM_ARCH=%s\n'%(self.get_scram_arch())
        infile += 'if [ -r %s ] ; then \n'%(self.get_attribute('cmssw_release'))
        infile += ' echo release %s already exists\n'%(self.get_attribute('cmssw_release'))
        infile += 'else\n'
        infile += 'scram p CMSSW ' + self.get_attribute('cmssw_release') + '\n'
        infile += 'fi\n'
        infile += 'cd ' + self.get_attribute('cmssw_release') + '/src\n'
        infile += 'eval `scram runtime -sh`\n'

        def initCvs():
            txt=''
            if not initCvs.cvsInit:
                txt += 'export CVSROOT=:pserver:anonymous@cmscvs.cern.ch:/local/reps/CMSSW\n'
                txt += "echo '/1 :pserver:anonymous@cmscvs.cern.ch:2401/local/reps/CMSSW AA_:yZZ3e' > cvspass\n"
                txt += "export CVS_PASSFILE=`pwd`/cvspass\n"
            initCvs.cvsInit=True
            return txt
        initCvs.cvsInit = False
        # checkout from cvs (if needed)
        if self.get_attribute('name_of_fragment') and self.get_attribute('cvs_tag'):
            infile+=initCvs()
            infile += 'cvs co -r ' + self.get_attribute('cvs_tag') + ' ' + self.get_attribute('name_of_fragment') + '\n'
        
        ##copy the fragment directly from the DB into a file
        if self.get_attribute('fragment'):
            #infile += 'curl -k -L -s --cookie-jar ~/private/cookie.txt --cookie ~/private/cookie.txt https://cms-pdmv-dev.cern.ch/mcm/restapi/requests/get_fragment/%s --create-dirs -o %s \n'%(self.get_attribute('prepid'),self.get_fragment())
            infile += 'curl -s --insecure https://cms-pdmv-dev.cern.ch/mcm/public/restapi/requests/get_fragment/%s --create-dirs -o %s \n'%(self.get_attribute('prepid'),self.get_fragment())

        # previous counter
        previous = 0

        # validate and build cmsDriver commands
        cmsd_list = ''
        
        for cmsd in self.build_cmsDrivers():

            # check if customization is needed to check it out from cvs
            if '--customise' in cmsd:
                cust = cmsd.split('--customise ')[1].split(' ')[0]
                toks = cust.split('.')
                cname = toks[0]
                cfun = toks[1]

                # add customization
                if 'GenProduction' in cname:
                    infile += initCvs()
                    infile += 'cvs co -r ' + self.get_attribute('cvs_tag') + ' Configuration/GenProduction/python/' + cname.split('/')[-1]
            # tweak a bit more finalize cmsDriver command
            res = cmsd
            #res += ' --python_filename '+directory+'config_0_'+str(previous+1)+'_cfg.py '
            res += ' --python_filename '+directory+self.get_attribute('prepid')+"_"+str(previous+1)+'_cfg.py '
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

        ## gen valid configs
        # to be refined using the information of the campaign
        firstSequence = self.get_attribute('sequences')[0]
        firstStep = firstSequence['step'][0]
        harvesting_and_dqm_upload='cmsDriver.py step2 --filein file:genvalid.root --conditions auto:startup --mc -s HARVESTING:genHarvesting --harvesting AtJobEnd --python_filename %sgenvalid_harvesting.py --no_exec \n'%(directory)
        valid_sequence = None
        n_to_valid=10000 #get it differently than that
        val_sentence=self.get_attribute('validation')
        if val_sentence:
            val_parameters=map( lambda spl: tuple(spl.split(':',1)), val_sentence.split(','))
            for (k,a) in val_parameters:
                if k == 'nEvents':
                    n_to_valid = int(a)
                
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
        
        ##############
        ## switch it off there
        ##############
        valid_sequence = None
        if valid_sequence:
            ## until we have full integration in the release
            infile += initCvs()
            cmsd_list +='addpkg GeneratorInterface/LHEInterface 2> /dev/null \n'
            cmsd_list +='cvs co -r HEAD GeneratorInterface/LHEInterface/python/lhe2HepMCConverter_cff.py 2> /dev/null \n'
            cmsd_list +='\nscram b -j5 \n'

            genvalid_request = request( self.json() )
            genvalid_request.set_attribute( 'sequences' , [valid_sequence.json()])
            cmsd_list += '%s --fileout file:genvalid.root --mc -n %d --python_filename %sgenvalid.py --no_exec \n'%(genvalid_request.build_cmsDriver(0),
                                                                                                          n_to_valid,
                                                                                                          directory)
            ###self.logger.log( 'valid request %s'%( genvalid_request.json() ))
            cmsd_list += harvesting_and_dqm_upload            

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


    def get_actors(self,N=-1,what='author_username'):
        #get the actors from itself, and all others it is related to
        actors=json_base.get_actors(self,N,what)
        crdb=database('chained_requests')
        lookedat=[]
        for cr in self.get_attribute('member_of_chain'):
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

    def test_failure(self,message,rewind=False):
        if rewind:
            self.set_status(0)
            self.approve(0)
        self.update_history({'action':'failed'})
        self.notify('Submission failed for request %s'%(self.get_attribute('prepid')), message)
        rdb = database('requests')
        rdb.update(self.json())

    def get_stats(self,
                  keys_to_import = ['pdmv_dataset_name','pdmv_dataset_list','pdmv_status_in_DAS','pdmv_status_from_reqmngr'],
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
        for rwma_i in range(len(mcm_rr)):
            rwma = mcm_rr[rwma_i]
            if not statsDB.document_exists( rwma['name'] ):
                self.logger.error('the request %s is linked in McM already, but is not in stats DB'%(rwma['name']))
                ## very likely, this request was aborted, rejected, or failed
                ## should we be removing it ?
                continue
            stats_r = statsDB.get( rwma['name'] )
            mcm_content=transfer( stats_r , keys_to_import )
            mcm_rr[rwma_i]['content'] = mcm_content

        ####
        ## look for new ones
        look_for_what = self.get_attribute('prepid')
        if override_id:
            look_for_what = override_id
        stats_rr = map(lambda x: x['value'], statsDB.query(query='prepid==%s'%(look_for_what) ,page_num=-1))
        #self.logger.error('found %s'%(stats_rr))
        one_new=False
        for stats_r in stats_rr:
            ## only add it if not present yet
            if not stats_r['pdmv_request_name'] in map(lambda d : d['name'], mcm_rr):
                mcm_content=transfer( stats_r , keys_to_import)
                mcm_rr.append( { 'content' : mcm_content,
                                 'name' : stats_r['pdmv_request_name']})
                one_new=True

        #if one_new:
            # order those requests properly
            ### FIXME
            #then set it back if at least one new    
        self.set_attribute('reqmgr_name', mcm_rr)

    def inspect(self):
        ### this will look for corresponding wm requests, add them, check on the last one in date and check the status of the output DS for ->done
        not_good = {"prepid": self.get_attribute('prepid'), "results":False}
        # only if you are in submitted
        if self.get_attribute('status') != 'submitted':
            not_good.update( {'message' : 'cannot inspect a request in %s status'%(self.get_attribute('status'))} )
            return not_good

        ## get fresh up to date stats
        self.get_stats()
        mcm_rr = self.get_attribute('reqmgr_name')
        if len(mcm_rr):
            if ('pdmv_status_in_DAS' in mcm_rr[-1]['content'] and 'pdmv_status_from_reqmngr' in mcm_rr[-1]['content']):
                if mcm_rr[-1]['content']['pdmv_status_in_DAS'] == 'VALID' and mcm_rr[-1]['content']['pdmv_status_from_reqmngr'] == 'announced':
                    self.set_status(with_notification=True)
                    db = database( 'requests')
                    saved = db.save( self.json() )
                    if saved:
                        return {"prepid": self.get_attribute('prepid'), "results":True}
                    else:
                        not_good.update( {'message' : "Set status to %s could not be saved in DB"%(self.get_attribute('status'))})
                        return not_good
                else:
                    not_good.update( {'message' : "last request %s is not ready"%(mcm_rr[-1]['name'])})
                    return not_good
            else:
                not_good.update( {'message' : "last request %s is malformed %s"%(mcm_rr[-1]['name'],
                                                                                 mcm_rr[-1]['content'])})
                return not_good
        else:
            ## add a reset acion here, in case in prod instance ?
            not_good.update( {'message' : " there are no requests in request manager. Please invsetigate!"})
            return not_good

