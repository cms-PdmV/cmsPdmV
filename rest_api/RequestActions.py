#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from couchdb_layer.prep_database import database
from RestAPIMethod import RESTResource
from RequestPrepId import RequestPrepId
from json_layer.request import request
from json_layer.action import action

class ImportRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.adb = database('actions')
        self.cdb = database('campaigns')
        self.json = {}

    def PUT(self):
        return self.import_request(cherrypy.request.body.read().strip())

    def import_request(self, data):
        try:
            self.json = request('automatic', json_input=loads(data)).json()
        except request.IllegalAttributeName as ex:
            return dumps({"results":False})

        id = RequestPrepId().generate_prepid(self.json['pwg'], self.json['member_of_campaign'])
        self.json['prepid'] = loads(id)['prepid']
        
        if not self.json['prepid']:
            raise ValueError('Prepid returned was None')
        self.json['_id'] = self.json['prepid']
        
        # save to database
        if not self.db.save(self.json):
            return dumps({"results":False})
        
        # add an action to the action_db
        self.add_action()
        
        return dumps({"results":self.json['_id']})
        
    def add_action(self):
        # Check to see if the request is a root request
        if self.json['mcdb_id'] != -1:
            camp = self.json['member_of_campaign']
            
            if not self.cdb.document_exists(camp):
                return dumps({"results":'Error: Campaign '+str(camp)+' does not exist.'})
                
            # get campaign
            c = self.cdb.get(camp)
            
            if c['root'] != 0:
                return
        
        # check to see if the action already exists
        if not self.adb.document_exists(self.json['prepid']):
            # add a new action
            a= action('automatic')
            a.set_attribute('prepid',  self.json['prepid'])
            a.set_attribute('_id',  a.get_attribute('prepid'))
            a.set_attribute('member_of_campaign',  self.json['member_of_campaign'])
            a.find_chains()
            self.adb.save(a.json())

class UpdateRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.json = {}
        self.request = None
        
    def PUT(self):
        return self.update_request(cherrypy.request.body.read().strip())

    def update_request(self, data):
        try:
                self.request = request('TEST', json_input=loads(data))
        except request.IllegalAttributeName as ex:
                return dumps({"results":False})
    
        if not self.request.get_attribute('prepid') and not self.request.get_attribute('_id'):
            raise ValueError('Prepid returned was None')
            
        self.json = self.request.json()
        return self.save_request()

    def save_request(self):
        return dumps({"results":self.db.update(self.json)})

class GetCmsDriverForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.json = {}
        self.request = None

    def GET(self, *args):
      print args
      if not args:
        return dumps({"results":{}})
      return self.get_cmsDriver(self.db.get(prepid=args[0]))

    def get_cmsDriver(self, data):
      try:
        self.request = request('TEST', json_input=data)
        self.request.print_self()     
      except request.IllegalAttributeName as ex:
        return dumps({"results":''})
        
      return dumps({"results":self.request.buildCmsDrivers()}) 
      

class DeleteRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.adb = database('actions')
    
    def DELETE(self, *args):
        if not args:
            return dumps({"results":False})
        return self.delete_request(args[0])
    
    def delete_request(self, id):
        # delete actions
        self.delete_action(id)
        
        return dumps({"results":self.db.delete(id)})
    
    def delete_action(self,  pid):
        if self.adb.document_exists(pid):
            self.adb.delete(pid)

class GetRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        print args
        if not args:
            return dumps({"results":{}})
        return self.get_request(args[0])
    
    def get_request(self, data):
        return dumps({"results":self.db.get(prepid=data)})

class ApproveRequest(RESTResource):
    def __init__(self):
        self.db = database('requests')
    
    def GET(self,  *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return self.approve(args[0],  args[1])
        
    def approve(self,  rid,  val):
        if not self.db.document_exists(rid):
            return dumps({"results":'Error: The given request id does not exist.'})
        req = request('',  json_input=self.db.get(rid))
        if not req.approve(val):
            return dumps({"results":False})
        
        return dumps({"results":self.db.update(req.json())})

class InjectRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)

    def GET(self, *args):
        if not args:
            return dumps({"results":{}})
        return self.inject_request(args[0])

    def inject_request(self, id):
        pass  
