#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from couchdb_layer.prep_database import database
from RestAPIMethod import RESTResource
from RequestPrepId import RequestPrepId
from json_layer.campaign import campaign
from json_layer.request import request
from json_layer.chained_campaign import chained_campaign
from json_layer.flow import flow

class CreateCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'campaigns'
        self.db = database(self.db_name)
        self.cdb = database('chained_campaigns')
        self.campaign = None

    def PUT(self):
        return self.create_campaign(cherrypy.request.body.read().strip())

    def create_campaign(self, data):
        try:
            self.campaign = campaign(json_input=loads(data))
        except campaign.IllegalAttributeName as ex:
            return dumps({"results":False})

        #id = RequestPrepId().generate_prepid(self.json['pwg'], self.json['member_of_campaign'])
        #self.json['prepid'] = loads(id)['prepid']
        if not self.campaign.get_attribute('prepid'):
            self.logger.error('Invalid prepid: Prepid returned None')
            return dumps({"results":False})

        if '_' in self.campaign.get_attribute('prepid'):
            self.logger.error('Invalid campaign name %s'%(self.campaign.get_attribute('prepid')))
            return dumps({"results":False})

        self.campaign.set_attribute('_id', self.campaign.get_attribute('prepid'))

        self.campaign.update_history({'action':'created'})
       
        # save to db
        if not self.db.save(self.campaign.json()):
            self.logger.error('Could not save object to database')
            return dumps({"results":False})
        
        # create dedicated chained campaign
        self.create_chained_campaign(self.campaign.get_attribute('_id'),  self.campaign.get_attribute('energy'))

        return dumps({"results":True})
    
    # creates a chained campaign containing only the given campaign
    def create_chained_campaign(self,  cid,  energy=-1):
	if self.db.get(cid)['root'] < 1:
	        dcc = chained_campaign()
        	dcc.set_attribute('prepid', 'chain_'+cid)
	        dcc.set_attribute('_id',  dcc.get_attribute('prepid'))
        	#dcc.set_attribute('energy',  energy)
	        dcc.add_campaign(cid) # flow_name = None
        	self.cdb.save(dcc.json())

class UpdateCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'campaigns'
        self.db = database(self.db_name)
        self.request = None
        
    def PUT(self):
        return self.update_request(cherrypy.request.body.read().strip())

    def update_request(self, data):
        try:
            self.request = campaign(json_input=loads(data))
        except campaign.IllegalAttributeName as ex:
            return dumps({"results":False})
        
        if not self.request.get_attribute('prepid') and not self.request.get_attribute('_id'):
            raise ValueError('Prepid returned was None')
        
        self.request.update_history({'action':'update'})
        
        return self.save_request()

    def save_request(self):
        return dumps({"results":self.db.update(self.request.json())})

class DeleteCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'campaigns'
        self.db = database(self.db_name)
        self.cdb = database('chained_campaigns')
        self.fdb = database('flows')
    
    def DELETE(self, *args):
        if not args:
            return dumps({"results":False})
        return self.delete_request(args[0])
    
    def delete_request(self, id):
        if not self.delete_all_requests(id):
                return dumps({"results":False})
        
        # delete all chained_campaigns and flows that have this campaign as a member
        self.resolve_dependencies(id)
        
        return dumps({"results":self.db.delete(id)})

    def delete_all_requests(self, id):
        rdb = database('requests')
        res = rdb.query('member_of_campaign=='+id, page_num=-1)
        try:
                for req in res:
                        rdb.delete(req['value']['prepid'])
                return True
        except Exception as ex:
                print str(ex)
                return False
    
    def resolve_dependencies(self,  cid):
        if not self.db.document_exists(cid):
            return
            
        camp = self.db.get(cid)
        
        # update all campaigns
        chains = self.cdb.query('campaign=='+cid)
        
        # include the delete method
        if chains:
            try:
                from rest_api.ChainedCampaignActions import DeleteChainedCampaign
            except ImportError as ex:
                return dumps({'results':str(ex)})
            
            # init deleter
            delr = DeleteChainedCampaign()
            
            for cc in chains:
                delr.delete_request(cc)
        
        # get all campaigns that contain cid in their next parameter
        allowed_campaigns = self.db.query('next=='+cid)
        
        # update all those campaigns
        for c in allowed_campaigns:
            c['next'].remove(cid)
            self.db.update(c)

class GetCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'campaigns'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        if not args:
	    self.logger.error("No Arguments were given")
            return dumps({"results":'Error: No arguments were given'})
        return self.get_request(args[0])
    
    def get_request(self, data):
        return dumps({"results":self.db.get(prepid=data)})

class GetAllCampaigns(RESTResource):
    def __init__(self):
        self.db_name = 'campaigns'
        self.db = database(self.db_name)

    def GET(self, *args):
        return self.get_all()

    def get_all(self):
        return dumps({"results":self.db.raw_query("prepid")})
        
class ToggleCampaign(RESTResource):
    def __init__(self):
        self.db = database('campaigns')
    
    def GET(self,  *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return self.toggle_campaign(args[0])
    
    def toggle_campaign(self,  rid):
        if not self.db.document_exists(rid):
            return dumps({"results":'Error: The given campaign id does not exist.'})
        camp = campaign(json_input=self.db.get(rid))
        camp.toggle_approval()
        
        return dumps({"results":self.db.update(camp.json())})

class ToggleCampaignStatus(RESTResource):
    def __init__(self):
        self.db = database('campaigns')

    def GET(self,  *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return self.toggle_campaign(args[0])

    def toggle_campaign(self,  rid):
        if not self.db.document_exists(rid):
            return dumps({"results":'Error: The given campaign id does not exist.'})
        camp = campaign(json_input=self.db.get(rid))
        try:
            camp.toggle_status()
            return dumps({"results":self.db.update(camp.json())})
        except:
            return dumps({"results":False})
    
class ApproveCampaign(RESTResource):
    def __init__(self):
        self.db = database('campaigns')
    
    def GET(self,  *args):
        if not args:
            self.logger.error('No arguments were given') 
            return dumps({"results":'Error: No arguments were given'})
        if len(args) < 2:
            return self.multiple_toggle(args[0])
        return self.multiple_toggle(args[0],  args[1])

    def multiple_toggle(self, rid, val=0):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.toggle_campaign(r, val))
            return dumps(res)
        else:
            return dumps(self.toggle_campaign(rid, val))
    
    def toggle_campaign(self,  rid,  index):
        if not self.db.document_exists(rid):
            return {"prepid": rid,  "results":'Error: The given campaign id does not exist.'}
        camp = campaign(json_input=self.db.get(rid))
        camp.approve(int(index))
        if int(index)==0:
            camp.set_status(0)
        res=self.db.update(camp.json())
        return {"prepid": rid, "results": res, "approval" : camp.get_attribute('approval')}


class GetCmsDriverForCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'campaigns'
        self.db = database(self.db_name)
        self.campaign = None

    def GET(self, *args):
      if not args:
        self.logger.error('No arguments were given')
        return dumps({"results":'Error: No arguments were given.'})
      return self.get_cmsDriver(self.db.get(prepid=args[0]))

    def get_cmsDriver(self, data):
      try:
        self.campaign = campaign(json_input=data)
      except campaign.IllegalAttributeName as ex:
        return dumps({"results":''})

      return dumps({"results":self.campaign.build_cmsDrivers()})

class CampaignsRESTResource(RESTResource):
    def __init__(self):
        self.cdb = database('campaigns')
        self.rdb = database('requests')

    def listAll(self):
      all_campaigns = self.cdb.raw_query("prepid")
      prepids_list = map(lambda x:x['id'], all_campaigns)
      return prepids_list
        
    def multiple_inspect(self, cid):
        clist=list(set(cid.rsplit(',')))
        res = []
        for c in clist:

            ## this query needs to be modified if we want to also inspect the request for submit !
            rlist = self.rdb.queries( ["member_of_campaign==%s"%( c ),
                                       "status==submitted"] )
            for r in rlist:
                mcm_r = request( r )
                if mcm_r:
                    res.append( mcm_r.inspect() ) 
                else:
                    res.append( {"prepid": r, "results":False, 'message' : '%s does not exist'%(r)})
        if len(res)>1:
            return dumps(res)
        elif len(res):
            return dumps(res[0])
        else:
            return dumps([])
    
class ListAllCampaigns(CampaignsRESTResource):
    def __init__(self):
        CampaignsRESTResource.__init__(self)

    def GET(self, *args):
        return dumps({"results": self.listAll()})


class InspectRequests(CampaignsRESTResource):
    def __init__(self):
        CampaignsRESTResource.__init__(self)
        self.access_limit = 3

    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return self.multiple_inspect(args[0])

class InspectCampaigns(CampaignsRESTResource):
    def __init__(self):
        CampaignsRESTResource.__init__(self)
        self.access_limit = 3

    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        if args[0] != 'all':
            return dumps({"results":'Error: Incorrect argument provided'})

        return self.multiple_inspect( ','.join(self.listAll()) )
