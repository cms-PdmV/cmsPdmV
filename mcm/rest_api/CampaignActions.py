#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResource
from json_layer.campaign import campaign
from json_layer.request import request
from json_layer.sequence import sequence
from json_layer.chained_campaign import chained_campaign

class CreateCampaign(RESTResource):
    def __init__(self):
        self.access_limit =3

    def PUT(self):
        """
        Create a request with the provided json content
        """
        return dumps(self.create_campaign(cherrypy.request.body.read().strip()))

    def create_campaign(self, data):
        db = database('campaigns')
        try:
            camp_mcm = campaign(json_input=loads(data))
        except campaign.IllegalAttributeName as ex:
            return {"results":False}

        #id = RequestPrepId().generate_prepid(self.json['pwg'], self.json['member_of_campaign'])
        #self.json['prepid'] = loads(id)['prepid']
        if not camp_mcm.get_attribute('prepid'):
            self.logger.error('Invalid prepid: Prepid returned None')
            return {"results":False}

        if '_' in camp_mcm.get_attribute('prepid'):
            self.logger.error('Invalid campaign name %s'%(camp_mcm.get_attribute('prepid')))
            return {"results":False}

        camp_mcm.set_attribute('_id', camp_mcm.get_attribute('prepid'))

        camp_mcm.update_history({'action':'created'})

        ## this is to create, not to update
        if db.document_exists( camp_mcm.get_attribute('prepid') ):
            return {"results":False}

        # save to db
        if not db.save(camp_mcm.json()):
            self.logger.error('Could not save object to database')
            return {"results":False}

        # create dedicated chained campaign
        self.create_chained_campaign(camp_mcm.get_attribute('_id'), db, camp_mcm.get_attribute('energy'))

        return {"results":True}

    # creates a chained campaign containing only the given campaign
    def create_chained_campaign(self, cid, db, energy=-1):
        if db.get(cid)['root'] < 1:
            cdb = database('chained_campaigns')
            dcc = chained_campaign()
            dcc.set_attribute('prepid', 'chain_'+cid)
            dcc.set_attribute('_id',  dcc.get_attribute('prepid'))
            #dcc.set_attribute('energy',  energy)
            dcc.add_campaign(cid) # flow_name = None
            cdb.save(dcc.json())

class UpdateCampaign(RESTResource):
    def __init__(self):
        self.access_limit = 3

    def PUT(self):
        """
        Update the content of a campaign data with the provided information
        """
        return dumps(self.update_campaign(cherrypy.request.body.read().strip()))

    def update_campaign(self, data):
        if not '_rev' in data:
            return {"results":False, 'message': 'There is no previous revision provided'}
        try:
            camp_mcm = campaign(json_input=loads(data))
        except campaign.IllegalAttributeName as ex:
            return {"results":False}

        if not camp_mcm.get_attribute('prepid') and not camp_mcm.get_attribute('_id'):
            raise ValueError('Prepid returned was None')

        #cast schema evolution of sequences
        sequences = camp_mcm.get_attribute('sequences')
        for steps in sequences:
            for label in steps:
                steps[label] = sequence( steps[label] ).json()
        camp_mcm.set_attribute('sequences', sequences)

        # create dedicated chained campaign
        self.create_chained_campaign(camp_mcm.get_attribute('_id'),  camp_mcm.get_attribute('root'))

        camp_mcm.update_history({'action':'update'})

        return self.save_campaign(camp_mcm)

    def save_campaign(self, camp_mcm):
        db = database('campaigns')
        return {"results": db.update(camp_mcm.json())}

    ##unfortunate duplicate
    # creates a chained campaign containing only the given campaign
    def create_chained_campaign(self,  cid,  root):
        if root < 1:
            cdb = database('chained_campaigns')
            dcc = chained_campaign()
            dcc.set_attribute('prepid', 'chain_'+cid)
            dcc.set_attribute('_id',  dcc.get_attribute('prepid'))
            dcc.add_campaign(cid)
            cdb.save(dcc.json())

class DeleteCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'campaigns'

    def DELETE(self, *args):
        """
        Delete a campaign
        """
        if not args:
            return dumps({"results":False})
        return dumps(self.delete_request(args[0]))

    def delete_request(self, cid):
        db = database(self.db_name)
        if not self.delete_all_requests(cid):
                return {"results":False}

        # delete all chained_campaigns and flows that have this campaign as a member
        self.resolve_dependencies(cid, db)

        return {"results":db.delete(cid)}

    def delete_all_requests(self, cid):
        rdb = database('requests')
        res = rdb.query('member_of_campaign=='+cid, page_num=-1)
        try:
                for req in res:
                        rdb.delete(req['prepid'])
                return True
        except Exception as ex:
                print str(ex)
                return False

    def resolve_dependencies(self, cid, db):
        if not db.document_exists(cid):
            return

        camp = db.get(cid)
        cdb = database('chained_campaigns')
        # update all campaigns
        chains = cdb.query('campaign=='+cid)

        # include the delete method
        if chains:
            try:
                from rest_api.ChainedCampaignActions import DeleteChainedCampaign
            except ImportError as ex:
                return {'results':str(ex)}

            # init deleter
            delr = DeleteChainedCampaign()

            for cc in chains:
                delr.delete_request(cc)

        # get all campaigns that contain cid in their next parameter
        allowed_campaigns = db.query('next=='+cid)

        # update all those campaigns
        for c in allowed_campaigns:
            c['next'].remove(cid)
            db.update(c)

class GetCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'campaigns'

    def GET(self, *args):
        """
        Retrive the json content of a campaign attributes
        """
        if not args:
            self.logger.error("No Arguments were given")
            return dumps({"results":'Error: No arguments were given'})
        return dumps(self.get_request(args[0]))

    def get_request(self, data):
        db = database(self.db_name)
        return {"results": db.get(prepid=data)}

class GetAllCampaigns(RESTResource):
    def __init__(self):
        self.db_name = 'campaigns'

    def GET(self, *args):
        """
        Get the json content of all campaigns in McM
        """
        return dumps(self.get_all())

    def get_all(self):
        db = database(self.db_name)
        return {"results":db.raw_query("prepid")}

class ToggleCampaign(RESTResource):
    def __init__(self):
        self.access_limit = 3

    def GET(self,  *args):
        """
        Move the campaign approval to the other state
        """
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return dumps(self.toggle_campaign(args[0]))

    def toggle_campaign(self,  rid):
        db = database('campaigns')
        if not db.document_exists(rid):
            return {"results":'Error: The given campaign id does not exist.'}
        camp = campaign(json_input=db.get(rid))
        camp.toggle_approval()

        return {"results":db.update(camp.json())}

class ToggleCampaignStatus(RESTResource):
    def __init__(self):
        self.access_limit = 3

    def GET(self,  *args):
        """
        Move the campaign status to the next state
        """
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return dumps(self.toggle_campaign(args[0]))

    def toggle_campaign(self,  rid):
        db = database('campaigns')
        if not db.document_exists(rid):
            return {"results":'Error: The given campaign id does not exist.'}
        camp = campaign(json_input=db.get(rid))
        try:
            camp.toggle_status()
            saved = db.update(camp.json())
            if saved:
                return {"results":True}
            else:
                return {"results":False, "message":"Could not save request"}

        except Exception as ex:
            return {"results":False, "message": str(ex) }

class ApproveCampaign(RESTResource):
    def __init__(self):
        self.access_limit = 3

    def GET(self,  *args):
        """
        Move campaign or provided list of campaigns ids to the next approval (/ids) or to the specified index (/ids/index)
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given'})
        if len(args) < 2:
            return dumps(self.multiple_toggle(args[0]))
        return dumps(self.multiple_toggle(args[0],  args[1]))

    def multiple_toggle(self, rid, val=-1):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.toggle_campaign(r, val))
            return res
        else:
            return self.toggle_campaign(rid, val)

    def toggle_campaign(self,  rid,  index):
        db = database('campaigns')
        if not db.document_exists(rid):
            return {"prepid": rid,  "results":'Error: The given campaign id does not exist.'}
        camp = campaign(json_input=db.get(rid))
        camp.approve(int(index))
        if int(index)==0:
            camp.set_status(0)
        res=db.update(camp.json())
        return {"prepid": rid, "results": res, "approval" : camp.get_attribute('approval')}


class GetCmsDriverForCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'campaigns'

    def GET(self, *args):
        """
        Retrieve the list of cmsDriver commands for a given campaign id
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given.'})
        db = database(self.db_name)
        return dumps(self.get_cmsDriver(db.get(prepid=args[0])))

    def get_cmsDriver(self, data):
        try:
            camp_mcm = campaign(json_input=data)
        except campaign.IllegalAttributeName as ex:
            return {"results":''}

        return {"results":camp_mcm.build_cmsDrivers()}

class CampaignsRESTResource(RESTResource):

    def listAll(self):
        cdb = database('campaigns')
        all_campaigns = cdb.raw_query("prepid")
        prepids_list = map(lambda x:x['id'], all_campaigns)
        return prepids_list

    def multiple_inspect(self, cid, in_statuses=['submitted','approved']):
        clist=list(set(cid.rsplit(',')))
        res = []
        rdb = database('requests')
        for c in clist:

            ## this query needs to be modified if we want to also inspect the request for submit !
            rlist=[]
            for in_status in in_statuses:
                rlist.extend(rdb.queries( ["member_of_campaign==%s"%( c ),
                                                "status==%s"%( in_status )] ))

            for r in rlist:
                mcm_r = request( r )
                if mcm_r:
                    res.append( mcm_r.inspect() )
                else:
                    res.append( {"prepid": r, "results":False, 'message' : '%s does not exist'%(r)})
        if len(res)>1:
            return res
        elif len(res):
            return res[0]
        else:
            return []

class ListAllCampaigns(CampaignsRESTResource):
    def __init__(self):
        CampaignsRESTResource.__init__(self)

    def GET(self, *args):
        """
        Retrieve the list of all existing campaigns
        """
        return dumps({"results": self.listAll()})


class InspectRequests(CampaignsRESTResource):
    def __init__(self):
        CampaignsRESTResource.__init__(self)
        self.access_limit = 3

    def GET(self, *args):
        """
        Inspect the campaign or coma separated list of campaigns for completed requests
        """
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return dumps(self.multiple_inspect(args[0]))

class InspectCampaigns(CampaignsRESTResource):
    def __init__(self):
        CampaignsRESTResource.__init__(self)
        self.access_limit = 3

    def GET(self, *args):
        """
        Inspect all the campaigns in McM for completed requests. Requires /all
        """
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        if args[0] != 'all':
            return dumps({"results":'Error: Incorrect argument provided'})

        return dumps(self.multiple_inspect( ','.join(self.listAll()) ))
