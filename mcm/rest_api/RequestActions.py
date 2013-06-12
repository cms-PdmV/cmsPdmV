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
from json_layer.campaign import campaign
from json_layer.generator_parameters import generator_parameters
from threading import Thread
from submitter.package_builder import package_builder

class RequestRESTResource(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.adb = database('actions')
        self.cdb = database('campaigns')
        self.request = None
        self.access_limit = 1
        self.with_trace = True

    def set_campaign(self):
        # check that the campaign it belongs to exsits
        camp = self.request.get_attribute('member_of_campaign')
        if not self.cdb.document_exists(camp):
            return dumps({"results":'Error: Campaign '+str(camp)+' does not exist.'})
        ## get campaign                   
        self.campaign = self.cdb.get(camp)

    ## duplicate version to be centralized in a unique class
    def add_action(self,force=False):
        # Check to see if the request is a root request
        #camp = self.request.get_attribute('member_of_campaign')
          
        #if not self.cdb.document_exists(camp):
        #    return dumps({"results":'Error: Campaign '+str(camp)+' does not exist.'})
                
        # get campaign
        #self.c = self.cdb.get(camp)
        
        if (not force) and ((self.campaign['root'] > 0) or (self.campaign['root'] <0 and int(self.request.get_attribute('mcdb_id')) > -1)):
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
            #a= action('automatic')
            a= action()
            a.set_attribute('prepid',  self.request.get_attribute('prepid'))
            a.set_attribute('_id',  a.get_attribute('prepid'))
            a.set_attribute('dataset_name', self.request.get_attribute('dataset_name'))
            a.set_attribute('member_of_campaign',  self.request.get_attribute('member_of_campaign'))
            a.find_chains()
            self.logger.log('Adding an action for %s'%(self.request.get_attribute('prepid')))
            self.adb.save(a.json())
        else:
            a=action(self.adb.get(self.request.get_attribute('prepid')))
            if a.get_attribute('dataset_name') != self.request.get_attribute('dataset_name'):
                a.set_attribute('dataset_name', self.request.get_attribute('dataset_name'))
                self.logger.log('Updating an action for %s'%(self.request.get_attribute('prepid')))
                self.adb.save(a.json())

    def import_request(self, data):

        if '_rev' in data:
            return dumps({"results":False, 'message' : 'could not save object with a revision number in the object'})

        try:
            #self.request = request(json_input=loads(data))
            self.request = request(json_input=data)
        except request.IllegalAttributeName as ex:
            return dumps({"results":False})

        self.set_campaign()
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

        

        ## put a generator info by default in case of possible root request
        if self.campaign['root'] <=0:
            self.request.update_generator_parameters()
            
        ##cast the campaign parameters into the request: knowing that those can be edited at will later
        if not self.request.get_attribute('sequences'):
            self.request.build_cmsDrivers(cast=1)

        #c = self.cdb.get(camp)
        #tobeDraggedInto = ['cmssw_release','pileup_dataset_name']
        #for item in tobeDraggedInto:
        #    self.request.set_attribute(item,c.get_attribute(item))
        #nSeq=len(c.get_attribute('sequences'))
        #self.request.
            
        # update history
        if self.with_trace:
            self.request.update_history({'action':'created'})

        # save to database
        if not self.db.save(self.request.json()):
            self.logger.error('Could not save results to database')
            return dumps({"results":False})
        
        # add an action to the action_db
        self.add_action()

        return dumps({"results":self.request.get_attribute('_id')})

    
class CloneRequest(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)
        self.access_limit = 1 ## maybe that is wrong

    def GET(self, *args):
        """
        Make a clone with no special requirement
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given.'})
        return self.clone_request(args[0])

    def PUT(self):
        """
        Make a clone with specific requirements
        """
        data=loads(cherrypy.request.body.read().strip())
        pid=data['prepid']
        return self.clone_request(pid,data)

    def clone_request(self, pid,data={}):
        new_pid=None
        
        if self.db.document_exists(pid):
            new_json = self.db.get(pid)
            new_json.update(data)
            del new_json['_id']
            del new_json['_rev']
            del new_json['prepid']
            del new_json['approval']
            del new_json['status']
            del new_json['history']
            del new_json['config_id']
            del new_json['member_of_chain']
            new_json['version']=0
            del new_json['generator_parameters']
            del new_json['reqmgr_name']
            

            return self.import_request(new_json)
            #new_pid = self.import_request(new_json)['results']

        if new_pid:
            return dumps({"results":True,"prepid":new_pid})
        else:
            return dumps({"results":False})

    
class ImportRequest(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)
        self.access_limit = 1 ## maybe that is wrong
        
    def PUT(self):
        """
        Saving a new request from a given dictionnary
        """
        return self.import_request(loads(cherrypy.request.body.read().strip()))


class UpdateRequest(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)
        
    def PUT(self):
        """
        Updating an existing request with an updated dictionnary
        """
        return self.update()

    def update(self):
        try:
            res=self.update_request(cherrypy.request.body.read().strip())
            return res
        except:
            self.logger.error('Failed to update a request from API')
            return dumps({'results':False,'message':'Failed to update a request from API'})

    def update_request(self, data):
        data = loads (data)
        if '_rev' not in data:
                self.logger.error('Could not locate the CouchDB revision number in object: %s' % (data))
		return dumps({"results":False, 'message' : 'could not locate revision number in the object'})
        
        if not self.db.document_exists( data['_id'] ):
            return dumps({"results":False, 'message' : 'request %s does not exist'%( data['_id']) })
        else:
            if self.db.get(data['_id']) ['_rev'] != data['_rev']:
                return dumps({"results":False, 'message' : 'revision clash'})

        try:
                self.request = request(json_input=data)
        except request.IllegalAttributeName as ex:
                return dumps({"results":False, 'message' : 'Mal-formatted request json in input'})
        
        

        if not self.request.get_attribute('prepid') and not self.request.get_attribute('_id'):
            self.logger.error('prepid returned was None')
            raise ValueError('Prepid returned was None')

        ## operate a check on whether it can be changed
        previous_version =  request(self.db.get(self.request.get_attribute('prepid')))
        editable = previous_version.get_editable()
        for (key,right) in editable.items():
            #self.logger.log('%s: %s vs %s : %s'%(key,previous_version.get_attribute(key),self.request.get_attribute(key),right))
            if (previous_version.get_attribute(key) != self.request.get_attribute(key)) and right==False:
                self.logger.error('Illegal change of parameter, %s: %s vs %s : %s'%(key,previous_version.get_attribute(key),self.request.get_attribute(key),right))
                return dumps({"results":False,'message':'Illegal change of parameter'})
                #raise ValueError('Illegal change of parameter')
        

        self.logger.log('Updating request %s...' % (self.request.get_attribute('prepid')))

        if len(self.request.get_attribute('history')) and 'action' in self.request.get_attribute('history')[0] and self.request.get_attribute('history')[0]['action'] == 'migrated':
            self.logger.log('Not changing the actions for %s as it has been migrated'%(self.request.get_attribute('prepid')))
            pass
        else:
            # check on the action 
            self.set_campaign()
            self.add_action()
        	
	# update history
        if self.with_trace:
            self.request.update_history({'action': 'update'})
        return  self.save_request()

    def save_request(self):
        return dumps({"results":self.db.update(self.request.json())})

class ManageRequest(UpdateRequest):
    """
    Same as UpdateRequest, leaving no trace in history, for admin only
    """
    def __init__(self):
        UpdateRequest.__init__(self)
        self.access_limit = 4
        self.with_trace = False
    def PUT(self):
        """
        Updating an existing request with an updated dictionnary, leaving no trace in history, for admin only
        """
        return self.update()

class MigratePage(RequestRESTResource):
    def __init__(self):  
        RequestRESTResource.__init__(self)       
        
    def GET(self, *args):
        """
        Provides a page to migrate requests from prep
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":False,"message":'Error: No arguments were given.'})
        prep_campaign=args[0]
        html='<html><body>This is the migration page for %s'%(prep_campaign)
        html+='</body></html>'
        return html
    
class MigrateRequest(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)

    def GET(self, *args):
        """
        Imports a request from prep (id provided)
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":False,"message":'Error: No arguments were given.'})
        return self.migrate_from_prep(args[0])

    def migrate_from_prep(self,pid):

        ## get the campaign name
        prep_campaign=pid.split('-')[1]
        mcm_campaign = prep_campaign.replace('_','')
        
        if not self.cdb.document_exists(mcm_campaign):
            return dumps({"results":False,"message":'no campaign %s exists in McM to migrate %s'%(mcm_campaign,pid)})
        camp = campaign(self.cdb.get(mcm_campaign))

        from sync.get_request import prep_scraper
        prep = prep_scraper()
        mcm_requests = prep.get(pid)
        if not len(mcm_requests):
            return dumps({"results":False,"message":"no conversions for prepid %s"%(pid)})
        mcm_request= mcm_requests[0]
        try:
            self.request = mcm_r = request(mcm_request)
        except:
            return dumps({"results":False,"message":"json does not cast into request type <br> %s"%(mcm_request)})

        ## make the sequences right ? NO, because that cast also the conditions ...
        #mcm_r.build_cmsDrivers(cast=-1)
        #mcm_r.build_cmsDrivers(cast=1)

        mcm_r.update_history({'action':'migrated'})
        if not self.db.document_exists(mcm_r.get_attribute('prepid')):
            mcm_r.get_stats(override_id = pid)

            if not len(mcm_r.get_attribute('reqmgr_name')):
                # no requests provided, the request should fail migration. 
                # I have put fake docs in stats so that it never happens
                return dumps({"results":False,"message":"Could not find an entry in the stats DB for prepid %s"%(pid)})

            # set the completed events properly
            if mcm_r.get_attribute('status') == 'done' and len(mcm_r.get_attribute('reqmgr_name')) and mcm_r.get_attribute('completed_events')<=0:
                mcm_r.set_attribute('completed_events', mcm_r.get_attribute('reqmgr_name')[-1]['content']['pdmv_evts_in_DAS'])
                
            
            saved = self.db.save(mcm_r.json())

            ## force to add an action on those requests
            #it might be that later on, upon update of the request that the action get deleted
            if camp.get_attribute('root') <=0:
                self.set_campaign()
                self.add_action(force=True)            
        else:
            return dumps({"results":False,"message":"prepid %s already exists as %s in McM"%(pid, mcm_r.get_attribute('prepid'))})

        if saved:
            html='<html><body>Request migrated from PREP (<a href="http://cms.cern.ch/iCMS/jsp/mcprod/admin/requestmanagement.jsp?code=%s" target="_blank">%s</a>) to McM (<a href="/mcm/requests?prepid=%s&page=0" target="_blank">%s</a>)</body></html>'%(pid,pid,
                                                                                                                                                                                                                                                                          mcm_r.get_attribute('prepid'),mcm_r.get_attribute('prepid'))
            return html
            return dumps({"results":saved,"message":"Request migrated from PREP (%s) to McM (%s)"%(pid,mcm_r.get_attribute('prepid'))})
        else:
            return dumps({"results":saved,"message":"could not save converted prepid %s in McM"%(pid)})

        #return dumps({"results":True,"message":"not implemented"})


class GetCmsDriverForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.json = {}
        self.request = None

    def GET(self, *args):
        """
        Retrieve the cmsDriver commands for a given request
        """
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
      """
      Retrieve the fragment as stored for a given request
      """
      if not args:
        self.logger.error('No arguments were given')
        return dumps({"results":'Error: No arguments were given.'})
      v=False
      if len(args)>1:
          v=True
      return self.get_fragment(self.db.get(prepid=args[0]),v)

    def get_fragment(self, data, view):
      try:
        self.request = request(json_input=data)
      except request.IllegalAttributeName as ex:
        return dumps({"results":''})
      
      fragmentText=self.request.get_attribute('fragment')
      if view:
          fragmentHTML="<pre>"
          fragmentHTML+=fragmentText
          fragmentHTML+="</pre>"
          return fragmentHTML
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

class GetSetupForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)

    def GET(self, *args):
      """
      Retrieve the script necessary to setup and test a given request
      """
      if not args:
        self.logger.error('No arguments were given')
        return dumps({"results":'Error: No arguments were given.'})
      pid = args[0]
      if self.db.document_exists(pid):
          return self.get_fragment(self.db.get(prepid=pid))
      else:
          return dumps({"results":False,"message":"%s does not exists"%(pid)})

    def get_fragment(self, data):
      try:
        self.request = request(json_input=data)
      except request.IllegalAttributeName as ex:
        return dumps({"results":False})
      
      setupText = self.request.get_setup_file()
      return setupText

class DeleteRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.adb = database('actions')
        self.crdb = database('chained_requests')

    def DELETE(self, *args):
        """
        Simply delete a request
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":False})
        return self.delete_request(args[0])
    
    def delete_request(self, pid):
        # delete actions !
        self.delete_action(pid)
        
        # delete chained requests !
        #self.delete_chained_requests(self,pid):

        return dumps({"results":self.db.delete(pid)})
    
    def delete_action(self,  pid):
        if self.adb.document_exists(pid):
            self.adb.delete(pid)

    def delete_chained_requests(self, pid):
        mcm_crs = map(lambda x: x['value'], self.crdb.query('contains=='+pid))
        for doc in mcm_crs:
            self.crdb.delete(doc['prepid'])

class GetRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        """
        Retreive the dictionnary for a given request
        """
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
        """
        Approve to the next step, or specified index the given request or coma separated list of requests
        """
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
            if val==0:
                req.set_attribute('completed_events', 0)
                req.set_attribute('reqmgr_name',[])
                req.set_attribute('config_id',[])
                req.set_status(step=val,with_notification=True)

	except request.WrongApprovalSequence as ex:
            return {'prepid': rid, 'results':False, 'message' : str(ex)}
        except request.WrongStatusSequence as ex:
            return {"prepid":rid, "results":False, 'message' : str(ex)}
        except request.IllegalApprovalStep as ex:
            return {"prepid":rid, "results": False, 'message' : str(ex)}
        except:
            return {'prepid': rid, 'results':False, 'message' : traceback.format_exc()}
	
        return {'prepid' : rid, 'approval' : req.get_attribute('approval') ,'results':self.db.update(req.json())}

class ResetRequestApproval(ApproveRequest):
    def __init__(self):
        ApproveRequest.__init__(self)
        
    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return self.multiple_approve(args[0], 0)

class GetStatus(RESTResource):
    def __init__(self):
        self.db = database('requests')

    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})

        return self.multiple_status(args[0])

    def multiple_status(self, rid):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                 res.append(self.status(r))
            return dumps(res)
        else:
            return dumps(self.status(rid))

    def status(self, rid):
        if not self.db.document_exists(rid):
            return {"prepid": rid, "results":'Error: The given request id does not exist.'}

        req = request(json_input=self.db.get(rid))

        #return {"prepid":rid, "results":req.get_attribute('status')}
        return {rid: req.get_attribute('status')}

class InspectStatus(RESTResource):
    def __init__(self):
        self.db = database('requests')
        self.access_limit = 3

    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return self.multiple_inspect(args[0])

    def multiple_inspect(self, rid):
        rlist=rid.rsplit(',')
        res = []
        for r in rlist:
            mcm_r = request( self.db.get( r ) )
            if mcm_r:
                res.append( mcm_r.inspect() ) 
            else:
                res.append( {"prepid": r, "results":False, 'message' : '%s does not exists'%(r)})
        if len(res)>1:
            return dumps(res)
        else:
            return dumps(res[0])


class SetStatus(RESTResource):
    def __init__(self):
        self.db = database('requests')
        self.access_limit = 3

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
            ## set the status with a notification if done via the rest api
            req.set_status(step,with_notification=True)
        except request.WrongStatusSequence as ex:
            return {"prepid":rid, "results":False, 'message' : str(ex)}
        except:
            return {"prepid":rid, "results":False, 'message' : 'Unknow error'+traceback.format_exc()}

        return {"prepid": rid, "results":self.db.update(req.json())}

class TestRequest(RESTResource):
    ## a rest api to make a creation test of a request
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        

class InjectRequest(RESTResource):
    def __init__(self):
        # set user access to administrator
        self.authenticator.set_limit(4)
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.access_limit = 3

    class INJECTOR(Thread):
        def __init__(self,pid,log,how_far=None):
            Thread.__init__(self)
            self.logger = log
            self.db = database('requests')
            self.act_on_pid=[]
            self.res=[]
            self.how_far = how_far
            if not self.db.document_exists(pid):
                self.res.append({"prepid": pid, "results": False,"message":"The request %s does not exist"%(pid)})
                return
            req = request(self.db.get(pid))
            if req.get_attribute('status')!='approved':
                self.res.append({"prepid": pid, "results": False,"message":"The request is in status %s, while approved is required"%(req.get_attribute('status'))})
                return
            if req.get_attribute('approval')!='submit':
                self.res.append({"prepid": pid, "results": False,"message":"The request is in approval %s, while submit is required"%(req.get_attribute('approval'))})
                return
            if not req.get_attribute('member_of_chain'):
                self.res.append({"prepid": pid, "results": False,"message":"The request is not member of any chain"})
                return

            self.act_on_pid.append(pid)
            ## this is a line that allows to brows back the logs efficiently
            self.logger.inject('## Logger instance retrieved', level='info', handler = pid)

            self.res.append({"prepid": pid, "results": True, "message":"The request %s is being forked"%(pid)})

        def run(self):
            if len(self.act_on_pid):
                self.res=[]
            for pid in self.act_on_pid:
                req = request(self.db.get(pid))
                pb=None
                try:
                    pb = package_builder(req_json=req.json())
                except:
                    message = "Errors in making the request : \n"+ traceback.format_exc()
                    self.logger.inject(message, handler = pid)
                    self.logger.error(message)
                    self.res.append({"prepid": pid, "results" : False, "message": message})
                    req.test_failure(message)
                    continue
                try:
                    res_sub=pb.build_package()
                except:
                    message = "Errors in building the request : \n"+ traceback.format_exc()
                    self.logger.inject(message, handler = pid)
                    self.logger.error(message)
                    self.res.append({"prepid": pid, "results" : False , "message": message})
                    req.test_failure(message)
                    continue

                self.res.append({"prepid": pid,"results": res_sub})
                # update history : was done already inside build_package
                ##req.update_history({'action':'inject'})
                
        def status(self):
            return self.res

    def GET(self, *args):
        if not args:
            self.logger.error('No arguments were given') 
            return dumps({"results":'Error: No arguments were given'})
        
        res=[]
        forking=(len(args)>1)
        forks=[]
        ids=args[0].split(',')
        for pid in ids:
            forks.append(self.INJECTOR(pid,self.logger))
            if forking:
                self.logger.log('Forking the injection of request %s ' % (pid))
                res.extend(forks[-1].status())
                ##forks the process directly
                forks[-1].start()
            else:
                ##makes you wait until it goes
                self.logger.log('Running the injection of request %s ' % (pid))
                forks[-1].run()
                res.extend(forks[-1].status())
        
        if len(res)>1:
            return dumps(res)
        elif len(res)==0:
            return dumps({"results":False})
        else:
            return dumps(res)

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

class NotifyUser(RESTResource):
    def __init__(self):
        self.rdb = database('requests')

    def PUT(self):
        data = loads(cherrypy.request.body.read().strip())
        # read a message from data
        message = data['message']
        pids = data['prepids']
        results=[]
        for pid in pids:
            if not self.rdb.document_exists(pid):
                return results.append({"prepid" : pid,"results":False,"message":"%s does not exists"%(pid)})
        
            req = request(self.rdb.get(pid))
            # notify the actors of the request
            req.notify('Communication about request %s'%(pid),
                       message)
            # update history with "notification"
            req.update_history({'action':'notify','step':message})
            if not self.rdb.save(req.json()):
                return results.append({"prepid" : pid, "results":False,"message":"Could not save %s"%(pid)})
            
            results.append({"prepid" : pid,"results":True,"message":"Notification send for %s"%(pid)})
        return dumps(results)
    

class RegisterUser(RESTResource):
    def __init__(self):
        self.rdb = database('requests')
        self.udb = database('users')

    def GET(self, *args):
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":False, 'message':'Error: No arguments were given'})
        return self.multiple_register( args[0]) ;

    def multiple_register(self, rid):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                 res.append(self.register_user(r))
            return dumps(res)
        else:
            return dumps(self.register_user(rid))
    
    def register_user(self,pid):
        request_in_db = request(self.rdb.get(pid))
        current_user = request_in_db.current_user
        if not current_user or not self.udb.document_exists(current_user):
            return {"prepid" : pid, "results":False,'message':"You (%s) are not a registered user to McM, correct this first"%(current_user)}

        if current_user in request_in_db.get_actors():
            return {"prepid" : pid, "results":False,'message':"%s already in the list of people for notification of %s"%(current_user,pid)}
        
        self.logger.error('list of users %s'%(request_in_db.get_actors()))
        self.logger.error('current actor %s'%(current_user))

        request_in_db.update_history({'action':'register','step':current_user})
        self.rdb.save(request_in_db.json())
        return {"prepid" : pid, "results":True,'message':'You (%s) are registered to %s'%(current_user,pid)}

class GetActors(RESTResource):
    def __init__(self):
        self.rdb = database('requests')
        
    def GET(self, *args):
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":False, 'message':'Error: No arguments were given'})
        if len(args)>1:
            return self.show_user(args[0],args[1])
        return self.show_user(args[0])

    def show_user(self,pid,what=None):
        request_in_db = request(self.rdb.get(pid))
        if what:
            return dumps(request_in_db.get_actors(what=what))
        else:
            return dumps(request_in_db.get_actors())

