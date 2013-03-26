#!/usr/bin/env python

import cherrypy
import sys
import traceback
from json import loads,dumps
from couchdb_layer.prep_database import database
from RestAPIMethod import RESTResource
from RequestPrepId import RequestPrepId
from json_layer.json_base import json_base
from json_layer.request import request
from json_layer.action import action
from json_layer.generator_parameters import generator_parameters

class ImportRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.adb = database('actions')
        self.cdb = database('campaigns')
        self.request = None

    def PUT(self):
        return self.import_request(cherrypy.request.body.read().strip())

    ## duplicate version to be centralized in a unique class
    def add_action(self):
        # Check to see if the request is a root request
        #camp = self.request.get_attribute('member_of_campaign')
          
        #if not self.cdb.document_exists(camp):
        #    return dumps({"results":'Error: Campaign '+str(camp)+' does not exist.'})
                
        # get campaign
        #self.c = self.cdb.get(camp)
        
        if (self.campaign['root'] > 0) or (self.campaign['root'] <=0 and int(self.request.get_attribute('mcdb_id')) > -1):
            ## c['root'] > 0 
            ##            :: not a possible root --> no action in the table
            ## c['root'] <=0 and self.request.get_attribute('mcdb_id') > -1 
            ##            ::a possible root and mcdbid=0 (import from WMLHE) or mcdbid>0 (imported from PLHE) --> no action on the table
            if self.adb.document_exists(self.request.get_attribute('prepid')):
                ## check that there was no already inserted actions, and remove it in that case
                self.adb.delete(self.request.get_attribute('prepid'))
            return
        
        # check to see if the action already exists
        if not self.adb.document_exists(self.request.get_attribute('prepid')):
            # add a new action
            a= action('automatic')
            a.set_attribute('prepid',  self.request.get_attribute('prepid'))
            a.set_attribute('_id',  a.get_attribute('prepid'))
            a.set_attribute('member_of_campaign',  self.request.get_attribute('member_of_campaign'))
            a.find_chains()
            self.logger.log('Adding an action for %s'%(self.request.get_attribute('prepid')))
            self.adb.save(a.json())

    def import_request(self, data):
        try:
            self.request = request(json_input=loads(data))
        except request.IllegalAttributeName as ex:
            return dumps({"results":False})

        self.logger.log('Building new request...')

	# set '_id' and 'prepid' fields
        if self.request.get_attribute('_id') :
            self.request.set_attribute('prepid', self.request.get_attribute('_id')) 
        elif self.request.get_attribute('prepid'):
            self.request.set_attribute('_id', self.request.get_attribute('prepid'))
        else:
            self.request.set_attribute('_id', '')
            self.request.set_attribute('prepid','')
        
        ##N.B (JR), '' is always an existing document
        if self.db.document_exists(self.request.get_attribute('_id')):
            self.logger.error('prepid %s already exists. Generating another...' % (self.request.get_attribute('_id')), level='warning')
            
            id = RequestPrepId().generate_prepid(self.request.get_attribute('pwg'), self.request.get_attribute('member_of_campaign'))
            self.request.set_attribute('prepid', loads(id)['prepid'])
        
            if not self.request.get_attribute('prepid'):
                self.logger.error('prepid returned was None')
                raise ValueError('Prepid returned was None')
            self.request.set_attribute('_id', self.request.get_attribute('prepid'))

        self.logger.log('New prepid: %s' % (self.request.get_attribute('prepid')))     

        

        # check that the campaign it belongs to exsits
        camp = self.request.get_attribute('member_of_campaign')
        if not self.cdb.document_exists(camp):
            return dumps({"results":'Error: Campaign '+str(camp)+' does not exist.'})
        ## get campaign                                                                                                                 
        self.campaign = self.cdb.get(camp)

        ## put a generator info by default in case of possible root request
        if self.campaign['root'] <=0:
            self.request.update_generator_parameters()
            
        ##cast the campaign parameters into the request: knowing that those can be edited at will later
        self.request.build_cmsDrivers(cast=1)

        #c = self.cdb.get(camp)
        #tobeDraggedInto = ['cmssw_release','pileup_dataset_name']
        #for item in tobeDraggedInto:
        #    self.request.set_attribute(item,c.get_attribute(item))
        #nSeq=len(c.get_attribute('sequences'))
        #self.request.
            
        # update history
        self.request.update_history({'action':'created'})

        # save to database
        if not self.db.save(self.request.json()):
            self.logger.error('Could not save results to database')
            return dumps({"results":False})
        
        # add an action to the action_db
        self.add_action()

        return dumps({"results":self.request.get_attribute('_id')})
        
class UpdateRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.adb = database('actions')
        self.cdb = database('campaigns')
        self.request = None
        
    def PUT(self):
        return self.update_request(cherrypy.request.body.read().strip())

    ## duplicate version to be centralized in a unique class
    def add_action(self):
        # Check to see if the request is a root request
        camp = self.request.get_attribute('member_of_campaign')
          
        if not self.cdb.document_exists(camp):
            return dumps({"results":'Error: Campaign '+str(camp)+' does not exist.'})
                
        # get campaign
        c = self.cdb.get(camp)
        
        if (c['root'] ==1) or (c['root'] ==-1 and self.request.get_attribute('mcdb_id') > -1):
            ## c['root'] ==1
            ##            :: not a possible root --> no action in the table
            ## c['root'] ==-1 and self.request.get_attribute('mcdb_id') > -1 
            ##            ::a possible root and mcdbid=0 (import from WMLHE) or mcdbid>0 (imported from PLHE) --> no action on the table
            if self.adb.document_exists(self.request.get_attribute('prepid')):
                ## check that there was no already inserted actions, and remove it in that case
                self.adb.delete(self.request.get_attribute('prepid'))
            return
        
        # check to see if the action already exists
        if not self.adb.document_exists(self.request.get_attribute('prepid')):
            # add a new action
            a= action()##JR ?? 'automatic')
            a.set_attribute('prepid',  self.request.get_attribute('prepid'))
            a.set_attribute('_id',  a.get_attribute('prepid'))
            a.set_attribute('member_of_campaign',  self.request.get_attribute('member_of_campaign'))
            a.set_attribute('dataset_name', self.request.get_attribute('dataset_name'))
            a.find_chains()
            self.logger.log('Adding an action for %s'%(self.request.get_attribute('prepid')))
            self.adb.save(a.json())
        else:
            ## propagating the dataset_name: over saving object ?
            a = action(self.adb.get(self.request.get_attribute('prepid')))
            a.set_attribute('dataset_name', self.request.get_attribute('dataset_name'))
            self.adb.save(a.json())

    def update_request(self, data):
        if '"_rev"' not in data:
                self.logger.error('Could not locate the CouchDB revision number in object: %s' % (data))
		return dumps({"results":False})
        try:
                self.request = request(json_input=loads(data))
        except request.IllegalAttributeName as ex:
                return dumps({"results":False})

        if not self.request.get_attribute('prepid') and not self.request.get_attribute('_id'):
            self.logger.error('prepid returned was None')
            raise ValueError('Prepid returned was None')

        self.logger.log('Updating request %s...' % (self.request.get_attribute('prepid')))

        # check on the action 
        self.add_action()
        	
	# update history
	self.request.update_history({'action': 'update'})
            
        return self.save_request()

    def save_request(self):
        return dumps({"results":self.db.update(self.request.json())})

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
      cast=0
      if len(args)>1:
          cast=int(args[1])
      return self.get_cmsDriver(self.db.get(prepid=args[0]),cast)

    def get_cmsDriver(self, data, cast):
      try:
        self.request = request(json_input=data)
      except request.IllegalAttributeName as ex:
        return dumps({"results":''})
        
      return dumps({"results":self.request.build_cmsDrivers(cast=cast)}) 
      
class GetFragmentForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)

    def GET(self, *args):
      if not args:
        self.logger.error('No arguments were given')
        return dumps({"results":'Error: No arguments were given.'})
      v=True
      if len(args)>1:
          v=False
      return self.get_fragment(self.db.get(prepid=args[0]),v)

    def get_fragment(self, data, view):
      try:
        self.request = request(json_input=data)
      except request.IllegalAttributeName as ex:
        return dumps({"results":''})
      
      fragmentText=self.request.get_attribute('fragment')
      if view:
          fragmentHTML=""
          for line in fragmentText.split('\n'):
              blanks=""
              while line.startswith(' '):
                  blanks+="&nbsp;"
                  line=line[1:]
              line=blanks+line
              fragmentHTML+=line.replace("\t","&nbsp;&nbsp;&nbsp;&nbsp;")+"<br>"
          return fragmentHTML
      else:
          return fragmentText
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
        req = request(json_input=self.db.get(rid))

	self.logger.log('Approving request %s for step "%s"' % (rid, val))

        #req.approve(val)
	try:
        	req.approve(val)
	except request.WrongApprovalSequence as ex:
            return {'prepid': rid, 'results':False, 'message' : str(ex)}
        except request.WrongStatusSequence as ex:
            return {"prepid":rid, "results":False, 'message' : str(ex)}
        except:
            return {'prepid': rid, 'results':False, 'message' : 'Unknonw error'}
	
        return {'prepid' : rid, 'approval' : req.get_attribute('approval') ,'results':self.db.update(req.json())}

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

        req = request(json_input=self.db.get(rid))

        appsteps = req.get_approval_steps()
        app = req.get_attribute('approval')

        if step > appsteps.index(app):
            return {"prepid": rid, "results":'Error: Cannot reset higher approval step %s:%s -> %s'%(app,appsteps.index(app),step)}

        try:
            req.approve(step)
            if step==0:
                req.set_status(0)
        except request.WrongApprovalSequence as ex:
            return {"prepid":rid, "results":False, 'message' : str(ex)}
        except request.WrongStatusSequence as ex:
            return {"prepid":rid, "results":False, 'message' : str(ex)}
        except:
            return {"prepid":rid, "results":False, 'message' : 'Unknow error'}

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

        req = request(json_input=self.db.get(rid))

        try:
            req.set_status(step)
        except request.WrongStatusSequence as ex:
            return {"prepid":rid, "results":False, 'message' : str(ex)}
        except:
            return {"prepid":rid, "results":False, 'message' : 'Unknow error'}

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
        
        return self.inject_request(ids=args[0])

    def inject_request(self, ids):
        try:
            from submitter.package_builder import package_builder
        except ImportError:
            self.logger.error('Could not import "package_builder" module.', level='critical')
            return dumps({"results":'Error: Could not import "package_builder" module.'})        

        res=[]
        for pid in ids.split(','):
            req = request(self.db.get(pid))
            if req.get_attribute('status')!='approved':
                res.append({"prepid": pid, "results": False,"message":"The request is in status %s, while approved is required"%(req.get_attribute('status'))})
                continue
            if not req.get_attribute('member_of_chain'):
                res.append({"prepid": pid, "results": False,"message":"The request is not member of any chain"})
                continue

            pb=None
            try:
                pb = package_builder(req_json=req.json())
            except:
                message = "Errors in making the request : \n"+ traceback.format_exc()
                self.logger.error(message)
                res.append({"prepid": pid, "results" : message})
                continue
            try:
                res_sub=str(pb.build_package())
            except:
                message = "Errors in building the request : \n"+ traceback.format_exc()
                self.logger.error(message)
                res.append({"prepid": pid, "results" : message})
                continue

            res.append({"results": res_sub})
            # update history
            req.update_history({'action':'inject'})
        if len(res)>1:
            return dumps(res)
        else:
            return dumps(res[0])


class GetEditable(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)

    def GET(self, *args):
        if not args:
            self.logger.error('Request/GetEditable: No arguments were given')
            return dumps({"results":'Error: No arguments were given'})
        return self.get_editable(args[0])

    def get_editable(self, prepid):
        request_in_db = request(self.db.get(prepid=prepid))
        editable= request_in_db.get_editable()
        return dumps({"results":editable})
        
class GetDefaultGenParams(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)

    def GET(self, *args):
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given'})

        return self.get_default_params(args[0])

    def get_default_params(self,prepid):
        request_in_db = request(self.db.get(prepid=prepid))
        request_in_db.update_generator_parameters()
        return dumps({"results":request_in_db.get_attribute('generator_parameters')[-1]})
