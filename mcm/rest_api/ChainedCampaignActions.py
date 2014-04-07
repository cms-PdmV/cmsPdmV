#!/usr/bin/env python

import cherrypy
from json import dumps
from couchdb_layer.mcm_database import database
from json_layer.chained_request import chained_request
from json_layer.chained_campaign import chained_campaign
from RestAPIMethod import RESTResource
from json_layer.action import action
from collections import defaultdict
from tools.user_management import access_rights
from tools.json import threaded_loads


class CreateChainedCampaign(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def PUT(self):
        """
        Create a chained campaign from the provide json content
        """
        return dumps(self.create_campaign(cherrypy.request.body.read().strip()))

    def create_campaign(self, jsdata):
        data = threaded_loads(jsdata)
        db = database('chained_campaigns')
        if '_rev' in data:
            return {"results":" cannot create from a json with _rev"}

        try:
            ccamp = chained_campaign(json_input=threaded_loads(jsdata))
        except chained_campaign('').IllegalAttributeName as ex:
            return {"results":False, "message":str(ex)}

        self.logger.log('Creating new chained_campaign %s...' % (ccamp.get_attribute('prepid')))

        ccamp.set_attribute("_id", ccamp.get_attribute("prepid"))
        if not ccamp.get_attribute("_id") :#or self.db.document_exists(ccamp.get_attribute("_id")):
            self.logger.error('Campaign %s already exists. Cannot re-create it.' % (ccamp.get_attribute('_id')))
            return {"results":False, "message":'Error: Campaign '+ccamp.get_attribute("_id")+' already exists'}

        # update history
        ccamp.update_history({'action':'created'})
        saved = db.save(ccamp.json())

        # update actions db
        self.update_actions(ccamp)

        # update campaigns db
        self.update_campaigns(ccamp)
        
        if saved:
            return {"results":True, "prepid" : ccamp.get_attribute("prepid")}
        else:
            return {"results":False, "message":"could not save to DB"}

    def update_campaigns(self, ccamp):
        cdb = database('campaigns')
        next=None
        self.logger.log('Looking at campaigns %s' %( ccamp.get_attribute('campaigns') ))
        for ( c, f ) in reversed(ccamp.get_attribute('campaigns')):
            mcm_c = cdb.get(c)
            if next:
                if not next in mcm_c['next']:
                    mcm_c['next'].append(next)
                    mcm_c['next'].sort()
                    cdb.update( mcm_c )
            next = c
                    

    # update the actions db to include the new chain
    def update_actions(self, ccamp):
        adb = database('actions')
        cid = ccamp.get_attribute('prepid')
        # get the initial campaigns
        (root_camp,f) = ccamp.get_attribute('campaigns')[0]
        #f == null
        allacs = adb.query('member_of_campaign=='+cid)

        # for each action
        for ac in allacs:
            # init action object
            a = action(json_input=ac)
            # calculate the available chains
            a.find_chains()
            # save to db
            adb.update(a.json())

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
                self.access_limit = access_rights.production_manager

        def PUT(self):
            """
            Update the content of a chained campaign with the provided json content
            """
            return dumps(self.update_campaign(cherrypy.request.body.read().strip()))

        def update_campaign(self, jsdata):
            db = database('chained_campaigns')
            data = threaded_loads( jsdata)
            if '_rev' not in data:
                return {"results":False}
            try:
                ccamp = chained_campaign(json_input=data)
            except chained_campaign('').IllegalAttributeName as ex:
                return {"results":False}


            if not ccamp.get_attribute("_id"):
                self.logger.error('prepid returned was None')
                return {"results":False}

            self.logger.log('Updating chained_campaign %s ...' % (ccamp.get_attribute('_id')))

            # update history
            ccamp.update_history({'action':'updated'})

            return {"results":db.update(ccamp.json())}

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

    def DELETE(self, *args):
        """
        Delete a chained campaign and all related
        """
        if not args:
            return dumps({"results":False})
        force=False
        if len(args)>1:
            force=(args[1]=='force')
        return dumps(self.delete_request(args[0], force))

    def delete_request(self, ccid, force=False):
        if not self.delete_all_requests(ccid, force ):
            return {"results":False}

        # update all relevant actions
        self.update_actions(ccid)
        db = database(self.db_name)
        return {"results": db.delete(ccid)}

    def update_actions(self,  cid):
        # get all actions that contain cid in their chains
        adb = database('actions')
        actions = adb.query('chain=='+cid)
        for a in actions:
            if cid in a['chains']:
                # delete the option of cid in each relevant action
                del a['chains'][cid]
                adb.update(a)

    def delete_all_requests(self, cid, force=False):
        rdb = database('chained_requests')
        res = rdb.query('member_of_campaign=='+cid, page_num=-1)
        if len(res) and not force:
            return False
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
        return dumps(self.get_request(args[0]))

    def get_request(self, id):
        return {"results":self.db.get(id)}


class GenerateChainedRequests(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def GET(self,  *args):
        """
        Generate the chained requests for a given chained campaign.
        """
        #return dumps({"results":"Broken and should not be used yet"})

        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given'})
        return dumps(self.generate_requests(args[0]))

    def generate_requests(self, ccid):
        ccdb = database('chained_campaigns')
        adb = database('actions')
        if not ccdb.document_exists(ccid):
            return {"results":False}

        mcm_cc = chained_campaign( ccdb.get(ccid))
        ## get the root campaign id
        root_campaign = mcm_cc.get_attribute('campaigns')[0][0]

        ## get all actions belonging to that root campaign
        root_actions = adb.queries(['member_of_campaign==%s'%(root_campaign)])
        res=[]
        from rest_api.ActionsActions import GenerateChainedRequests
        generator = GenerateChainedRequests()
        for a in root_actions:
            res.append(generator.generate_request(a['prepid']))

        return res


class InspectChainedCampaignsRest(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def listAll(self):
        ccdb = database('chained_campaigns')
        all_cc = ccdb.raw_query("prepid")
        prepids_list = map(lambda x:x['id'], all_cc)
        return prepids_list

    def multiple_inspect(self, ccids):
        crdb = database('chained_requests')
        res=[]
        for ccid in ccids.split(','):
            crlist = crdb.queries( ["member_of_campaign==%s"% ccid,
                                         "last_status==done",
                                         "status==processing"] )
            self.logger.log('crlist %s in chained_camp %s ' % (crlist, ccid))
            for cr in crlist:
                mcm_cr = chained_request( cr )
                if mcm_cr:
                    res.append( mcm_cr.inspect() )
                else:
                    res.append( {"prepid":cr, "results":False, 'message' : '%s does not exist' % cr})

        if len(res)>1:
            return res
        elif len(res):
            return res[0]
        else:
            return []


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
        return dumps(self.multiple_inspect(args[0]))

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

        ccid_list = self.listAll()
        from random import shuffle
        shuffle(ccid_list)
        return dumps(self.multiple_inspect( ','.join( ccid_list )))


class SelectNewChainedCampaigns(RESTResource):

    def __init__(self):
        self.access_limit = access_rights.production_manager

    def GET(self, *args):
        """
        Generate the list of chained campaigns documents that can be created from the content of flows and campaigns.
        """
        # get all the flows
        fdb = database('flows')
        ccdb = database('chained_campaigns')
        cdb = database('campaigns')
        flows = fdb.queries([])
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
                db_existence = ccdb.document_exists(chain_name)
                validity = False
                new_campaigns = list(previous_campaigns)
                new_campaigns.append((next_campaign, flow))
                if db_existence:
                    mcm_cc=ccdb.get(chain_name)
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
            campaigns = cdb.queries(['prepid==%s' % allowed_c])
            if len(campaigns) == 0 or campaigns[0]["root"] == 1:
                continue
            next_campaigns = allowed_campaigns_dict[allowed_c]
            traverse_next_campaigns(next_campaigns, chains_dict, [(allowed_c, None)], 'chain_' + allowed_c, allowed_campaigns_dict)

        return dumps({"results" : all_cc})


class ListChainCampaignPrepids(RESTResource):
    def __init__(self):
        RESTResource.__init__(self)
        self.db_name = 'chained_campaigns'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
        List all prepids from view by given key(-s)
        """
        if not args:
            self.logger.error(' No arguments were given')
            return dumps({"results": False, 'message': 'Error: No arguments were given'})
        return dumps(self.get_all_prepids(args[0], args[1]))

    def get_all_prepids(self, view, key=None):
        view_name = view
        if key:
            search_key = key
        result = self.db.raw_query(view_name, {'key': search_key})
        self.logger.log('All list raw_query view:%s searching for: %s' %(view_name,search_key))
        data = [key['value'] for key in result]
        return {"results": data}
