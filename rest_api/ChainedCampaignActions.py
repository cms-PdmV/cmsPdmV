#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from couchdb_layer.prep_database import database
from json_layer.chained_request import chained_request
from json_layer.chained_campaign import chained_campaign
from json_layer.campaign import campaign
from json_layer.request import request
from RestAPIMethod import RESTResource
from json_layer.action import action

class CreateChainedCampaign(RESTResource):
    def __init__(self):
        self.db = database('chained_campaigns')
        self.adb = database('actions')
        self.ccamp = None
        self.json = None
    
    def PUT(self):
                return self.create_campaign(cherrypy.request.body.read().strip())

    def create_campaign(self, jsdata):
        try:
            self.ccamp = chained_campaign('TEST', json_input=loads(jsdata))
        except chained_campaign('').IllegalAttributeName as ex:
            return dumps({"results":str(ex)})
        
        self.ccamp.set_attribute("_id", self.ccamp.get_attribute("prepid"))
        if not self.ccamp.get_attribute("_id") :#or self.db.document_exists(self.ccamp.get_attribute("_id")):
            return dumps({"results":'Error: Campaign '+self.ccamp.get_attribute("_id")+' already exists'})
        
        # update actions db
        self.update_actions()
        
        return dumps({"results":self.db.save(self.ccamp.json())})
    
    # update the actions db to include the new chain
    def update_actions(self):
        # get all campaigns in the chained campaign
        camps = self.ccamp.get_attribute('campaigns')
        
        # for every campaign with a defined flow
        for c, f in camps:
            if f:
                # update all its requests
                self.update_action(c)
    
    # find all actions that belong to requests in cid
    # and append cid in the chain
    def update_action(self,  cid):
        rel_ac = self.adb.query('member_of_campaign=='+cid)
        for a in rel_ac:
            # avoid duplicate entries
            if cid not in a['chains']:
                # append new chain id and set to 0
                a['chains'][cid]=0
                # save to db
                self.adb.update(a)

class UpdateChainedCampaign(RESTResource):
        def __init__(self):
                self.db = database('chained_campaigns')
                self.ccamp = None
                self.json = None

        def PUT(self):
                return self.update_campaign(cherrypy.request.body.read().strip())

        def update_campaign(self, jsdata):
                try:
                        self.ccamp = chained_campaign('TEST', json_input=loads(jsdata))
                except chained_campaign('').IllegalAttributeName as ex:
                        return dumps({"results":False})

                if not self.ccamp.get_attribute("_id"):
                        return dumps({"results":False})
                return dumps({"results":self.db.update(self.ccamp.json())})

        
class AddRequestToChain(RESTResource):
    def __init__(self):
        self.request_db = database('requests')
        self.campaign_db = database('campaigns')
        self.chained_db = database('chained_requests')
        self.json = {}

    def POST(self, *args):
        if not args:
            return dumps({"results":False})
        if len(args) < 2:
            return dumps({"results":False})
        return self.import_request(args[0], args[1])

    def add_request(self, chainid, campaignid):
        if not chainid:
            return dumps({"results":False}) 
        else:
            try:
                chain = chained_request('', chained_request_json=self.chained_db.get(chainid))
            except Exception as ex:
                return dumps({"results":False})
        if not campaignid:
            return dumps({"results":False})
        else:
            try:
                camp = campaign('', campaign_json=self.campaign_db.get(campaignid))
            except Exception as ex:
                return dumps({"results":False})
        req = camp.add_request()
        new_req = chain.add_request(req)
        
        # save everything
        if not self.chain_db.save(chain.json()):
            return dumps({"results":False})
        return dumps({"results":self.request_db.save(new_req)})

class DeleteChainedCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'chained_campaigns'
        self.db = database(self.db_name)
        self.adb = database('actions')
    def DELETE(self, *args):
        if not args:
            return dumps({"results":False})
        return self.delete_request(args[0])
        
    def delete_request(self, id):
        if not self.delete_all_requests(id):
            return dumps({"results":False})
            
        # update all relevant actions
        self.update_actions(id)
        
        return dumps({"results":self.db.delete(id)})
        
    def update_actions(self,  cid):
        # get all actions that contain cid in their chains
        actions = self.adb.query('chain=='+cid)
        for a in actions:
            if cid in a['chains']:
                # delete the option of cid in each relevant action
                del a['chains'][cid]
                self.adb.update(a)

    def delete_all_requests(self, id):
        rdb = database('chained_requests')
        res = rdb.query('member_of_campaign=='+id, page_num=-1)
        try:
            for req in res:
                rdb.delete(req['value']['prepid'])
            return True
        except Exception as ex:
            print str(ex)
            return False

class GetChainedCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'chained_campaigns'
        self.db = database(self.db_name)
    def GET(self, *args):
        if not args:
            return dumps({"results":False})
        return self.get_request(args[0])
    def get_request(self, id):
        return dumps({"results":self.db.get(id)})
      

class GenerateChainedRequests(RESTResource):
    def __init__(self):
        self.crdb = database('chained_requests')
        self.ccdb = database('chained_campaigns')
        self.cdb = database('campaigns')
        self.adb = database('actions')
    
    def GET(self,  *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return self.generate_requests(args[0])
    
    def generate_requests(self,  id):
        # init chained_campaign
        cc = chained_campaign('',  json_input=self.ccdb.get(id))
        
        # get the campaigns field and from that...
        camps = cc.get_attribute('campaigns')
        # ... the root campaign (assume it is the first, since non-root campaigns are only appended to chains)
        rootc = camps[0][0]
        
        # get all the actions of requests that belong to the root campaign
        rootreqs = self.adb.query('member_of_campaign=='+rootc)
        rreqs = map(lambda x: x['value'],  rootreqs)
        
        # find all actions that have selected this chained campaign
        for ract in rreqs:
            if ract['chains'][id]:
                if ract['chains'][id] > 0:
                    # check if the chain already exists
                    accs = map(lambda x: x['value'],  self.crdb.query('root_request=='+ract['_id']))
                    flag = False
                    for acc in accs:
                        if id == acc['_id'].split('-')[1]:
                            flag = True
                            break
                
                    if flag:
                        print 'Warning: A chained request already exists for chained_campaign',  id
                        continue
                    
                    # create the chained requests
                    new_req = cc.generate_request(ract['prepid'])
                    # save to database
                    self.crdb.save(new_req)
                    
        return dumps({"results":True})
