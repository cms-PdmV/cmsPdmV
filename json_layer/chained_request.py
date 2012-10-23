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
        def __str__(self):
            return 'Error: Campaign', self.c,  'already represented in the chain.' 
    
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
    
    # proceed to the next request in the chain
    def flow(self):
        # increase step counter
        step = self.get_attribute('step') + 1
            
        # check sanity
        if not self.get_attribute('chain'):
            print 'Error: Chain '+self.get_attribute('_id')+' has no root.'
            return False
        
        try:
            rdb = database('requests')
            ccdb = database('chained_campaigns')
        except database.DatabaseAccessError as ex:
            print str(ex)
            return False
        
        # get root request id
        root = self.get_attribute('chain')[0]
        
        # check if exists
        if not rdb.document_exists(root):
            print 'Error: Request '+str(root)+' does not exist.'
            return False
        
        # actually get root request
        req = rdb.get(root)
        
        # get the campaign in the next step
        if not ccdb.document_exists(self.get_attribute('member_of_campaign')):
            print 'Error: Chained Campaign '+str(self.get_attribute('member_of_campaign'))+' does not exist.'
            return False
        
        # get mother chained_campaign
        cc = ccdb.get(self.get_attribute('member_of_campaign'))
        if step >= len(cc['campaigns']):
            print 'Warning: Chained Request '+str(self.get_attribute('_id'))+' cannot flow any further.'
            return False  
        
        # get next campaign
        next_camp = cc['campaigns'][step][0] # just the camp name, not the flow
        
        # use root request as template
        req['member_of_campaign'] = next_camp
        req['root'] = False
        
        # remove couchdb specific fields
        del req['_rev']
        del req['_id']
        
        # register it to the chain
        print req
        new_req = self.add_request(req)
        
        # save new request to database
        rdb.save(new_req)
        
        # finalize changes
        self.set_attribute('step',  step)
        
        return True

    def approve(self,  index=-1):
        approvals = self.get_attribute('approvals')
        app = approval('')
        
        # if no index is specified, just go one step further
        if index==-1:
            index = len(approvals)
        
        try:
            new_apps = app.approve(index)
            self.set_attribute('approvals',  new_apps)
            return True
        except app.IllegalApprovalStep as ex:
            print str(ex)
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
            print str(ex)
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
        # import prep-id generator
        try:
            from rest_api.RequestPrepId import RequestPrepId
        except ImportError as ex:
            print str(ex)
            return {}
        try:
            req = request('',json_input=data)
        except Exception as ex:
            print str(ex)
            return {}

        if len(self.get_attribute('request_parameters')) > 0:
            changes = self.get_attribute('request_parameters')[-1]
            for key in changes:
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
        return req.json()

