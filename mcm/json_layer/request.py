#!/usr/bin/env python

import os
import re
import pprint
import xml.dom.minidom
from math import sqrt
import hashlib

from couchdb_layer.mcm_database import database

from json_layer.json_base import json_base
from json_layer.campaign import campaign
from json_layer.flow import flow
from json_layer.generator_parameters import generator_parameters
from json_layer.sequence import sequence
from tools import ssh_executor
from tools.locator import locator
from tools.batch_control import batch_control
from tools.settings import settings
from tools.locker import locker

class request(json_base):
    class DuplicateApprovalStep(Exception):
        def __init__(self,  approval=None):
            self.__approval = repr(approval)
            request.logger.error('Duplicate Approval Step: Request has already been %s approved' % (self.__approval))
        def __str__(self):
            return 'Duplicate Approval Step: Request has already been \'' + self.__approval + '\' approved'

    def __init__(self, json_input=None):

        # detect approval steps
        if not json_input: json_input = {}
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
            'priority':20000,
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
            'completed_events':-1,
            'total_events':-1,
            'member_of_chain':[],
            'member_of_campaign':'',
            'flown_with':'',
            'time_event':float(-1),
            'size_event':-1,
            'memory' : 2300, ## the default until now
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
            'tags': []
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
        ## prevent anything to happen during validation procedure.
        if self.get_attribute('status')=='new' and self.get_attribute('approval') == 'validation':
            for key in self._json_base__schema:
                editable[key]=False
            return editable

        if self.get_attribute('status')!='new': ## after being new, very limited can be done on it
            for key in self._json_base__schema:
                editable[key]=False
            if self.current_user_level!=0: ## not a simple user
                for key in ['generator_parameters','notes','history','generators','tags']:
                    editable[key]=True
            if self.current_user_level>3: ## only for admins
                for key in self._json_base__schema:#make it fully opened for admins ['completed_events','reqmgr_name','member_of_chain']:
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

        bad_characters=[' ','?','/']
        if not self.get_attribute('dataset_name') or any(map(lambda char : char in self.get_attribute('dataset_name'), bad_characters)):
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The dataset name is invalid: either null string or containing %s'%(','.join(bad_characters)))

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
            if re.match('^[\w/.-]+$', self.get_attribute('name_of_fragment')) is None:
                raise self.WrongApprovalSequence(self.get_attribute('status'),'validation', 'The configuration fragment {0} name contains illegal characters'.format(self.get_attribute('name_of_fragment')))
            for line in self.parse_fragment():
                if 'This is not the web page you are looking for' in line:
                    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The configuration fragment does not exist in git')
                if 'Exception Has Occurred' in line:
                    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The configuration fragment does not exist in cvs')

        if self.get_attribute('total_events') < 0:
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The number of requested event is invalid: Negative')

        if self.get_wmagent_type()=='LHEStepZero':
            if self.get_attribute('mcdb_id') == 0:
                nevents_per_job = self.numberOfEventsPerJob()
                if not nevents_per_job:
                    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The number of events per job cannot be retrieved for lhe production')
                elif nevents_per_job == self.get_attribute('total_events'):
                    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The number of events per job is equal to the number of events requested')
            if self.get_attribute('mcdb_id')<0:
                raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The request should have a positive of null mcdb id')

        cdb = database('campaigns')
        mcm_c = cdb.get( self.get_attribute('member_of_campaign') )
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
                    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','Two requests with the same dataset name, same process string and they are the same extension mumber (%s)'%( my_extension))
        # check whether there are similar requests (same mcdb_id, campaign and number of events) if the campaign is a root campaign
        #if mcm_c['root'] == 0 and self.get_attribute('mcdb_id') > 0:
        #    rdb.raw_query('mcdb_check', {'key': [mcm_c['prepid'], self.get_attribute('mcdb_id'), self.get_attribute('total_events')], 'group': True})

        ##this below needs fixing
        if not len(self.get_attribute('member_of_chain')):
            #not part of any chains ...
            if self.get_attribute('mcdb_id')>=0 and not self.get_attribute('input_filename'):
                if mcm_c['root'] in [-1,1]:
                    ##only requests belonging to a root==0 campaign can have mcdbid without input before being in a chain
                    raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The request has an mcdbid, not input dataset, and not member of a root campaign.')
            if self.get_attribute('mcdb_id')>0 and self.get_attribute('input_filename') and self.get_attribute('history')[0]['action'] != 'migrated':
                ## not a migrated request, mcdb
                raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The request has an mcdbid, an input dataset, not part of a chain, and not a result of a migration.')

        else:
            crdb = database('chained_requests')
            for cr in self.get_attribute('member_of_chain'):
                mcm_cr = crdb.get(cr)
                if mcm_cr['chain'].index( self.get_attribute('prepid') ) !=0:
                    if self.get_attribute('mcdb_id')>=0 and not self.get_attribute('input_filename'):
                        raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The request has an mcdbid, not input dataset, and not considered to be a request at the root of its chains.')


        ## check on chagnes in the sequences
        if len(self.get_attribute('sequences')) != len(mcm_c['sequences']):
            raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The request has a different number of steps than the campaigns it belong to')


        def in_there( seq1, seq2):
            items_that_do_not_matter=['conditions','datatier','eventcontent']
            for (name,item) in seq1.json().items():
                if name in items_that_do_not_matter:
                    #there are parameters which do not require specific processing string to be provided
                    continue
                if name in seq2.json():
                    if item!=seq2.json()[name]:
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
            self_sequence = sequence(self.get_attribute('sequences')[i_seq])
            this_matching=set([])
            for (label,seq_j) in seqs.items():
                seq = sequence( seq_j )
                # label = default , seq = dict
                if in_there( seq, self_sequence ) and in_there( self_sequence, seq ):
                    ## identical sequences
                    self.logger.log('identical sequences %s'% label)
                    this_matching.add(label)
                else:
                    self.logger.log('different sequences %s \n %s \n %s'%(label, seq.json(), self_sequence.json()))
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
        else:
            if self.get_attribute('process_string'):
                raise self.WrongApprovalSequence(self.get_attribute('status'),'validation','The sequences is the same as one of the campaign, but a process string %s has been provided'%( self.get_attribute('process_string')))


        ## select to synchronize status and approval toggling, or run the validation/run test
        de_synchronized=True
        if de_synchronized:
            from tools.handlers import RuntestGenvalid
            threaded_test = RuntestGenvalid( rid=str(self.get_attribute('prepid')))
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

        #if not self.is_action_root():
        if not len(self.get_attribute('member_of_chain')):
            raise self.WrongApprovalSequence(self.get_attribute('status'),'submit','This request is not part of any chain yet')

        at_least_an_action = self.has_at_least_an_action()
        if not at_least_an_action:
            raise self.WrongApprovalSequence(self.get_attribute('status'),'submit','This request does not spawn from any valid action')

        if self.get_attribute('size_event')<=0 or self.get_attribute('time_event')<=0:
            raise self.WrongApprovalSequence(self.get_attribute('status'),'submit','The time (%s) or size per event (%s) is inappropriate'%( self.get_attribute('time_event'), self.get_attribute('size_event')))

        sync_submission=True
        if sync_submission:
            # remains to the production manager to announce the batch the requests are part of
            from tools.handlers import RequestInjector
            threaded_submission = RequestInjector(prepid=self.get_attribute('prepid'), check_approval=False, lock=locker.lock(self.get_attribute('prepid')))
            threaded_submission.start()
        else:
            #### not settting any status forward
            ## the production manager would go and submit those by hand via McM : the status is set automatically upon proper injection
            pass

    def is_action_root(self):
        action_db = database('actions')
        if action_db.document_exists(self.get_attribute('prepid')):
            return True
        return False

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
                    if content['flag']:
                        at_least_an_action=True
                        break

        return at_least_an_action


    def retrieve_fragment(self,name=None,get=True):
        if not name:
            name=self.get_attribute('name_of_fragment')
        get_me=''
        tag=self.get_attribute('fragment_tag')
        fragment_retry_amount = 2
        if not tag:
            tag = self.get_attribute('cvs_tag')
        if tag and name:
            # remove this to allow back-ward compatibility of fragments/requests placed with PREP
            name=name.replace('Configuration/GenProduction/python/','')
            name=name.replace('Configuration/GenProduction/','')
            # curl from git hub which has all history tags
            get_me='curl -s https://raw.github.com/cms-sw/genproductions/%s/python/%s --retry %s '%( self.get_attribute('fragment_tag'), name, fragment_retry_amount )
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
        if fragment and not fragment.startswith('Configuration/GenProduction/python/'):
            fragment='Configuration/GenProduction/python/'+fragment
        return fragment

    def build_cmsDriver(self, sequenceindex):

      fragment=self.get_fragment()

      ##JR
      if fragment=='':
          fragment='step%d'%(sequenceindex+1)
      command = 'cmsDriver.py %s ' % fragment

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
              #command +=' --filein "dbs:%s" '%(self.get_attribute('input_filename'))
              command +='--dbsquery "find file where dataset=%s" '%(self.get_attribute('input_filename'))
          else:
              command+='--filein file:step%d.root '%(sequenceindex)

      elif self.get_attribute('mcdb_id')>0:
          command +='--filein lhe:%d '%(self.get_attribute('mcdb_id'))

      if sequenceindex == len(self.get_attribute('sequences'))-1:
          ## last one
          command +='--fileout file:%s.root '%(self.get_attribute('prepid'))
      else:
          command +='--fileout file:step%d.root '%(sequenceindex+1)


      ##JR
      if self.get_attribute('pileup_dataset_name') and not (seq.get_attribute('pileup') in ['','NoPileUp']):
          command +='--pileup_input "dbs:%s" '%(self.get_attribute('pileup_dataset_name'))

      return '%s%s' % (command, cmsDriverOptions)

    def build_cmsDrivers(self,cast=0, can_save=True):
      commands = []
      if cast==1 and self.get_attribute('status')=='new':
          cdb = database('campaigns')

          flownWith=None
          if self.get_attribute('flown_with'):
              fdb = database('flows')
              flownWith = flow(fdb.get(self.get_attribute('flown_with')))

          camp = campaign(cdb.get(self.get_attribute('member_of_campaign')))
          self.set_attribute('cmssw_release',camp.get_attribute('cmssw_release'))
          self.set_attribute('pileup_dataset_name',camp.get_attribute('pileup_dataset_name'))
          self.set_attribute('type',camp.get_attribute('type'))
          ## putting things together from the campaign+flow
          freshSeq=[]
          if flownWith:
              #self.logger.error('Using a flow: %s and a campaign %s , to recast %s'%(flownWith['prepid'],
              #                                                                       camp.get_attribute('prepid'),
              #                                                                       new_req['prepid']))
              request.put_together(camp, flownWith, self)
          else:
              for i in range(len(camp.get_attribute('sequences'))):
                      fresh = sequence(camp.get_attribute('sequences')[i]["default"])
                      freshSeq.append(fresh.json())
              self.set_attribute('sequences',freshSeq)
          if can_save:
              self.reload()
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
        makeRel = 'source  /afs/cern.ch/cms/cmsset_default.sh\n'
        makeRel += 'export SCRAM_ARCH=%s\n'%(self.get_scram_arch())
        makeRel += 'if [ -r %s ] ; then \n'%(self.get_attribute('cmssw_release'))
        makeRel += ' echo release %s already exists\n'%(self.get_attribute('cmssw_release'))
        makeRel += 'else\n'
        makeRel += 'scram p CMSSW ' + self.get_attribute('cmssw_release') + '\n'
        makeRel += 'fi\n'
        makeRel += 'cd ' + self.get_attribute('cmssw_release') + '/src\n'
        makeRel += 'eval `scram runtime -sh`\n' ## setup the cmssw
        return makeRel

    def get_setup_file(self,directory='',events=None, run=False, do_valid=False):
        #run is for adding cmsRun
        #do_valid id for adding the file upload

        l_type = locator()
        infile = ''
        infile += '#!/bin/bash\n'
        if directory:
            ## go into the request directory itself to setup the release, since we cannot submit more than one at a time ...
            infile += 'cd ' + os.path.abspath(directory + '../') + '\n'


        ##create a release directory "at the root" if not already existing

        if directory:
            ##create a release directory "in the request" directory if not already existing
            infile += 'cd ' + os.path.abspath(directory) + '\n'
            infile += self.make_release()
        else:
            infile += self.make_release()

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
        if events is None:
            events = self.get_n_for_test( self.target_for_test() )


        for cmsd in self.build_cmsDrivers():

            # check if customization is needed to check it out from cvs
            if '--customise ' in cmsd:
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
            configuration_names.append( directory+self.get_attribute('prepid')+"_"+str(previous+1)+'_cfg.py')
            res += ' --python_filename %s --no_exec '%( configuration_names[-1] )

            ## add monitoring at all times...
            if '--customise ' in cmsd:
                old_cust = cmsd.split('--customise ')[1].split()[0]
                new_cust=old_cust
                new_cust+=',Configuration/DataProcessing/Utils.addMonitoring '
                res=res.replace('--customise %s'%(old_cust),'--customise %s'%(new_cust))
                #res +='--customise %s'%( cust )
            else:
                res += '--customise Configuration/DataProcessing/Utils.addMonitoring '


            res += '-n '+str(events)+ ' || exit $? ; \n'
            if run:
                res += 'cmsRun -e -j %s%s_rt.xml %s || exit $? ; \n'%( directory, self.get_attribute('prepid'), configuration_names[-1] )
                res += 'grep "TotalEvents" %s%s_rt.xml \n'%(directory, self.get_attribute('prepid'))
                res += 'grep "Timing-tstoragefile-write-totalMegabytes" %s%s_rt.xml \n'%(directory, self.get_attribute('prepid'))
                res += 'grep "PeakValueRss" %s%s_rt.xml \n'%(directory, self.get_attribute('prepid'))
                res += 'grep "AvgEventTime" %s%s_rt.xml \n'%(directory, self.get_attribute('prepid'))
                

            #try create a flash runtest
            if 'lhe:' in cmsd and run and self.get_attribute('mcdb_id')>0:
                affordable_nevents = 2000000 #at a time
                max_tests=1
                skip_some=''
                test_i=0
                while affordable_nevents*test_i < self.get_attribute('total_events') and test_i < max_tests:
                    res += 'cmsDriver.py lhetest --filein lhe:%s --mc  --conditions auto:startup -n %s --python lhetest_%s.py --step NONE --no_exec --no_output %s\n'%( self.get_attribute('mcdb_id'), affordable_nevents, test_i ,skip_some)
                    res += 'cmsRun lhetest_%s.py & \n'%( test_i )
                    #prepare for next test job
                    test_i+=1
                    skip_some="--customise_command 'process.source.skipEvents=cms.untracked.uint32(%d)'" % ( affordable_nevents*test_i )
                """
                res += 'cmsDriver.py lhetest --filein lhe:%s --mc --conditions auto:startup -n -1 --python lhetest_%s.py --step NONE --no_exec --no_output \n'%( self.get_attribute('mcdb_id'))
                res += 'cmsRun lhetest.py || exit $? ; \n'
                """
                wait_for_me='''\

for job in `jobs -p` ; do
    wait $job || exit $? ;
done
            '''
                res+= wait_for_me
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

        if run and do_valid and self.genvalid_driver:
            infile += self.harverting_upload

        infile += 'cd ../../\n'
        ## if there was a release setup, jsut remove it
        #not in dev
        if directory and not l_type.isDev():
            infile += 'rm -rf %s' %( self.get_attribute('cmssw_release') )


        return infile

    def change_priority(self, new_priority):
        if self.get_attribute('status') in ['done']:
            return True
        if self.get_attribute('priority') >= new_priority:
            return True
        if not isinstance(new_priority, int):
            self.logger.error('Priority has to be an integer')
            return False
        with locker.lock(self.get_attribute('prepid')):
            loc = locator()
            reqmgr_names = [reqmgr['name'] for reqmgr in self.get_attribute('reqmgr_name')]
            if len(reqmgr_names):
                ssh_exec = ssh_executor.ssh_executor(server='pdmvserv-test.cern.ch')
                cmd = 'export X509_USER_PROXY=/afs/cern.ch/user/p/pdmvserv/private/$HOST/voms_proxy.cert\n'
                cmd += 'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh\n'
                cmd += 'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n'
                test = ""
                if loc.isDev():
                    test = '-u cmsweb-testbed.cern.ch'
                for req_name in reqmgr_names:
                    cmd += 'wmpriority.py {0} {1} {2}\n'.format(req_name, new_priority, test)
                _, stdout, stderr = ssh_exec.execute(cmd)
                self.logger.log(cmd)
                if not stdout and not stderr:
                    self.logger.error('SSH error while changing priority of {0}'.format(self.get_attribute('prepid')))
                    return False
                output_text = stdout.read()
                self.logger.log('wmpriority output:\n{0}'.format(output_text))
                not_found=False
                for line in output_text.split("\n"):
                    if 'Unable to change priority of workflow' in line:
                        self.logger.error("Request {0}. {1}".format(self.get_attribute('prepid'), line))
                        not_found = True
                if not_found:
                    return False
            self.set_attribute('priority', new_priority)
            saved = self.reload()
            if not saved:
                self.logger.error('Could not save request {0} with new priority'.format(self.get_attribute('prepid')))
                return False
            self.logger.log('Priority of request {0} was changed to {1}'.format(self.get_attribute('prepid'), new_priority))
            return True




    def get_genvalid_setup(self,directory,run):
        cmsd_list =""
        infile =""

        ############################################################################
        #### HERE starts a big chunk that should be moved somewhere else than here
        ## gen valid configs
        self.genvalid_driver = None
        valid_sequence = None
        val_attributes = self.get_attribute('validation')
        n_to_valid = self.get_n_for_valid()
        yes_to_valid=False
        if n_to_valid:
            yes_to_valid=True

        if 'valid' in val_attributes:
            yes_to_valid=val_attributes['valid']
        else:
            yes_to_valid=False

        ##get the campaign enalbing/disabling
        #cdb = database('campaigns', cache=True)
        #mcm_c = cdb.get( self.get_attribute('member_of_campaign'))
        #c_val_attributes = mcm_c['validation']
        ### then do something with that object, once it will be an object

        l_type=locator()
        #if self.little_release() < '530':# or (not l_type.isDev()):
        #    yes_to_valid= False

        if not yes_to_valid:
            return ("","")

        # to be refined using the information of the campaign
        firstSequence = self.get_attribute('sequences')[0]
        firstStep = firstSequence['step'][0]

        dump_python=''
        genvalid_request = request( self.json() )

        if firstStep == 'GEN':
            gen_valid = settings().get_value('gen_valid')
            if not gen_valid:
                return ("","")

            cmsd_list += '\n\n'
            valid_sequence = sequence( firstSequence )
            valid_sequence.set_attribute( 'step', ['GEN','VALIDATION:genvalid_all'])
            valid_sequence.set_attribute( 'eventcontent' , ['DQM'])
            valid_sequence.set_attribute( 'datatier' , ['DQM'])
            ## forfeit customisation until they are made fail-safe
            valid_sequence.set_attribute( 'customise' , '')

        elif firstStep in ['LHE','NONE']:
            cmsd_list += '\n\n'
            valid_sequence = sequence( firstSequence )
            ## when integrated properly
            if firstStep=='LHE':
                wlhe_valid = settings().get_value('wlhe_valid')
                if not wlhe_valid:
                    return ("","")
                valid_sequence.set_attribute( 'step', [firstStep,'USER:GeneratorInterface/LHEInterface/wlhe2HepMCConverter_cff.generator','GEN','VALIDATION:genvalid_all'])
            else:
                lhe_valid = settings().get_value('lhe_valid')
                if not lhe_valid:
                    return ("","")
                #genvalid_request.set_attribute('name_of_fragment', 'GeneratorInterface/LHEInterface/lhe2HepMCConverter_cff')
                #valid_sequence.set_attribute( 'step', ['GEN','VALIDATION:genvalid_all'])
                valid_sequence.set_attribute( 'step', ['USER:GeneratorInterface/LHEInterface/lhe2HepMCConverter_cff.generator','GEN','VALIDATION:genvalid_all'])
            valid_sequence.set_attribute( 'eventcontent' , ['DQM'])
            valid_sequence.set_attribute( 'datatier' , ['DQM'])
            dump_python= '--dump_python' ### only there until it gets fully integrated in all releases
        if valid_sequence:
            self.setup_harvesting(directory,run)

            ## until we have full integration in the release
            genvalig_config = settings().get_value('genvalid_config')
            cmsd_list += genvalig_config
            #cmsd_list +='addpkg GeneratorInterface/LHEInterface 2> /dev/null \n'
            #cmsd_list +='curl -s http://cmssw.cvs.cern.ch/cgi-bin/cmssw.cgi/CMSSW/GeneratorInterface/LHEInterface/python/lhe2HepMCConverter_cff.py?revision=HEAD -o GeneratorInterface/LHEInterface/python/lhe2HepMCConverter_cff.py \n'
            #cmsd_list +='\nscram b -j5 \n'


            genvalid_request.set_attribute( 'sequences' , [valid_sequence.json()])

            self.genvalid_driver = '%s --fileout file:genvalid.root --mc -n %d --python_filename %sgenvalid.py %s --no_exec || exit $? ;\n'%(genvalid_request.build_cmsDriver(0),
                                                                                                                                 int(n_to_valid),
                                                                                                                                 directory,
                                                                                                                                 dump_python)
            if run:
                self.genvalid_driver += 'cmsRun -e -j %s%s_gv.xml %sgenvalid.py || exit $? ; \n'%( directory, self.get_attribute('prepid'),
                                                                                               directory)
                self.genvalid_driver += 'grep "TotalEvents" %s%s_gv.xml \n'%(directory, self.get_attribute('prepid'))
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
        self.harvesting_driver = 'cmsDriver.py step2 --filein file:genvalid.root --conditions auto:startup --mc -s HARVESTING:genHarvesting --harvesting AtJobEnd --python_filename %sgenvalid_harvesting.py --no_exec || exit $? ; \n'%(directory)
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


    def get_actors(self,N=-1,what='author_username',Nchild=-1):
        #get the actors from itself, and all others it is related to
        actors=json_base.get_actors(self,N,what)
        crdb=database('chained_requests')
        lookedat=[]
        ## initiate the list with myself
        if Nchild==0:
            return actors

        for cr in self.get_attribute('member_of_chain'):
            ## this protection is bad against malformed db content. it should just fail badly with exception
            if not crdb.document_exists(cr):
                self.logger.error('For requests %s, the chain %s of which it is a member of does not exist.'%( self.get_attribute('prepid'), cr))
                continue
            crr = crdb.get(cr)
            for (other_i,other) in enumerate(crr['chain']):
                ## skip myself
                if other == self.get_attribute('prepid'): continue
                if other in lookedat: continue
                if Nchild>0 and other_i>Nchild: break
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

    def get_stats(self, keys_to_import=None, override_id=None, limit_to_set=0.05):
        #existing rwma
        if not keys_to_import: keys_to_import = ['pdmv_dataset_name', 'pdmv_dataset_list', 'pdmv_status_in_DAS',
                                                 'pdmv_status_from_reqmngr', 'pdmv_evts_in_DAS',
                                                 'pdmv_open_evts_in_DAS', 'pdmv_submission_date',
                                                 'pdmv_submission_time','pdmv_type']
        mcm_rr=self.get_attribute('reqmgr_name')
        statsDB = database('stats',url='http://cms-pdmv-stats.cern.ch:5984/')

        changes_happen=False

        ## make a connection check to stats ! Get the views
        if not statsDB.document_exists('_design/stats'):
            self.logger.error('Connection to stats DB is down. Cannot get updated statistics')
            return False

        def transfer( stats_r , keys_to_import):
            mcm_content={}
            if not len(keys_to_import):
                keys_to_import = stats_r.keys()
            for k in keys_to_import:
                if k in stats_r:
                    mcm_content[k] = stats_r[k]
            return mcm_content

        ####
        ## update all existing
        earliest_date=0
        earliest_time=0
        failed_to_find=[]
        for (rwma_i,rwma) in enumerate(mcm_rr):
            if not statsDB.document_exists( rwma['name'] ):
                self.logger.error('the request %s is linked in McM already, but is not in stats DB'%(rwma['name']))
                ## very likely, this request was aborted, rejected, or failed : connection check was done just above
                if rwma_i!=0:
                    ## always keep the original request
                    changes_happen=True
                    failed_to_find.append(rwma['name'])
                stats_r = rwma['content']
            else:
                stats_r = statsDB.get( rwma['name'] )

            if ('pdmv_submission_date' in stats_r and earliest_date==0) or ('pdmv_submission_date' in stats_r and int(earliest_date)> int(stats_r['pdmv_submission_date'])):
                earliest_date = stats_r['pdmv_submission_date'] #yymmdd
            if ('pdmv_submission_time' in stats_r and earliest_time==0) or ('pdmv_submission_time' in stats_r and int(earliest_time)> int(stats_r['pdmv_submission_time'])):
                earliest_time = stats_r['pdmv_submission_time']

            if not len(failed_to_find) or rwma['name']!=failed_to_find[-1]: ## no need to copy over if it has just been noticed that it is not taken from stats but the mcm document itself
                mcm_content=transfer( stats_r , keys_to_import )
                mcm_rr[rwma_i]['content'] = mcm_content

        ## take out the one which were not found !
        mcm_rr = filter( lambda wmr : not wmr['name'] in failed_to_find, mcm_rr)

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

        self.logger.error('got stats with date %s and time %s , %s existings and %s matching'%( earliest_date, earliest_time, len(mcm_rr), len(stats_rr) ))

        #self.logger.error('found %s'%(stats_rr))

        for stats_r in stats_rr:
            ## only add it if not present yet
            if stats_r['pdmv_request_name'] in map(lambda d : d['name'], mcm_rr):
                continue

            ## we should not be blindly adding anything, if we could not determine the time of the submission.
            #if not earliest_date:
            #    continue

            ## only add if the date is later than the earliest_date
            if not 'pdmv_submission_date' in stats_r:
                continue
            if stats_r['pdmv_submission_date'] and int(stats_r['pdmv_submission_date']) < int(earliest_date):
                continue
            if stats_r['pdmv_submission_date'] and int(stats_r['pdmv_submission_date']) == int(earliest_date):
                if earliest_time and 'pdmv_submission_time' in stats_r and stats_r['pdmv_submission_time'] and int(stats_r['pdmv_submission_time']) < int(earliest_time):
                    continue

            mcm_content=transfer( stats_r , keys_to_import)
            mcm_rr.append( { 'content' : mcm_content,
                             'name' : stats_r['pdmv_request_name']})
            changes_happen=True

        if len(mcm_rr):
            try:
                completed= mcm_rr[-1]['content']['pdmv_evts_in_DAS'] + mcm_rr[-1]['content']['pdmv_open_evts_in_DAS']
            except:
                self.logger.error('Could not calculate completed from last request')
                completed=0
            # above how much change do we update : 5%
            #self.logger.error('completed %s and there already %s' %( completed, self.get_attribute('completed_events')))
            if float(completed) > float( (1+limit_to_set) * self.get_attribute('completed_events')):
                changes_happen=True
            self.set_attribute('completed_events', completed)

        self.set_attribute('reqmgr_name', mcm_rr)
        return changes_happen

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
        db = database( 'requests')
        if self.get_attribute('approval') == 'approve':
            try:
                with locker.lock('{0}-wait-for-approval'.format( self.get_attribute('prepid'))):
                    self.approve()
                    saved = db.save( self.json() )
                if saved:
                    return {"prepid": self.get_attribute('prepid'), "results":True}
                else:
                    not_good.update( {'message' : "Could not save the request after approve "} )
                    return not_good
            except Exception as ex:
                not_good.update( {'message' : str(ex)})
                return not_good

        elif self.get_attribute('approval') == 'submit':
            from tools.handlers import RequestInjector
            threaded_submission = RequestInjector(prepid=self.get_attribute('prepid'), check_approval=False, lock=locker.lock(self.get_attribute('prepid')))
            threaded_submission.start()
            return {"prepid": self.get_attribute('prepid'), "results":True}
        else:
            not_good.update( {'message' : 'Not implemented yet to inspect a request in %s status and approval %s'%(self.get_attribute('status'), self.get_attribute('approval'))} )
            return not_good

    def inspect_submitted(self):
        not_good = {"prepid": self.get_attribute('prepid'), "results":False}
        ## get fresh up to date stats
        changes_happen = self.get_stats()
        mcm_rr = self.get_attribute('reqmgr_name')
        db = database( 'requests')
        if len(mcm_rr):
            wma_r = mcm_rr[-1] 
            ## pick up the last request of type!='Resubmission'
            #for wma in  mcm_rr :
            #    if 'pdmv_type' in wma and wma['pdmv_type']!='Resubmission':
            #        wma_r = wma

            wma_r_N = mcm_rr[-1] # so that we can decouple the two
            if ('pdmv_status_in_DAS' in wma_r['content'] and 'pdmv_status_from_reqmngr' in wma_r['content']):
                if wma_r['content']['pdmv_status_in_DAS'] == 'VALID' and wma_r['content']['pdmv_status_from_reqmngr'] in ['announced','normal-archived']:
                    ## how many events got completed for real: summing open and closed


                    self.set_attribute('completed_events' , wma_r_N['content']['pdmv_evts_in_DAS'] + wma_r_N['content']['pdmv_open_evts_in_DAS'] )

                    if self.get_attribute('completed_events') <=0:
                        not_good.update( {'message' : '%s completed but with no statistics. stats DB lag. saving the request anyway.'%( wma_r['content']['pdmv_dataset_name'])})
                        saved = db.save( self.json() )
                        return not_good
                    tier_produced=wma_r['content']['pdmv_dataset_name'].split('/')[-1]
                    if not tier_produced in self.get_attribute('sequences')[-1]['datatier']:
                        not_good.update( {'message' : '%s completed but tier does no match any of %s'%( wma_r['content']['pdmv_dataset_name'], self.get_attribute('sequences')[-1]['datatier'])} )
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
                    if changes_happen: db.save( self.json() )
                    not_good.update( {'message' : "last request %s is not ready"%(wma_r['name'])})
                    return not_good
            else:
                if changes_happen: db.save( self.json() )
                not_good.update( {'message' : "last request %s is malformed %s"%(wma_r['name'],
                                                                                 wma_r['content'])})
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

    def target_for_test(self):
        #could reverse engineer the target 
        return settings().get_value('test_target')

    def get_n_unfold_efficiency(self, target):
        if self.get_attribute('generator_parameters'):
            ## get the last entry of generator parameters
            match = float(self.get_attribute('generator_parameters')[-1]['match_efficiency'])
            filter_eff = float(self.get_attribute('generator_parameters')[-1]['filter_efficiency'])
            if match > 0 and filter_eff > 0:
                target /=  (match*filter_eff)
        return target

    def get_n_for_valid(self):
        n_to_valid = settings().get_value('min_n_to_valid')
        val_attributes = self.get_attribute('validation')
        if 'nEvents' in val_attributes:
            if val_attributes['nEvents'] > n_to_valid:
                n_to_valid=val_attributes['nEvents']

        return self.get_n_unfold_efficiency(n_to_valid)

    def get_n_for_test(self, target=1.0):
        #=> correct for the matching and filter efficiencies
        events = self.get_n_unfold_efficiency(target)

        #=> estimate how long it will take
        total_test_time = float(self.get_attribute('time_event')) * events
        fraction = settings().get_value('test_timeout_fraction')
        timeout = settings().get_value('batch_timeout') * 60. * fraction # in seconds
        # check that it is not going to time-out
        ### either the batch test time-out is set accordingly, or we limit the events
        self.logger.log('running %s means running for %s s, and timeout is %s' %( events, total_test_time, timeout))
        if total_test_time > timeout:
            #reduce the n events for test to fit in 75% of the timeout
            if self.get_attribute('time_event'):
                events = timeout / float(self.get_attribute('time_event'))
                self.logger.log('N for test was lowered to %s to not exceed %s * %s min time-out'%( events, fraction , settings().get_value('batch_timeout') ))
            else:
                self.logger.error('time per event is set to 0 !')

        if events>=1:
            return int(events)
        else:
            ##default to 0
            return int(0)

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
        if self.get_attribute('mcdb_id')>=0 and self.get_attribute('type') in ['LHE','LHEStepZero']:
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
        total_event_in = self.get_n_for_test( self.target_for_test() )
        total_event_in_valid = self.get_n_for_valid()

        xml_data = xml.dom.minidom.parseString( xml_doc )

        if not len(xml_data.documentElement.getElementsByTagName("TotalEvents")):
            self.logger.error("There are no TotalEvents reported, bailing out from performnace test")
            return

        total_event= float(xml_data.documentElement.getElementsByTagName("TotalEvents")[-1].lastChild.data)
        if what=='eff':
            if total_event==0 and total_event_in_valid!=0:
                self.logger.error("For %s the total number of events in output of the %s test %s is 0. ran %s"%( self.get_attribute('prepid'), what , total_event_in_valid))
                raise Exception("The test should have ran %s events in input, and produced 0 events: there is certainly something wrong with the request"%( total_event_in_valid ))
        else:    
            if total_event==0 and total_event_in!=0:
                ##fail it !
                self.logger.error("For %s the total number of events in output of the %s test %s is 0. ran %s"%( self.get_attribute('prepid'), what , total_event_in))
                raise Exception("The test should have ran %s events in input, and produced 0 events: there is certainly something wrong with the request"%( total_event_in ))

        memory = None
        timing = None
        file_size = None
        for item in xml_data.documentElement.getElementsByTagName("PerformanceReport"):
            for summary in item.getElementsByTagName("PerformanceSummary"):
                for perf in summary.getElementsByTagName("Metric"):
                    name=perf.getAttribute('Name')
                    if name == 'AvgEventTime':
                        timing = float( perf.getAttribute('Value'))
                    if name == 'Timing-tstoragefile-write-totalMegabytes':
                        file_size = float( perf.getAttribute('Value')) * 1024. # MegaBytes -> kBytes
                    if name == 'PeakValueRss':
                        memory = float( perf.getAttribute('Value'))

        if file_size:
            file_size = int(  file_size / total_event)

        efficiency = total_event / total_event_in_valid
        efficiency_error = efficiency * sqrt( 1./total_event + 1./total_event_in_valid )

        geninfo=None
        if len(self.get_attribute('generator_parameters')):
            geninfo = self.get_attribute('generator_parameters')[-1]

        to_be_saved= False

        to_be_changed='filter_efficiency'
        if self.get_attribute('input_filename'):
            to_be_changed='match_efficiency'

        self.logger.error("Calculated all eff: %s eff_err: %s timing: %s size: %s" % ( efficiency, efficiency_error, timing, file_size ))

        if what =='eff':
            do_update=False
            if not geninfo:
                do_update=True
            if geninfo and geninfo[to_be_changed] and efficiency:
                if (geninfo[to_be_changed+'_error'] / geninfo[to_be_changed] ) > (efficiency_error/ efficiency):
                    do_update=True
                if (efficiency!=1 and geninfo[to_be_changed]==1) or (efficiency==1 and  geninfo[to_be_changed]!=1):
                    raise Exception('For this request, %s=%s was given, %s was measured from %s events (ran %s). It is not possible to process the request.'%( to_be_changed, geninfo[to_be_changed], efficiency, total_event, total_event_in_valid))

            if do_update:
                ## we have a better error on the efficiency: combine or replace: replace for now
                self.update_generator_parameters()
                added_geninfo = self.get_attribute('generator_parameters')[-1]
                added_geninfo[to_be_changed] = efficiency
                added_geninfo[to_be_changed+'_error'] = efficiency_error
                to_be_saved=True
            if geninfo:
                if efficiency==0.:
                    ## that is a very bad thing !
                    self.notify('Runtest for %s: %s seems very wrong.'%( self.get_attribute('prepid'), to_be_changed),
                                'For this request, %s=%s was given, %s was measured from %s events (ran %s). Please check and reset the request if necessary.'%( to_be_changed, geninfo[to_be_changed], efficiency, total_event, total_event_in_valid))
                    #raise Exception('For this request, %s=%s was given, %s was measured from %s events (ran %s). It is not possible to process the request'%( to_be_changed, geninfo[to_be_changed], efficiency, total_event, total_event_in_valid))
                elif abs(geninfo[to_be_changed]-efficiency)/efficiency>0.05:
                    ## efficiency is wrong by more than 0.05
                    self.notify('Runtest for %s: %s seems incorrect.'%( self.get_attribute('prepid'), to_be_changed),
                                'For this request, %s=%s was given, %s was measured from %s events (ran %s). Please check and reset the request if necessary.'%( to_be_changed, geninfo[to_be_changed], efficiency, total_event, total_event_in_valid))


        elif what =='perf':
            ## timing checks
            if timing and timing>self.get_attribute('time_event'):
                ## timing under-estimated
                if timing *0.90 > self.get_attribute('time_event'):
                    ## notify if more than 10% discrepancy found !
                    self.notify('Runtest for %s: time per event under-estimate.'%(self.get_attribute('prepid')),
                                'For this request, time/event=%s was given, %s was measured and set to the request from %s events (ran %s).'%( self.get_attribute('time_event'), timing, total_event, total_event_in))
                self.set_attribute('time_event', timing)
                to_be_saved=True
            if timing and timing < (0.90 * self.get_attribute('time_event')):
                ## timing over-estimated
                ## warn if over-estimated by more than 10% : we should actually fail those big time !!
                self.notify('Runtest for %s: time per event over-estimate.'%(self.get_attribute('prepid')),
                            'For this request, time/event=%s was given, %s was measured from %s events (ran %s).'%( self.get_attribute('time_event'), timing, total_event, total_event_in))

            ## size check
            if file_size and file_size>self.get_attribute('size_event'):
                ## size under-estimated
                if file_size * 0.90 > self.get_attribute('size_event'):
                    ## notify if more than 10% discrepancy found !
                    self.notify('Runtest for %s: size per event under-estimate.'%(self.get_attribute('prepid')),
                                'For this request, size/event=%s was given, %s was measured from %s events (ran %s).'%( self.get_attribute('size_event'), file_size, total_event, total_event_in))
                self.set_attribute('size_event', file_size)                    
                to_be_saved=True
            if file_size and file_size< int( 0.90 * self.get_attribute('size_event')):
                ## size over-estimated
                ## warn if over-estimated by more than 10% 
                self.notify('Runtest for %s: size per event over-estimate.'%(self.get_attribute('prepid')),
                            'For this request, size/event=%s was given, %s was measured from %s events (ran %s).'%( self.get_attribute('size_event'), file_size, total_event, total_event_in))

            if memory and memory>self.get_attribute('memory'):
                safe_margin = 1.05
                memory *= safe_margin
                if memory > 4000:
                    self.logger.error("Request %s has a %s requirement of %s MB in memory exceeding 4GB."%(self.get_attribute('prepid'),safe_margin, memory))
                    self.notify('Runtest for %s: memory over-usage' %( self.get_attribute('prepid')),
                                'For this request, the memory usage is found to be large. Requiring %s MB measured from %s events (ran %s). Setting to high memory queue'%( memory, total_event, total_event_in ))
                    #truncate to 4G, or catch it in ->define step ?
                self.set_attribute('memory', memory)
                to_be_saved=True

        if to_be_saved:
            self.update_history({'action':'update','step':what})

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
                    sequences.append(step[name])

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
                sequences.append(step['default'])

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
            elif key =='process_string':
                ##concatenate to existing
                if new_req.get_attribute(key):
                    new_req.set_attribute(key, new_req.get_attribute(key)+'_'+fl.get_attribute('request_parameters')[key])
                else:
                    new_req.set_attribute(key, fl.get_attribute('request_parameters')[key])
            else:
                if key in new_req.json():
                    new_req.set_attribute(key, fl.get_attribute('request_parameters')[key])

    @staticmethod
    def transfer( current_request, next_request):
        to_be_transferred = ['pwg', 'dataset_name', 'generators', 'process_string', 'analysis_id', 'mcdb_id','notes','tags']
        for key in to_be_transferred:
            next_request.set_attribute(key, current_request.get_attribute(key))

    def reset(self):

        ## check on who's trying to do so
        if self.current_user_level == 1 and not self.get_attribute('status') in ['validation','defined', 'new']:
            raise json_base.WrongStatusSequence(self.get_attribute('status'), self.get_attribute('approval'), 'You have not enough karma to reset the request')

        if self.get_attribute('approval') == 'validation' and self.get_attribute('status')=='new':
            raise json_base.WrongStatusSequence(self.get_attribute('status'), self.get_attribute('approval'), 'Cannot reset a request when running validation')

        chains = self.get_attribute('member_of_chain')
        from json_layer.chained_request import chained_request
        crdb= database('chained_requests')
        for chain in chains:
            cr = chained_request( crdb.get(chain))
            if cr.get_attribute('chain').index( self.get_attribute('prepid')) < cr.get_attribute('step'):
                ## cannot reset a request that is part of a further on-going chain
                raise json_base.WrongStatusSequence(self.get_attribute('status'), self.get_attribute('approval'), 'The request is part of a chain (%s) that is currently processing another request (%s)' %( chain, cr.get_attribute('chain')[cr.get_attribute('step')]))
            


        self.approve(0)
        ## make sure to keep track of what needs to be invalidated in case there is
        invalidation = database('invalidations')
        req_to_invalidate=[]
        ds_to_invalidate=[]

        # retrieve the latest requests for it
        self.get_stats()
        # increase the revision only if there was a request in req mng, or a dataset already on the table
        increase_revision=False

        # and put them in invalidation
        for wma in self.get_attribute('reqmgr_name'):
            ## save the reqname to invalidate
            req_to_invalidate.append(wma['name'])
            new_invalidation={"object" : wma['name'], "type" : "request", "status" : "new" , "prepid" : self.get_attribute('prepid')}
            new_invalidation['_id'] = new_invalidation['object']
            invalidation.save( new_invalidation )

            ## save all dataset to be invalidated
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


        ##do not increase version if not in an announced batch
        bdb = database('batches')
        if increase_revision:
            for req in req_to_invalidate:
                # find the batch it is in
                bs = bdb.queries(['contains=%s'%( req)])
                for b in bs:
                    if not b['status'] in ['done','announced']:
                        increase_revision=False
                        ## we're done checking
                        break


        self.set_attribute('completed_events', 0)
        self.set_attribute('reqmgr_name',[])
        self.set_attribute('config_id',[])
        if increase_revision:
            self.set_attribute('version', self.get_attribute('version')+1)
        # remove the configs doc hash in reset
        hash_ids = database('configs')
        for i in range( len(self.get_attribute('sequences'))):
            hash_id = self.configuration_identifier(i)
            if hash_ids.document_exists( hash_id ):
                hash_ids.delete( hash_id )
        self.set_status(step=0,with_notification=True)



