#!/usr/bin/env python

from chained_request import chained_request
from json_base import json_base
from request import request
from couchdb_layer.mcm_database import database
from rest_api.ChainedRequestPrepId import ChainedRequestPrepId
from json import loads,  dumps

class chained_campaign(json_base):
    class CampaignDoesNotExistException(Exception):
        def __init__(self,  campid):
            self.c = str(campid)
            chained_campaign.logger.error('Campaign %s does not exist' % (self.c) )

        def __str__(self):
            return 'Error: Campaign ' +  self.c +  ' does not exist.'
    
    class FlowDoesNotExistException(Exception):
        def __init__(self,  flowid):
            self.f = str(flowid)
            chained_campaign.logger.error('Flow %s does not exist' % (self.f))

        def __str__(self):
            return 'Error: Flow ' + self.f + ' does not exist.'
    
    def __init__(self, json_input=None):
        if not json_input: json_input = {}
        self._json_base__schema = {
            '_id':'',
            'prepid':'',
            'alias':'', 
            #'energy':0,
            'campaigns':[], # list of lists [camp_id, flow]
            #'description':'',
            'notes':'',
            'action_parameters':{}, 
            #'www':'',
            'history':[],
            'valid':True
            }
        
        # update self according to json_input
        self.update(json_input)
        self.validate()

    # start() makes the chained campaign visible to the actions page
    def start(self):
        if self._json_base__json['valid']:
            return
        self.update_history({'action':'start'})
        self._json_base__json['valid']=True
    
    # stop() makes the chained campaign invisible to the actions page
    def stop(self):
        if not self._json_base__json['valid']:
            return
        self.update_history({'action':'stop'})
        self._json_base__json['valid']=False

    def add_campaign(self, campaign_id,  flow_name=None):
        self.logger.log('Adding a new campaign %s to chained campaign %s' % (campaign_id, self.get_attribute('_id'))) 

        camp_db = database('campaigns')
        flow_db = database('flows')
            
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
        self.logger.log('Removing campaign %s from chained_campaign %s' % (cid, self.get_attribute('_id'))) 
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
        self.logger.log('Building a new chained_request for chained_campaign %s. Root request: %s' % (self.get_attribute('_id'), root_request_id ))
        try:
            rdb = database('requests')
            crdb = database('chained_requests')
        except database.DatabaseAccessError as ex:
            return {}
            
        # check to see if root request id exists
        if not rdb.document_exists(root_request_id):
            return {}
        
        # init new creq

        # parse request id
        tok = root_request_id.split('-')
        pwg = tok[0]
        camp = tok[1]
        # generate new chain id
        cid = ChainedRequestPrepId().next_id(pwg, self.get_attribute('prepid'))

        creq = chained_request(crdb.get(cid))

        
        # set values
        creq.set_attribute('pwg',  pwg)
        creq.set_attribute('member_of_campaign',  self.get_attribute('prepid'))
        ##inherit the approval of the chained_campaign
        ## approval is not a member of chained campaign 
        # creq.set_attribute('approval', self.get_attribute('approval'))


        if not creq.get_attribute('prepid'):
            raise ValueError('Prepid returned was None')
        
        # set the default values that will be carried over to the next step in the chain
        req = rdb.get(root_request_id)
        
        #creq.set_attribute("generators", req["generators"])
        creq.set_attribute("total_events", req["total_events"])
        creq.set_attribute("dataset_name", req["dataset_name"])
        creq.set_attribute("pwg", req["pwg"])
        #creq.set_attribute("priority", req["priority"] )
        #creq.approve(0)
        
        # set request parameters
        ## legacy wat of passing the info to the chained request
        """
        reqp = self.get_attribute('action_parameters')
        if root_request_id in reqp:
            creq.set_attribute('request_parameters',  reqp[root_request_id])
        
            # delete the parameters for this chained request
            #self.__remove_request_parameters(root_request_id)
            del reqp[root_request_id]
            self.set_attribute('action_parameters',  reqp)
        """

        # add root request to chain
        creq.set_attribute('chain',  [root_request_id])

        # update history
        creq.update_history({'action':'created'})
        self.update_history({'action':'add request','step':creq.get_attribute('_id')})
        
        # save to database
        return creq.json()
        
    def __remove_request_parameters(self,  rootid=None):
        ob = self.get_attribute('action_parameters')
        res = {}
        for key in ob:
            if key == rootid:
                continue
            res[key] = ob[key]
        self.set_attribute('action_parameters',  res)
