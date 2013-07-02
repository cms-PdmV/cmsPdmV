from json_base import json_base
from json_layer.request import request
from flow import flow

from couchdb_layer.prep_database import database
import json
from tools.priority import priority

class chained_request(json_base):
    class CampaignAlreadyInChainException(Exception):
        def __init__(self,  campaign):
            self.c = campaign
            chained_request.logger.error('Campaign %s is already member of the chain.' % (self.c))

        def __str__(self):
            return 'Error: Campaign', self.c,  'already represented in the chain.'
    
    class ChainedRequestCannotFlowException(Exception):
        def __init__(self,  crname, message='cannot flow any further'):
            self.name = str(crname)
            self.message = message
            chained_request.logger.error('Chained request %s %s.' % (self.name, self.message))

        def __str__(self):
            return 'Chained request %s %s.' % (self.name, self.message)
    
    class NotApprovedException(Exception):
        def __init__(self,  oname,  alevel, allowed):
            self.name = str(oname)
            self.level = str(alevel)
            self.allowed = ' or '.join(map(lambda s : '"%s"'%s,allowed))
            chained_request.logger.error('%s has not been approved for any of %s levels : "%s"' % (self.name , self.allowed, self.level))

        def __str__(self):
            return 'Error: '+self.name+' is "'+self.level+'" approved. requires '+self.allowed

    class NotInProperStateException(Exception):
        def __init__(self,  oname,  alevel, allowed):
            self.name = str(oname)
            self.level = str(alevel)
            self.allowed = ' or '.join(map(lambda s : '"%s"'%s,allowed))
            chained_request.logger.error('%s has not reached status %s : "%s"' % (self.name , self.allowed, self.level))

        def __str__(self):
            return 'Error: '+self.name+' is in"'+self.level+'" status. requires '+self.allowed
        
    class CampaignStoppedException(NotApprovedException):
        def __init__(self,  oname):
            self.name = str(oname)
            chained_request.logger.error('Campaign %s is stopped' % (self.name))

        def __str__(self):
            return 'Error: '+self.name+' is stopped.'
    
    def __init__(self, json_input={}):

        self._json_base__approvalsteps = ['none','flow', 'submit']
        #self._json_base__status = ['new','started','done']

        self._json_base__status = ['new', 'processing', 'done']

        self._json_base__schema = {
            '_id':'',
            'chain':[],
            'approval':self.get_approval_steps()[0],
            'step':0, 
            'analysis_id':[],
            'pwg':'',
            #'generators':'', #prune
            #'priority':-1, #prune
            'prepid':'',
            #'alias':'', #prune
            'dataset_name':'',
            'total_events':-1,
            'history':[],
            'member_of_campaign':'',
            #'generator_parameters':[], #prune
            #'request_parameters':{} # json with user prefs #prune
            'last_status':'new',
            'status' : self.get_status_steps()[0]
            }
        # update self according to json_input
        self.update(json_input)
        self.validate()


    def flow_trial( self, input_dataset='',  block_black_list=[],  block_white_list=[]):
        chainid = self.get_attribute('prepid')
        try:
            if self.flow():
                db = database('chained_requests')
                db.update(self.json()) 
                return {"prepid":chainid,"results":True}
            return {"prepid":chainid,"results":False, "message":"Failed to flow."}
        except Exception as ex:
            return {"prepid":chainid,"results":False, "message":str(ex)}
        #except chained_request.NotInProperStateException as ex:
        #    return {"prepid":chainid,"results":False, "message":str(ex)}
        #except chained_request.ChainedRequestCannotFlowException as ex:
        #    return {"prepid":chainid,"results":False, "message":str(ex)}

    def flow(self,  input_dataset='',  block_black_list=[],  block_white_list=[]):
        return self.flow_to_next_step(input_dataset,  block_black_list,  block_white_list)
        
    # proceed to the next request in the chain
    def flow_to_next_step(self,  input_dataset='',  block_black_list=[],  block_white_list=[]):
        self.logger.log('Flowing chained_request %s to next step...' % (self.get_attribute('_id')))         

        # check sanity
        if not self.get_attribute('chain'):
            self.logger.error('chained_request %s has got no root' % (self.get_attribute('_id')))
            return False
        
        try:
            rdb = database('requests')
            cdb = database('campaigns')
            ccdb = database('chained_campaigns')
            crdb = database('chained_requests')
            fdb = database('flows')
            adb = database('actions')

        except database.DatabaseAccessError as ex:
            return False

        # where we are in the chain
        stepIndex = int(self.get_attribute('step') )
                    
        # get previous request id
        root = self.get_attribute('chain')[stepIndex]

        # increase step counter        
        stepIndex+=1
        
        # check if exists
        if not rdb.document_exists(root):
            return False
        
        # actually get root request
        initial_req = request(rdb.get(root))
        pc = cdb.get( initial_req.get_attribute('member_of_campaign') )
        req = initial_req.json()
            
        # get the campaign in the next step
        if not ccdb.document_exists(self.get_attribute('member_of_campaign')):
            return False
        
        # get mother chained_campaign
        cc = ccdb.get(self.get_attribute('member_of_campaign'))
        if stepIndex >= len(cc['campaigns']):
            self.logger.error('chained_campaign %s does not allow any further flowing.' % (cc['prepid']), level='warning')
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'))
        
        # check if root request is approved
        #allowed_approvals = ['define',  'approve',  'submit']
        allowed_request_approvals = ['submit']
        
        if initial_req.get_attribute('approval') not in allowed_request_approvals:
            raise self.NotApprovedException(req['_id'], req['approval'], allowed_request_approvals)

        # JR : also check on the status of the root request
        allowed_request_statuses = ['submitted','done']

        if initial_req.get_attribute('status') not in allowed_request_statuses:
            raise self.NotInProperStateException(req['_id'], req['status'], allowed_request_statuses)

        original_action = adb.get( self.get_attribute('chain')[0] )
        my_action_item = original_action['chains'][self.get_attribute('member_of_campaign')]
        if my_action_item['flag'] == False:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'has no valid action')
        if not 'block_number' in my_action_item or not my_action_item['block_number']:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'has no valid block number')

        # find the flow responsible for this step
        #tokstr = cc['prepid'].split('_') # 0: chain, 1: root camp, 2: flow1, 3: flow2, ...
        
        # since step has been increased at the beginning, only add 1
        #if len(tokstr) <= step+1:
        #    self.logger.error('chained_campaign %s does not allow any further flowing.' % (cc['prepid']), level='warning')
        #    raise self.ChainedRequestCannotFlowException(self.get_attribute('prepid'))
            
        #flowname = tokstr[step+1]
        #JR: use the chained campaign internals for finding what to do
        (next_camp,flowname) = cc['campaigns'][stepIndex]

        # check if exists
        if not fdb.document_exists(flowname):
            return False
        if not cdb.document_exists(next_camp):
            return False        
        
        # get flow
        fl = flib.flow(fdb.get(flowname)).json()
        
        allowed_flow_approvals = ['flow','submit']


        ###### cascade of checks
        # if flow allows -> do it
        ## else if chained_request allows -> do it
        # check all approvals (if flow say yes -> allowing policy)
        if fl['approval'] not in allowed_flow_approvals:
            # if flow says No -> check on the chained request itself
            if self.get_attribute('approval') not in allowed_flow_approvals:
                raise self.NotApprovedException(self.get_attribute('_id'),  self.get_attribute('approval'), allowed_flow_approvals)

        # get campaign
        nc = cdb.get(next_camp)
        
        # check if next campaign is started or stopped
        if nc['status'] == 'stopped':
            raise self.CampaignStoppedException(str(next_camp)) 
        
        ## JR: check that there is no already existing requests in the campaign, that corresponds to the same steps of campaign+flow up until now
        alreadyExistingRequest=False
        ## faking it : alreadyExistingRequest=request(rdb.get('JME-Fall11R1-00001'))
        ## look up all chained requests that start from the same root request
        
        
        ## remove <pwg>-chain_ and the -serial number, replacing _ with a .
        toMatch='.'.join(self.get_attribute('prepid').split('_')[1:][0:stepIndex+1]).split('-')[0]
        accs = map(lambda x: x['value'],  crdb.query('root_request=='+self.get_attribute('chain')[0]))
        for existing in accs:
            #if existing['prepid']==self.get_attribute('prepid'): continue
            # get a string truncated to the 
            truncated = '.'.join(existing['prepid'].split('_')[1:][0:stepIndex+1]).split('-')[0]
            self.logger.error('to match : %s , this one %s'%( toMatch, truncated ))
            
            if truncated == toMatch:
                #we found a chained request that starts with all same steps
                matchingcc = chained_request(crdb.get(existing['prepid']))
                if len(matchingcc.get_attribute('chain'))<=stepIndex: 
                       #found one, but it has not enough content either
                       continue
                else:
                    matchingID=matchingcc.get_attribute('chain')[stepIndex]
                    alreadyExistingRequest = request(rdb.get(matchingID))
                    break


        if alreadyExistingRequest!=False:
            # if exist, hand it over to the chained request
            chain = self.get_attribute("chain")
            alreadyExistingID=alreadyExistingRequest.get_attribute('prepid')
            self.logger.log('There is already the request "%s" that fits in the flowing of %s'%(alreadyExistingID,self.get_attribute("prepid")))
            if not alreadyExistingID in chain:
                chain.append(alreadyExistingID)
                self.set_attribute("chain",chain)
                self.update_history({'action':'flow', 'step':str(int(self.get_attribute('step'))+1)})
                self.set_attribute('step',  stepIndex)

            # and register to the lucky one that it is part of a second chained request
            inchains=alreadyExistingRequest.get_attribute("member_of_chain")
            if not self.get_attribute("prepid") in inchains:
                inchains.append(self.get_attribute("prepid"))
                alreadyExistingRequest.set_attribute("member_of_chain",inchains)
                alreadyExistingRequest.update_history({'action':'flow'})
                rdb.update(alreadyExistingRequest.json())
            
            return True
            

        # use root request as template
        req['member_of_campaign'] = next_camp
        req['type'] = nc['type']
        req['cmssw_release'] = nc['cmssw_release']
        req['pileup_dataset_name'] = nc['pileup_dataset_name']
        req['root'] = False #JR???
        req['version']=0
        req['energy'] = nc['energy']
        
        # add the previous requests output_dataset name as input for the new
        ## get the input dataset from the previous request
        ## turn this into a DB object in the far future ?
        # a call to the stats DB ?
        if len(req['reqmgr_name']):
            lastrequest=req['reqmgr_name'][-1]
            if 'content' in lastrequest and 'pdmv_dataset_name' in lastrequest['content']:
                input_dataset = lastrequest['content']['pdmv_dataset_name']
            else:
                ## this is already a soft linking to the stats DB
                statsDB = database('stats',url='http://cms-pdmv-stats.cern.ch:5984/')
                if statsDB.document_exists(lastrequest['name']):
                    latestStatus = statsDB.get(lastrequest['name'])
                    input_dataset = latestStatus['pdmv_dataset_name']
                    

        if input_dataset: 
            req['input_filename'] = input_dataset
        """
        else:
            ## JR we should find a way of getting that info from the previous request
            ### the naming is really awkward here ...
            lastFound=None
            for previous_wma in req['requests']:
                if 'pdmv_dataset' in previous_wma
        """        
            
        if req['completed_events'] <=0:
            raise KeyError('Completed events is negative or null')

        ##transfer completed events to requested events
        req['total_events'] = req['completed_events']
        ## null the completed events
        req['completed_events']=0

        ## check whether we went from a possible root to non-root request
        if nc['root'] ==1 and pc['root'] !=1:
            #in this case, if there are staged number requirements, let's use it
            if self.get_attribute('member_of_campaign') in original_action['chains']:
                my_action_item = original_action['chains'][self.get_attribute('member_of_campaign')]
                if 'staged' in my_action_item:
                    req['total_events'] = my_action_item['staged']
                elif 'threshold' in my_action_item:
                    req['total_events'] = int( req['total_events'] * float( my_action_item['threshold'])  / 100. )

        #self.logger.error( 'we arrived here and req = %s' % (str( req)))

        # add a block black and white list
        if block_black_list:
            req['block_black_list'] = block_black_list
        
        if block_white_list:
            req['block_white_list'] = block_white_list
        
        # remove couchdb specific fields to not confuse it later with an existing document
        del req['_rev']
        del req['_id']
        
        # register it to the chain
        new_req = self.add_request(req)
        
        #set the flow_with parameter
        new_req['flown_with'] = flowname

        # get the sequences
	new_req['sequences'] = []

	# check consistency for the sequences
	if 'sequences' not in fl['request_parameters']:
		self.logger.error('Flow "%s" does not contain any sequences. This is inconsistent. Aborting...' % (fl['_id']), level='critical')
		raise KeyError('Parameter "sequences" is not present in the "request_parameters" of flow "%s".' % (fl['_id']))

	# if the landing campaign and the flow have different sequence steps
	# then fail due to inconsistency
	if len(nc['sequences']) != len(fl['request_parameters']['sequences']):
		self.logger.error('Detected inconsistency ! Campaign "%s" has different sequences defined than flow "%s". Aborting...' % (nc['_id'], fl['_id']), level='critical') 
		raise IndexError('Sequences of campaign "%s" do not match those of flow "%s"' % (nc['_id'], fl['_id']))

        ## put the keep output in order: could be overwritten later by the flow
        new_req['keep_output']=[]
        for s in nc['sequences']:
            new_req['keep_output'].append(False)
        new_req['keep_output'][-1] = True

        ### this is an awfull copy/paste that I had to do because of cross import between request and chained_requests


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
		
        puttogether(nc,fl,new_req)
        

        nre = request(new_req)

        #JR toggle approval of the request until we reached the desired 
        # maximum approval level max(flow,chained_request) in ['none','flow','submit']
        ## TO BE INSERTED HERE, in a Thread object, so as to not hold the request back

        # update history and save request to database
	nre.update_history({'action':'flow'})
        rdb.save(nre.json())

        ## inspect priority
        self.set_priority( my_action_item['block_number'] )

        self.set_attribute('last_status', nre.get_attribute('status'))
        # update local history
        self.update_history({'action':'flow', 'step':str(int(self.get_attribute('step'))+1)})
        
        # finalize changes
        self.set_attribute('step',  int(stepIndex))
        # send notification
        initial_req.notify('Flow for request %s in %s'%(initial_req.get_attribute('prepid'),next_camp),
                           'The request %s has been flown within:\n %s into campaign:\n %s using\n: %s creating the new request:\n %s as part of:\n %s and from the produced dataset:\n %s'%(initial_req.get_attribute('prepid'),
                                                                                                                                                                                             self.get_attribute('member_of_campaign'),
                                                                                                                                                                                             next_camp,
                                                                                                                                                                                             flowname,
                                                                                                                                                                                             nre.get_attribute('prepid'),
                                                                                                                                                                                             self.get_attribute('prepid'),
                                                                                                                                                                                             nre.get_attribute('input_filename')
                                                                                                                                                                                             ))
                    
        
        return True

    # add a new request to the chain
    def add_request(self, data={}):
        self.logger.log('Adding new request to chained_request %s' % (self.get_attribute('_id')))

        # import prep-id generator
        try:
            from rest_api.RequestPrepId import RequestPrepId
        except ImportError as ex:
            self.logger.error('Could not import prep-id generator class. Reason: %s' % (ex), level='critical')
            return {}
        try:
            req = request(json_input=data)
        except Exception as ex:
            self.logger.error('Could not build request object. Reason: %s' % (ex))
            return {}
        
        chain_specific = ['threshold',  'block_number',  'staged']
        
        ## JR remove from schema
        ##this was removed as part of cleaning things up
        #if len(self.get_attribute('request_parameters')) > 0:
        #    changes = self.get_attribute('request_parameters')
        #    for key in changes:
        #        if key not in chain_specific:
        #            req.set_attribute(key, changes[key])

        # get the chain and inherit
        #req.set_attribute("generators", self.get_attribute("generators"))
        #req.set_attribute("total_events", self.get_attribute("total_events")) ## this was taken earlier, with staged number in consideration
        req.set_attribute("dataset_name", self.get_attribute("dataset_name"))
        req.set_attribute("pwg", self.get_attribute("pwg"))
        #JR removed from schema req.set_attribute("priority", self.get_attribute("priority") )
        #JR clear the fragment in flowing: always
        req.set_attribute('name_of_fragment','')
        req.set_attribute('cvs_tag','')
        req.set_attribute('fragment','')
        req.set_attribute('history',[])
        req.set_attribute('reqmgr_name',[])

        #JR
        #clean the mcdbid in the flown request
        #if req.get_attribute('mcdbid')>=0:
        #    req.set_attribute('mcdbid',0)

        # get the new prepid and append it to the chain
        prepid = json.loads(RequestPrepId().generate_prepid(req.get_attribute("pwg"), req.get_attribute('member_of_campaign')))["prepid"]
        chain = self.get_attribute("chain")
        if not chain or chain is None:
            chain = []
        flag = False
        for pid in chain:
            #if req.get_attribute('member_of_campaign') in pid:
            if pid.split('-')[1] == req.get_attribute('member_of_campaign'):
                flag = True
                break
                
        if not flag:
            chain.append(prepid)
            self.set_attribute("chain", chain)
            #self.logger.log('Adding %s to the chain %s'%(prepid,chain))
        else:
            raise self.CampaignAlreadyInChainException(req.get_attribute('member_of_campaign'))

        req.set_attribute('_id', prepid)
        req.set_attribute('prepid',  prepid)
        ## JR: add what the request is member of N.B: that breaks down if a digi-reco request has to be member of two chains (R1,R4)
        req.set_attribute('member_of_chain',[self.get_attribute('_id')])

        ## reset the status and approval chain
        req.set_status(0)
        req.approve(0)

        ### mode the approval of the new request to the approval of the chained request
        if not req.is_root:
            self.logger.log('The newly created request %s is not root, the chained request has approval %s'%(req.get_attribute('prepid'),
                                                                                                             self.get_attribute('approval')
                                                                                                                 ))
            
            #if self.get_attribute('approval') == 'approve':
                #toggle the request approval to 'approved'?
                
            if self.get_attribute('approval') == 'submit':
                req.set_status(to_status='approved')
                req.approve(to_approval='submit')

            
        # update history
        req.update_history({'action': 'join chain', 'step': self.get_attribute('_id')})
        self.update_history({'action':'add request', 'step':req.get_attribute('_id')})

        # set request approval status to new
        #req.approve(0)
        return req.json()

    def set_last_status(self):
        rdb = database('requests')
        step_r = rdb.get( self.get_attribute('chain')[ self.get_attribute('step') ])
        new_last_status= step_r['status']
        if new_last_status != self.get_attribute('last_status'):
            self.update_history({'action':'set last status', 'step': step_r['status']})
            self.set_attribute( 'last_status' , step_r['status'] )
            return True
        else:
            return False
    
    def set_processing_status(self, pid=None, status=None):
        if not pid  or not status:
            rdb = database('requests')
            step_r = rdb.get( self.get_attribute('chain')[ self.get_attribute('step') ])
            pid = step_r['prepid']
            status = step_r['status']

        if pid ==self.get_attribute('chain')[ self.get_attribute('step') ]:
            expected_end = max(0,self.get_attribute('prepid').count('_')-1)
            current_status = self.get_attribute('status')
            ## the current request is the one the status has just changed
            self.logger.log('processing status %s given %s and at %s and stops at %s '%( current_status, status, self.get_attribute('step'), expected_end))
            if self.get_attribute('step') == expected_end and status=='done' and current_status=='processing':
                ## you're supposed to be in processing status
                self.set_status()
                return True
            ##only when updating with a submitted request status do we change to processing
            if status in ['submitted'] and current_status=='new':
                self.set_status()
                return True
            return False
        else:
            return False

    def set_priority(self,level):
        rdb = database('requests')
        for r in self.get_attribute('chain'):
            req=request(rdb.get(r))
            ##only those that can still be changed
            if not req.get_attribute('status') in ['submitted','done']:
                #set to the maximum priority
                req.set_attribute('priority', max(req.get_attribute('priority'),  priority().priority(level)))
                rdb.update(req.json())
        
    def inspect(self):
        not_good = {"prepid": self.get_attribute('prepid'), "results":False}
        
        if self.get_attribute('last_status') == 'done':
            return self.inspect_done()

        not_good.update( {'message' : 'Nothing to inspect on chained request in %s last status'%( self.get_attribute('last_status')) })
        return not_good

    def inspect_done(self):
        return self.flow_trial()
        

        
        
