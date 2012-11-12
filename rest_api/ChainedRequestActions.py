#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from couchdb_layer.prep_database import database
from RestAPIMethod import RESTResource
from RequestChainId import RequestChainId
from json_layer.chained_request import chained_request

class CreateChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'
        self.db = database(self.db_name)
        self.req = None
        self.json = {}

    def PUT(self):
        return self.import_request(cherrypy.request.body.read().strip())
    def import_request(self, data):
        try:
            self.req = chained_request('TEST', json_input=loads(data))
        except chained_request.IllegalAttributeName as ex:
            print str(ex)
            return dumps({"results":False})

        id = RequestChainId().generate_id(self.req.get_attribute('pwg'), self.req.get_attribute('member_of_campaign'))
        self.req.set_attribute('prepid',loads(id)['results'])

        if not self.req.get_attribute('prepid'):
            raise ValueError('Prepid returned was None')
        self.req.set_attribute('_id', self.req.get_attribute('prepid'))
        self.json = self.req.json()

        return self.save_request()

    def save_request(self):
        if self.db.save(self.json):
            return dumps({"results":True})
        else:
            return dumps({"results":False})

class UpdateChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'
        self.db = database(self.db_name)
        self.json = {}
        self.request = None
    def PUT(self):
        return self.update_request(cherrypy.request.body.read().strip())

    def update_request(self, data):
        try:
            self.request = chained_request('TEST', json_input=loads(data))
        except chained_request.IllegalAttributeName as ex:
            print str(ex)
            return dumps({"results":False})

        if not self.request.get_attribute('prepid') and not self.request.get_attribute('_id'):
            raise ValueError('Prepid returned was None')
            #self.request.set_attribute('_id', self.request.get_attribute('prepid')
        self.json = self.request.json()
        return self.save_request()
        
    def save_request(self):
        return dumps({"results":self.db.update(self.json)})

class DeleteChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'
        self.db = database(self.db_name)
    
    def DELETE(self, *args):
        if not args:
            return dumps({"results":False})
        return self.delete_request(args[0])
    
    def delete_request(self, id):
        return dumps({"results":self.db.delete(id)})

class GetChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        if not args:
            return dumps({"results":{}})
        return self.get_request(args[0])
    
    def get_request(self, data):
        return dumps({"results":self.db.get(prepid=data)})

# REST method to add a new request to the chain
class AddRequestToChain(RESTResource):
    def __init__(self):
        self.rdb = database('requests')
        self.db = database('chained_requests')
    
    def PUT(self):
        return self.add_to_chain(cherrypy.request.body.read().strip())
        
    def add_to_chain(self, data):
        try:
            from json_layer.request import request
        except ImportError as ex:
            print str(ex)
            return dumps({"results":False})
        try:
            req = request('TEST', json_input=loads(data))
        except request.IllegalAttributeName as ex:
            print str(ex)
            return dumps({"results":str(ex)})
            
        if not req.get_attribute("member_of_chain"):
            raise ValueError('"member_of_chain" attribute was None.')
            return dumps({"results":'Error: "member_of_chain" attribute was None.'})
            
        if not req.get_attribute("member_of_campaign"):
            raise ValueError('"member_of_campaign" attribute was None.')
            return dumps({"results":'Error: "member_of_chain" attribute was None.'})        
        
        try:
            creq = chained_request('test',  json_input=self.db.get(req.get_attribute('member_of_chain')))
        except chained_request.IllegalAttributeName as ex:
            print str(ex)
            return dumps({"results":str(ex)})
            
        try:
            new_req = creq.add_request(req.json())
        except chained_request.CampaignAlreadyInChainException as ex:
            print str(ex)
            return dumps({"results":str(ex)})
            
        if not new_req:
            return dumps({"results":False})

        # finalize and make persistent
        self.db.update(creq.json())
        self.rdb.save(new_req)
        return dumps({"results":True})

# REST method that makes the chained request flow to the next
# step of the chain
class FlowToNextStep(RESTResource):
    def __init__(self):
        self.db = database('chained_requests')
    
    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given.'})
        return self.flow(args[0])
        
    def flow(self,  chainid):
        try:
            creq = chained_request('test',  json_input=self.db.get(chainid))
        except Exception as ex:
            print str(ex)
            return dumps({"results":str(ex)})
        
        # if the chained_request can flow, do it
        try:
            if creq.flow():
                self.db.update(creq.json())
                return dumps({"results":True})
            return dumps({"results":False})
        except chained_request.NotApprovedException as ex:
            return dumps({"results":str(ex)})
        except chained_request.ChainedRequestCannotFlowException as ex:
            return dumps({"results":str(ex)})

class ApproveRequest(RESTResource):
    def __init__(self):
        self.db = database('chained_requests')
    
    def GET(self,  *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return self.approve(args[0],  int(args[1]))
        
    def approve(self,  rid,  val):
        if not self.db.document_exists(rid):
            return dumps({"results":'Error: The given chained_request id does not exist.'})
        creq = chained_request('',  json_input=self.db.get(rid))
        if not creq.approve(val):
            return dumps({"results":False})
        
        return dumps({"results":self.db.update(creq.json())})
