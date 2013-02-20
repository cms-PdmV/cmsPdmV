from json_base import json_base
from submission_details import submission_details
from approval import approval
from comment import comment
from request import request
from couchdb_layer.prep_database import database
import json

class chained_request(json_base):
    class CampaignAlreadyInChainException(Exception):
        def __init__(self,  campaign):
            self.c = campaign
            chained_request.logger.error('Campaign %s is already member of the chain.' % (self.c))

        def __str__(self):
            return 'Error: Campaign', self.c,  'already represented in the chain.'
    
    class ChainedRequestCannotFlowException(Exception):
        def __init__(self,  crname):
            self.name = str(crname)
            chained_request.logger.error('Chained request %s cannot flow any further.' % (self.name))

        def __str__(self):
            return 'Error: Chained request '+self.name+' cannot flow any further.'
    
    class NotApprovedException(Exception):
        def __init__(self,  oname,  alevel):
            self.name = str(oname)
            self.level = str(alevel)
            chained_request.logger.error('%s has not been approved for level "%s"' % (self.name , self.level))

        def __str__(self):
            return 'Error: '+self.name+' has not been "'+self.level+'" approved.'
        
    class CampaignStoppedException(NotApprovedException):
        def __init__(self,  oname):
            self.name = str(oname)
            chained_request.logger.error('Campaign %s has been stopped' % (self.name))

        def __str__(self):
            return 'Error: '+self.name+' has been stopped.'
    
    def __init__(self, author_name, author_cmsid=-1, author_inst_code='', author_project='', json_input={}):
        self._json_base__schema = {
            '_id':'',
            'chain':[],
            'approvals':[],
            'submission_details':submission_details().build(author_name,  author_cmsid,  author_inst_code,  author_project), 
            'step':0, 
            'comments':[],
            'analysis_id':[],
            'pwg':'',
            'generators':'',
            'priority':-1,
            'prepid':'',
            'alias':'', 
            'dataset_name':'',
            'total_events':-1,
            'member_of_campaign':'',
            'generator_parameters':[],
            'request_parameters':{} # json with user prefs
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
            if '_rev' in json_input:
                self._json_base__json['_rev'] = json_input['_rev']
    
    def flow(self,  input_dataset='',  block_black_list=[],  block_white_list=[]):
        return self.flow_to_next_step(input_dataset,  block_black_list,  block_white_list)
        
    # proceed to the next request in the chain
    def flow_to_next_step(self,  input_dataset='',  block_black_list=[],  block_white_list=[]):
        self.logger.log('Flowing chained_request %s to next step...' % (self.get_attribute('_id')))         

        # increase step counter
        step = int(self.get_attribute('step') )+ 1
            
        # check sanity
        if not self.get_attribute('chain'):
            self.logger.error('chained_request %s has got no root' % (self.get_attribute('_id')))
            return False
        
        try:
            rdb = database('requests')
            cdb = database('campaigns')
            ccdb = database('chained_campaigns')
            fdb = database('flows')
        except database.DatabaseAccessError as ex:
            return False
        
        # get previous request id
        root = self.get_attribute('chain')[step-1]
        
        # check if exists
        if not rdb.document_exists(root):
            return False
        
        # actually get root request
        req = rdb.get(root)
            
        # get the campaign in the next step
        if not ccdb.document_exists(self.get_attribute('member_of_campaign')):
            return False
        
        # get mother chained_campaign
        cc = ccdb.get(self.get_attribute('member_of_campaign'))
        if step >= len(cc['campaigns']):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'))
        
        # check if request is approved
        # TODO: check flow's approvals
        allowed_approvals = ['define',  'approve',  'submit']
        
        if req['approvals'][-1]['approval_step'] != 'define' and req['approvals'][-1]['approval_step'] not in allowed_approvals:  
                raise self.NotApprovedException(req['_id'],  'define')
        
        # find the flow responsible for this step
        tokstr = cc['prepid'].split('_') # 0: chain, 1: root camp, 2: flow1, 3: flow2, ...
        
        # since step has been increased at the beginning, only add 1
        if len(tokstr) <= step+1:
            self.logger.error('chained_campaign %s does not allow any further flowing.' % (cc['prepid']), level='warning')
            raise self.ChainedRequestCannotFlowException(self.get_attribute('prepid'))
            
        flowname = tokstr[step+1]
        
        if not fdb.document_exists(flowname):
            return False
        
        # get flow
        fl = fdb.get(flowname)
        
        # check all approvals (if flow say yes -> allowing policy)
        if 'approvals' in fl and len(fl['approvals']) > 0:
            if fl['approvals'][-1]['approval_step'] not in allowed_approvals:
                if req['approvals'][-1]['approval_step'] not in allowed_approvals:
                    if self.get_attribute('approvals')[-1]['approval_step'] not in allowed_approvals:
                        raise self.NotApprovedException(self.get_attribute('_id'),  'flow')
        else:
            if req['approvals'][-1]['approval_step'] not in allowed_approvals:
                if self.get_attribute('approvals')[-1]['approval_step'] not in allowed_approvals:
                    raise self.NotApprovedException(self.get_attribute('_id'),  'flow')            
        
        # get next campaign
        next_camp = cc['campaigns'][step][0] # just the camp name, not the flow
        
        # check if exists
        if not cdb.document_exists(next_camp):
            return False
        
        # get campaign
        nc = cdb.get(next_camp)
        
        # check if next campaign is started or stopped
	if len(nc['approvals']) > 1:
	        if nc['approvals'][-1]['approval_step'] == 'stop':
        	    raise self.CampaignStoppedException(str(next_camp))
	elif not nc['approvals']:
		raise self.CampaignStoppedException(str(next_camp))
        
        # use root request as template
        req['member_of_campaign'] = next_camp
        req['type'] = nc['type']
        req['root'] = False
        
        # add the previous requests output_dataset name as input for the new
        if input_dataset: 
            req['input_filename'] = input_dataset
            
        # add a block black and white list
        if block_black_list:
            req['block_black_list'] = block_black_list
        
        if block_white_list:
            req['block_white_list'] = block_white_list
        
        # remove couchdb specific fields
        del req['_rev']
        del req['_id']
        
        # register it to the chain
        new_req = self.add_request(req)
        
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
		

        # save new request to database
        rdb.save(new_req)
        
        # finalize changes
        self.set_attribute('step',  str(step))
        
        return True

    def approve(self,  index=-1):
        approvals = self.get_attribute('approvals')
        app = approval('')
        
        # if no index is specified, just go one step further
        if index==-1:
            index = len(approvals)

        self.logger.log('Approving chained_request %s for step "%s"' % (self.get_attribute('_id'), index)) 
        
        try:
            new_apps = app.approve(index)
            self.set_attribute('approvals',  new_apps)
            return True
        except app.IllegalApprovalStep as ex:
            return False

    def approve1(self,  author_name,  author_cmsid=-1, author_inst_code='', author_project=''):
        approvals = self.get_attribute('approvals')
        app = approval('')
        index = -1
        step = app.get_approval(0)

        # find if approve is legal (and next step)
        if len(approvals) == 0:
            index = -1
        elif len(approvals) == len(app.get_approval_steps()):
            raise app.IllegalApprovalStep()
        else:
            step = approvals[-1]['approval_step']
            index = app.index(step) + 1
            step = app.get_approval(index)

        # build approval 
        try:
            new_approval = approval(author_name, author_cmsid, author_inst_code,author_project).build(step)
        except approval('').IllegalApprovalStep(step) as ex:
            return

        # make persistent
        approvals.append(new_approval)
        self.set_attribute('approvals',  approvals)

    def add_comment(self,author_name, comment, author_cmsid=-1, author_inst_code='', author_project=''):
        comments = self.get_attribute('comments')
        new_comment = comment(author_name,  author_cmsid,  author_inst_code,  author_project).build(comment)
        comments.append(new_comment)
        self.set_attribute('comments',  comments)
    
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
            req = request('',json_input=data)
        except Exception as ex:
            self.logger.error('Could not build request object. Reason: %s' % (ex))
            return {}
        
        chain_specific = ['threshold',  'block_number',  'staged']
        
        if len(self.get_attribute('request_parameters')) > 0:
            changes = self.get_attribute('request_parameters')
            for key in changes:
                if key not in chain_specific:
                    req.set_attribute(key, changes[key])

        # get the chain and inherit
        req.set_attribute("generators", self.get_attribute("generators"))
        req.set_attribute("total_events", self.get_attribute("total_events"))
        req.set_attribute("dataset_name", self.get_attribute("dataset_name"))
        req.set_attribute("pwg", self.get_attribute("pwg"))
        req.set_attribute("priority", self.get_attribute("priority") )
        
        # get the new prepid and append it to the chain
        prepid = json.loads(RequestPrepId().generate_prepid(req.get_attribute("pwg"), req.get_attribute('member_of_campaign')))["prepid"]
        chain = self.get_attribute("chain")
        if not chain or chain is None:
            chain = []
        flag = False
        for pid in chain:
            if req.get_attribute('member_of_campaign') in pid:
                flag = True
                break
                
        if not flag:
            chain.append(prepid)
            self.set_attribute("chain", chain)
        else:
            raise self.CampaignAlreadyInChainException(req.get_attribute('member_of_campaign'))
        
        req.set_attribute('_id', prepid)
        req.set_attribute('prepid',  prepid)
        # set request approval status to new
        req.approve(0)
        return req.json()

