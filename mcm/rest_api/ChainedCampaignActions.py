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
from collections import defaultdict

class CreateChainedCampaign(RESTResource):
    def __init__(self):
        self.db = database('chained_campaigns')
        self.adb = database('actions')
        self.ccamp = None
        self.access_limit = 3
    
    def PUT(self):
        """
        Create a chained campaign from the provide json content
        """
        return self.create_campaign(cherrypy.request.body.read().strip())

    def create_campaign(self, jsdata):
        data = loads(jsdata)
        if '_rev' in data:
            return dumps({"results":" cannot create from a json with _rev"})

        try:
            self.ccamp = chained_campaign(json_input=loads(jsdata))
        except chained_campaign('').IllegalAttributeName as ex:
            return dumps({"results":False, "message":str(ex)})

        self.logger.log('Creating new chained_campaign %s...' % (self.ccamp.get_attribute('_id'))) 
        
        self.ccamp.set_attribute("_id", self.ccamp.get_attribute("prepid"))
        if not self.ccamp.get_attribute("_id") :#or self.db.document_exists(self.ccamp.get_attribute("_id")):
            self.logger.error('Campaign %s already exists. Cannot re-create it.' % (self.ccamp.get_attribute('_id')))
            return dumps({"results":False, "message":'Error: Campaign '+self.ccamp.get_attribute("_id")+' already exists'})
        
	# update history
	self.ccamp.update_history({'action':'created'})
        
        saved = self.db.save(self.ccamp.json())

        # update actions db
        self.update_actions()

        if saved:
            return dumps({"results":True, "prepid" : self.ccamp.get_attribute("prepid")})
        else:
            return dumps({"results":False, "message":"could not save to DB"})

    
    # update the actions db to include the new chain
    def update_actions(self):
        cid = self.ccamp.get_attribute('prepid')
        # get the initial campaigns
        (root_camp,f) = self.ccamp.get_attribute('campaigns')[0]
        #f == null
        allacs = self.adb.query('member_of_campaign=='+cid) 
                
        # for each action
        for ac in allacs:
            # init action object
            a = action(json_input=ac)
            # calculate the available chains
            a.find_chains()
            # save to db
            self.adb.update(a.json())

"""
    def update_actions(self):
        # get all campaigns in the chained campaign
        camps = self.ccamp.get_attribute('campaigns')
 
        self.logger.log('Updating actions for new chained_campaign %s ...' % (self.ccamp.get_attribute('_id')))
        
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
                a['chains'][cid]['flag']=False
                # save to db
                self.adb.update(a)
"""

class UpdateChainedCampaign(RESTResource):
        def __init__(self):
                self.db = database('chained_campaigns')
                self.ccamp = None
                self.access_limit = 3 

        def PUT(self):
            """
            Update the content of a chained campaign with the provided json content
            """
            return self.update_campaign(cherrypy.request.body.read().strip())

        def update_campaign(self, jsdata):
                data = loads ( jsdata)
                if '_rev' not in data:
                    return dumps({"results":False})

                try:
                        self.ccamp = chained_campaign(json_input=data)
                except chained_campaign('').IllegalAttributeName as ex:
                        return dumps({"results":False})


                if not self.ccamp.get_attribute("_id"):
                        self.logger.error('prepid returned was None')
                        return dumps({"results":False})

                self.logger.log('Updating chained_campaign %s ...' % (self.ccamp.get_attribute('_id')))

		# update history
		self.ccamp.update_history({'action':'updated'})

                return dumps({"results":self.db.update(self.ccamp.json())})

"""        
class AddRequestToChain(RESTResource):
    def __init__(self):
        self.request_db = database('requests')
        self.campaign_db = database('campaigns')
        self.chained_db = database('chained_requests')
        self.ccamp_db = database('chained_campaigns')
        self.campaign = None

    def POST(self, *args):
        if not args:
            return dumps({"results":False})
        if len(args) < 2:
            return dumps({"results":False})
        return self.import_request(args[0], args[1])

    def add_request(self, chainid, campaignid):

        self.logger.log('Generating new request to add in %s...' % (chainid))

        if not chainid:
            self.logger.error('chained_request\'s prepid was None.') 
            return dumps({"results":False}) 
        else:
            try:
                chain = chained_request(chained_request_json=self.chained_db.get(chainid))
            except Exception as ex:
                self.logger.error('Could not initialize chained_request object. Reason: %s' % (ex))
                return dumps({"results":False})
        if not campaignid:
            self.logger.error('id of the campaign provided was None')
            return dumps({"results":False})
        else:
            try:
                camp = campaign(campaign_json=self.campaign_db.get(campaignid))
            except Exception as ex:
                self.logger.error('Could not initialize campaign object. Reason: %s' % (ex))
                return dumps({"results":False})
        req = camp.add_request()
        new_req = chain.add_request(req)
        
        # save everything
        if not self.chained_db.save(chain.json()):
            self.logger.error('Could not save newly created request to database.')
            return dumps({"results":False})
        return dumps({"results":self.request_db.save(new_req)})
"""

class DeleteChainedCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'chained_campaigns'
        self.db = database(self.db_name)
        self.adb = database('actions')
    def DELETE(self, *args):
        """
        Delete a chained campaign and all related
        """
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
                rdb.delete(req['prepid'])
            return True
        except Exception as ex:
            print str(ex)
            return False

class GetChainedCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'chained_campaigns'
        self.db = database(self.db_name)
    def GET(self, *args):
        """
        Retrieve the content of a given chained campaign id
        """
        if not args:
            self.logger.error('No arguments were given.')
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
        self.access_limit = 3
        from rest_api.ActionsActions import GenerateChainedRequests
        self.generator = GenerateChainedRequests()

    def GET(self,  *args):
        """
        Generate the chained requests for a given chained campaign.
        """
        #return dumps({"results":"Broken and should not be used yet"})
    
        if not args:
            self.logger.error('No arguments were given') 
            return dumps({"results":'Error: No arguments were given'})
        return self.generate_requests(args[0])
    
    def generate_requests(self, ccid):
        if not self.ccdb.document_exists(ccid):
            return dumps({"results":False})

        mcm_cc = chained_campaign( self.ccdb.get(ccid))
        ## get the root campaign id
        root_campaign = mcm_cc.get_attribute('campaigns')[0][0]

        ## get all actions belonging to that root campaign
        root_actions = self.adb.queries(['member_of_campaign==%s'%(root_campaign)])
        res=[]
        for a in root_actions:
            res.append(self.generator.generate_request(a['prepid']))
            
        return dumps(res)
    

class InspectChainedCampaignsRest(RESTResource):
    def __init__(self):
        self.ccdb = database('chained_campaigns') 
        self.crdb = database('chained_requests')
        self.access_limit = 3

    def listAll(self):
        all_cc = self.ccdb.raw_query("prepid")
        prepids_list = map(lambda x:x['id'], all_cc)
        return prepids_list

    def multiple_inspect(self, ccids):
        res=[]
        for ccid in ccids.split(','):
            crlist = self.crdb.queries( ["member_of_campaign==%s"% ccid,
                                         "last_status==done",
                                         "status==processing"] )
            for cr in crlist:
                mcm_cr = chained_request( cr )
                if mcm_cr:
                    res.append( mcm_cr.inspect() )
                else:
                    res.append( {"prepid":cr, "results":False, 'message' : '%s does not exist'%(r)})

        if len(res)>1:
            return dumps(res)
        elif len(res):
            return dumps(res[0])
        else:
            return dumps([])

class InspectChainedRequests(InspectChainedCampaignsRest): 
    def __init__(self):
        InspectChainedCampaignsRest.__init__(self)

    def GET(self, *args):
        """
        Inspect the chained requests of a provided chained campaign id
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given'})
        return self.multiple_inspect( args[0] )

class InspectChainedCampaigns(InspectChainedCampaignsRest):
    def __init__(self):
        InspectChainedCampaignsRest.__init__(self)

    def GET(self, *args):
        """
        Inspect the chained requests of all chained campaigns, requires /all
        """
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        if args[0] != 'all':
            return dumps({"results":'Error: Incorrect argument provided'})

        return self.multiple_inspect( ','.join(self.listAll()) )

    
class SelectNewChainedCampaigns(RESTResource):

    def __init__(self):
        self.ccdb = database('chained_campaigns')
        self.cdb = database('campaigns')
        self.fdb = database('flows')
        self.access_limit = 3

    def GET(self, *args):
        """
        just a testing restapi
        """
        # get all the flows
        flows = self.fdb.queries([])
        all_cc = []

        def finish_chain(chain_name, chains_dict, allowed_campaigns_dict):
            """
            Start recursive finishing of chain.
            """
            chain = chains_dict[chain_name]["campaigns_list"]
            try:
                last_campaign, last_flow = chain[-1]
            except TypeError:
                return
            next_campaigns = []
            if last_campaign in allowed_campaigns_dict:
                next_campaigns.extend(allowed_campaigns_dict[last_campaign])

            traverse_next_campaigns(next_campaigns, chains_dict, chain, chain_name,allowed_campaigns_dict)

        def traverse_next_campaigns(next_campaigns, chains_dict, previous_campaigns, previous_chain_name, allowed_campaigns_dict):
            """
            Go through all possible connections between chains.
            """
            for flow, next_campaign in next_campaigns:
                chain_name = previous_chain_name+'_'+flow
                db_existence = self.ccdb.document_exists(chain_name)
                validity = False
                new_campaigns = list(previous_campaigns)
                new_campaigns.append((next_campaign, flow))
                if db_existence:
                    mcm_cc=self.ccdb.get(chain_name)
                    validity=mcm_cc['valid']
                    #all_cc.append(mcm_cc)
                else:
                    all_cc.append({'prepid': chain_name, 'campaigns': new_campaigns, "exists": False})
                    
                # chained_campaigns = self.ccdb.queries(['prepid==%s' % chain_name])
                # db_existence = False
                # validity = False
                # if len(chained_campaigns) > 0:
                #    db_existence = True
                #    if chained_campaigns[0]['valid']:
                #        validity = True
                chains_dict[chain_name] = {"campaigns_list": new_campaigns, "exists_in_database": db_existence, "valid": validity}
                # recursively fill all the possible chains
                finish_chain(chain_name, chains_dict, allowed_campaigns_dict)

        allowed_campaigns_dict = defaultdict(list)
        # preparation of dicts needed by later algorithm
        for flow in flows:
            allowed_campaigns = flow['allowed_campaigns']
            for allowed_campaign in allowed_campaigns:
                allowed_campaigns_dict[allowed_campaign].append((flow['prepid'], flow['next_campaign']))

        chains_dict = defaultdict(dict) # chain_id:{"campaigns_list": list, "exists_in_database":exists, "valid":validity})
        # creation of output dictionary
        for allowed_c in allowed_campaigns_dict:
            campaigns = self.cdb.queries(['prepid==%s' % allowed_c])
            if len(campaigns) == 0 or campaigns[0]["root"] == 1:
                continue
            next_campaigns = allowed_campaigns_dict[allowed_c]
            traverse_next_campaigns(next_campaigns, chains_dict, [(allowed_c, None)], 'chain_' + allowed_c, allowed_campaigns_dict)

        return dumps({"results" : all_cc})
        #return dumps({'results':'Got %s flows and %s campaigns'%(len(flows),len(campaigns))})
