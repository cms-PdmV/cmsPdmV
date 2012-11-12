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

class GetAction(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
            
        return self.get_request(args[0])
    
    def get_request(self, id):
        return dumps({"results":self.db.get(id)})

class SelectChain(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
            
        return self.select_chain(args[0],  args[1],  args[2])
    
    def select_chain(self, id,  chainid,  value):
        # if action exists
        if self.db.document_exists(id):
            # initialize the object
            a = action('test',  json_input=self.db.get(id))
            # and set it to 1 (default ?)
            a.select_chain(chainid,  int(value))
            
            # save
            self.db.update(a.json())
            return dumps({'results':True})
        else:
            return dumps({"results":False})

class DeSelectChain(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
            
        return self.deselect_chain(args[0],  args[1])
    
    def deselect_chain(self,  aid,  chainid):
        # if action exists
        if self.db.document_exists(aid):
            # initialize the object
            a = action('test',  json_input=self.db.get(aid))
            # and set it to 1 (default ?)
            a.deselect_chain(chainid)
            # save
            self.db.update(a.json())
            return dumps({'results':True})
        else:
            return dumps({"results":False})

class GenerateChainedRequests(RESTResource):
    def __init__(self):
        self.db = database('actions')
        self.ccdb = database('chained_campaigns')
        self.crdb = database('chained_requests')
    
    def GET(self,  *args):
        if not args:
            return dumps({'results':'Error: No arguments were given'})
        
        return self.generate_request(args[0])
    
    def generate_request(self,  id):
        if not self.db.document_exists(id):
            return dumps({'results':'Error: PrepId '+id+' does not exist in the database.'})
        
        # init action
        req = action('',  json_input=self.db.get(id))
                
        # get chains
        chains = req.get_attribute('chains')
        
        # iterate through chains
        for cc in chains:
            if chains[cc] > 0:
                # check if the chain already exists
                accs = map(lambda x: x['value'],  self.crdb.query('root_request=='+id))
                flag = False
                for acc in accs:
                    if cc == acc['_id'].split('-')[1]:
                        flag = True
                        break
                
                if flag:
                    print 'Warning: A chained request already exists for chained_campaign',  cc
                    continue
                
                # init chained campaign
                ccamp = chained_campaign('',  json_input=self.ccdb.get(cc))
                # create the chained request
                new_req = ccamp.generate_request(id)
                # save to database
                if not self.crdb.save(new_req):
                    print 'Error: Could not save '+str(id)+' to database.'
                    return dumps({'results':False})
                    
                self.ccdb.update(ccamp.json())
        
        return dumps({'results':True})

class GenerateAllChainedRequests(RESTResource):
    def __init__(self):
        self.db = database('actions')
        self.ccdb = database('chained_campaigns')
        self.crdb = database('chained_requests')
    
    def GET(self,  *args):
        return self.generate_requests()
        
    def generate_requests(self):
        allacs = self.db.get_all(-1) # no pagination
        for a in allacs:
            self.generate_request(a['key'])
        
        return dumps({'results':True})
            
    def generate_request(self,  id):
        if not self.db.document_exists(id):
            return dumps({'results':'Error: PrepId '+id+' does not exist in the database.'})
        
        # init action
        req = action('',  json_input=self.db.get(id))
                
        # get chains
        chains = req.get_attribute('chains')
        
        # iterate through chains
        for cc in chains:
            if chains[cc] > 0:
                # check if the chain already exists
                accs = map(lambda x: x['value'],  self.crdb.query('root_request=='+id))
                flag = False
                for acc in accs:
                    if cc == acc['_id'].split('-')[1]:
                        flag = True
                        break
                
                if flag:
                    print 'Warning: A chained request already exists for chained_campaign',  cc
                    continue
                
                # init chained campaign
                ccamp = chained_campaign('',  json_input=self.ccdb.get(cc))
                # create the chained request
                new_req = ccamp.generate_request(id)
                # save to database
                if not self.crdb.save(new_req):
                    print 'Error: Could not save '+str(id)+' to database.'
                    return dumps({'results':False})
                    
                self.ccdb.update(ccamp.json())
        
        return dumps({'results':True})
            
        
class DetectChains(RESTResource):
    def __init__(self):
        self.db = database('actions')
    
    def GET(self,  *args):
        if not args:
            return self.find_all_chains()
        return self.find_chains(args[0])
    
    def find_chains(self,  aid):
        ac = action('',  json_input=self.db.get(aid))
        ac.find_chains()
        return dumps({'results':self.db.update(ac.json())})
    
    def find_all_chains(self):
        try:
            map(lambda x: self.find_chains(x['key']),  self.db.get_all(-1))
        except Exception as ex:
            return dumps({'results': str(ex)})
        return dumps({'results': True})
        
