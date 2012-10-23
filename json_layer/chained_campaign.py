#!/usr/bin/env python

from chained_request import chained_request
from json_base import json_base
from submission_details import submission_details
from approval import approval
from comment import comment
from request import request
from couchdb_layer.prep_database import database
from rest_api.RequestChainId import RequestChainId
from json import loads,  dumps

class chained_campaign(json_base):
    class CampaignDoesNotExistException(Exception):
        def __init__(self,  campid):
            self.c = str(campid)
        def __str__(self):
            return 'Error: Campaign ' +  self.c +  ' does not exist.'
    
    class FlowDoesNotExistException(Exception):
        def __init__(self,  flowid):
            self.f = str(flowid)
        def __str__(self):
            return 'Error: Flow ' + self.f + ' does not exist.'
    
    def __init__(self, author_name, author_cmsid=-1, author_inst_code='', author_project='', json_input={}):
        self._json_base__schema = {
            '_id':'',
            'prepid':'',
            'alias':'', 
            'energy':0,
            'campaigns':[], # list of lists [camp_id, flow]
            'approvals':[],
            'description':'',
            'action_parameters':{}, 
            'www':'',
            'submission_details':submission_details().build(author_name,  author_cmsid,  author_inst_code,  author_project    ),
            'comments':[], 
            'valid':True
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
    
    # start() makes the chained campaign visible to the actions page
    def start(self):
        if self._json_base__json['valid']:
            return
        self._json_base__json['valid']=True
    
    # stop() makes the chained campaign invisible to the actions page
    def stop(self):
        if not self._json_base__json['valid']:
            return
        self._json_base__json['valid']=False

    def add_comment(self,author_name, comment, author_cmsid=-1, author_inst_code='', author_project=''):
        comments = self.get_attribute('comments')
        new_comment = comment(author_name,  author_cmsid,  author_inst_code,  author_project).build(comment)
        comments.append(new_comment)
        self.set_attribute('comments',  comments)
    
    def add_campaign(self, campaign_id,  flow_name=None):
        try:
            from couchdb_layer.prep_database import database
        except ImportError as ex:
            print str(ex)
            return False
            
        try:
            camp_db = database('campaigns')
            flow_db = database('flows')
        except database.DatabaseAccessError as ex:
            print str(ex)
            return False
            
        if not camp_db.document_exists(campaign_id):
            raise self.CampaignDoesNotExistException(campaign_id) 
        
        # check to see if flow_name is none (campaign_id = root)
        if flow_name is not None:
            if not flow_db.document_exists(flow_name):
                raise self.FlowDoesNotExistException(flow_name)
        
        camps = self.get_attribute('campaigns')
        if not camps or camps is None:
            camps = []
        camps.append([campaign_id,  flow_name])
        self.set_attribute('campaigns', camps)
        
        return True
        
    def remove_campaign(self,  cid):
        camps = self.get_attribute('campaigns')
        new_camps = []
        if not camps or camps is None:
            camps = []
        else:
            for c, f in camps:
                if cid in c:
                    continue
                new_camps.append((c, f))
                
        self.set_attribute('campaigns',  new_camps)
    
    # create a chained request spawning from root_request_id
    def generate_request(self,  root_request_id):
        try:
            rdb = database('requests')
        except database.DatabaseAccessError as ex:
            print str(ex)
            return {}
            
        # check to see if root request id exists
        if not rdb.document_exists(root_request_id):
            print 'Error: PrepId ',  root_request_id,  'does not exist.'
            return {}
        
        # init new creq
        creq = chained_request('automatic')
        
        # parse request id
        tok = root_request_id.split('-')
        pwg = tok[0]
        camp = tok[1]
        
        # set values
        creq.set_attribute('pwg',  pwg)
        creq.set_attribute('member_of_campaign',  self.get_attribute('prepid'))
        
        # generate new chain id
        id = RequestChainId().generate_id(creq.get_attribute('pwg'), creq.get_attribute('member_of_campaign'))
        creq.set_attribute('prepid',loads(id)['results'])

        if not creq.get_attribute('prepid'):
            raise ValueError('Prepid returned was None')
        creq.set_attribute('_id', creq.get_attribute('prepid'))
        
        # set the default values that will be carried over to the next step in the chain
        req = rdb.get(root_request_id)
        
        creq.set_attribute("generators", req["generators"])
        creq.set_attribute("total_events", req["total_events"])
        creq.set_attribute("dataset_name", req["dataset_name"])
        creq.set_attribute("pwg", req["pwg"])
        creq.set_attribute("priority", req["priority"] )
        
        # set request parameters
        reqp = self.get_attribute('action_parameters')
        if root_request_id in reqp:
            creq.set_attribute('request_parameters',  reqp[root_request_id])
        
        # add root request to chain
        creq.set_attribute('chain',  [root_request_id])
        
        # save to database
        return creq.json()
