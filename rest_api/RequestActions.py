#!/usr/bin/env python

import cherrypy
import sys
from json import loads,dumps
from couchdb_layer.prep_database import database
from RestAPIMethod import RESTResource
from RequestPrepId import RequestPrepId
from json_layer.request import request
from json_layer.submission_details import submission_details
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

        self.logger.log('Building new request...')
        
        if '_id' in self.json and self.json['_id'] :
            self.json['prepid'] = self.json['_id'] 
        elif 'prepid' in self.json and self.json['prepid']:
            self.json['_id'] = self.json['prepid']
        else:
            self.json['_id'] = self.json['prepid'] = ''
        
        if self.db.document_exists(self.json['_id']):
            self.logger.error('prepid %s already exists. Generating another...' % (self.json['_id']), level='warning')
            
            id = RequestPrepId().generate_prepid(self.json['pwg'], self.json['member_of_campaign'])
            self.json['prepid'] = loads(id)['prepid']
        
            if not self.json['prepid']:
                self.logger.error('prepid returned was None')
                raise ValueError('Prepid returned was None')
            self.json['_id'] = self.json['prepid']

        self.logger.log('New prepid: %s' % (self.json['prepid']))     
            
        
        # global tag ::All fix
        i = 0
        for seq in self.json['sequences']:
            if '::All' not in seq['conditions']:
                self.json['sequences'][i]['conditions'] += '::All'
            i += 1
        
        # save to database
        if not self.db.save(self.json):
            self.logger.error('Could not save results to database')
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
            self.logger.error('prepid returned was None')
            raise ValueError('Prepid returned was None')

        self.logger.log('Updating request %s...' % (self.request.get_attribute('prepid')))
            
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
      if not args:
        self.logger.error('No arguments were given')
        return dumps({"results":'Error: No arguments were given.'})
      return self.get_cmsDriver(self.db.get(prepid=args[0]))

    def get_cmsDriver(self, data):
      try:
        self.request = request('TEST', json_input=data)
        #self.request.print_self()     
      except request.IllegalAttributeName as ex:
        return dumps({"results":''})
        
      return dumps({"results":self.request.build_cmsDrivers()}) 
      

class DeleteRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.adb = database('actions')
    
    def DELETE(self, *args):
        if not args:
            self.logger.error('No arguments were given')
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
        if not args:
            self.logger.error('No arguments were given')
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
        if len(args) == 1:
		return self.multiple_approve(args[0])
        return self.multiple_approve(args[0], int(args[1]))

    def multiple_approve(self, rid, val=-1):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                 res.append(self.approve(r, val))
            return dumps(res)
        else:
            return dumps(self.approve(rid, val))
        
    def approve(self,  rid,  val=-1):
        if not self.db.document_exists(rid):
            return {"prepid": rid, "results":'Error: The given request id does not exist.'}
        req = request('',  json_input=self.db.get(rid))
        if not req.approve(val):
            return {"prepid": rid, "results":False}

        hist = {}
        hist['updater'] = submission_details().build(cherrypy.request.headers['ADFS-LOGIN'])
        hist['action'] = sys._getframe().f_code.co_name
        hist['step'] = req.get_attribute('approvals')[-1]['approval_step']

        req.update_history(hist)

        return {"prepid" : rid, "results":self.db.update(req.json())}

class ResetRequestApproval(RESTResource):
    def __init__(self):
        self.db = database('requests')
    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        if len(args) < 2:
            return self.multiple_reset(args[0])
        return self.multiple_reset(args[0], int(args[1]))

    def multiple_reset(self, rid, val=0):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                 res.append(self.reset(r, val))
            return dumps(res)
        else:
            return dumps(self.reset(rid, val))


    def reset(self, rid, step=0):
        if not self.db.document_exists(rid):
            return {"prepid": rid, "results":'Error: The given request id does not exist.'}

        req = request('', json_input=self.db.get(rid))
        if step >= len(req.get_attribute('approvals')) - 1:
            return {"prepid": rid, "results":'Error: Cannot reset higher approval step'}

        if not req.approve(step):
            return {"prepid":rid, "results":False}

        hist = {}
        hist['updater'] = submission_details().build(cherrypy.request.headers['ADFS-LOGIN'])
        hist['action'] = sys._getframe().f_code.co_name
        hist['step'] = req.get_attribute('approvals')[-1]['approval_step']

        req.update_history(hist)

        return {"prepid": rid, "results":self.db.update(req.json())}

class SetStatus(RESTResource):
    def __init__(self):
        self.db = database('requests')

    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        if len(args) < 2:
            return self.multiple_status(args[0])
        return self.multiple_status(args[0], int(args[1]))

    def multiple_status(self, rid, val=-1):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                 res.append(self.status(r, val))
            return dumps(res)
        else:
            return dumps(self.status(rid, val))

    def status(self, rid, step=-1):
        if not self.db.document_exists(rid):
            return {"prepid": rid, "results":'Error: The given request id does not exist.'}

        req = request('', json_input=self.db.get(rid))

        if not req.add_status(step):
            return {"prepid": rid, "results":False}

        hist = {}
        hist['updater'] = submission_details().build(cherrypy.request.headers['ADFS-LOGIN'])
        hist['action'] = sys._getframe().f_code.co_name
        hist['step'] = req.get_attribute('status')

        req.update_history(hist)

        return {"prepid": rid, "results":self.db.update(req.json())}

class InjectRequest(RESTResource):
    def __init__(self):
        # set user access to administrator
        self.authenticator.set_limit(4)
        self.db_name = 'requests'
        self.db = database(self.db_name)

    def GET(self, *args):
        if not args:
            self.logger.error('No arguments were given') 
            return dumps({"results":'Error: No arguments were given'})
        return self.inject_request(args[0])

    def inject_request(self, id):
        try:
            from submitter.package_builder import package_builder
        except ImportError:
            self.logger.error('Could not import "package_builder" module.', level='critical')
            return dumps({"results":'Error: Could not import "package_builder" module.'})        
        req = self.db.get(id)
        pb = package_builder(req_json=req)
        return dumps({"results": str(pb.build_package())})
