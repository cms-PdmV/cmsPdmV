#!/usr/bin/env python

import cherrypy
import multiprocessing
import time

from json import dumps
from collections import defaultdict
from random import shuffle

from RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from json_layer.chained_request import chained_request
from json_layer.chained_campaign import chained_campaign
from json_layer.action import action
from tools.user_management import access_rights
from tools.json import threaded_loads
from rest_api.ActionsActions import GenerateChainedRequests


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

        self.logger.info('Creating new chained_campaign %s...' % (
                ccamp.get_attribute('prepid')))

        ccamp.set_attribute("_id", ccamp.get_attribute("prepid"))
        if not ccamp.get_attribute("_id") :#or self.db.document_exists(ccamp.get_attribute("_id")):
            self.logger.error('Campaign %s already exists. Cannot re-create it.' % (
                    ccamp.get_attribute('_id')))

            return {"results":False, "message":'Error: Campaign '+ccamp.get_attribute("_id")+' already exists'}

        # update history
        ccamp.update_history({'action' : 'created'})
        saved = db.save(ccamp.json())

        # update actions db
        self.update_actions(ccamp)

        # update campaigns db
        self.update_campaigns(ccamp)

        if saved:
            return {"results" : True, "prepid" : ccamp.get_attribute("prepid")}
        else:
            return {"results" : False, "message" : "could not save to DB"}

    def update_campaigns(self, ccamp):
        cdb = database('campaigns')
        next = None
        self.logger.info('Looking at campaigns %s' % (ccamp.get_attribute('campaigns')))
        for (c, f) in reversed(ccamp.get_attribute('campaigns')):
            mcm_c = cdb.get(c)
            if next:
                if not next in mcm_c['next']:
                    mcm_c['next'].append(next)
                    mcm_c['next'].sort()
                    cdb.update(mcm_c)
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
            data = threaded_loads(jsdata)
            if '_rev' not in data:
                return {"results" : False}
            try:
                ccamp = chained_campaign(json_input=data)
            except chained_campaign('').IllegalAttributeName as ex:
                return {"results" : False}


            if not ccamp.get_attribute("_id"):
                self.logger.error('prepid returned was None')
                return {"results":False}

            self.logger.info('Updating chained_campaign %s ...' % (
                    ccamp.get_attribute('_id')))

            # update history
            ccamp.update_history({'action' : 'updated'})
            return {"results" : db.update(ccamp.json())}

class DeleteChainedCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'chained_campaigns'

    def DELETE(self, *args):
        """
        Delete a chained campaign and all related
        """
        if not args:
            return dumps({"results" : False})
        force = False
        if len(args) > 1:
            force = (args[1] == 'force')
        return dumps(self.delete_request(args[0], force))

    def delete_request(self, ccid, force=False):
        if not self.delete_all_requests(ccid, force):
            return {"results" : False}

        # update all relevant actions
        self.update_actions(ccid)
        db = database(self.db_name)
        return {"results" : db.delete(ccid)}

    def update_actions(self, cid):
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
        res = rdb.query('member_of_campaign==' + cid, page_num=-1)
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
            return dumps({"results" : False})
        return dumps(self.get_request(args[0]))

    def get_request(self, id):
        return {"results" : self.db.get(id)}

class GenerateChainedRequests(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def GET(self, *args):
        """
        Generate the chained requests for a given chained campaign.
        """

        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results" : 'Error: No arguments were given'})
        return dumps(self.generate_requests(args[0]))

    def generate_requests(self, ccid):
        ccdb = database('chained_campaigns')
        adb = database('actions')
        if not ccdb.document_exists(ccid):
            return {"results" : False}

        mcm_cc = chained_campaign( ccdb.get(ccid))
        ## get the root campaign id
        root_campaign = mcm_cc.get_attribute('campaigns')[0][0]

        ## get all actions belonging to that root campaign
        __query = adb.construct_lucene_query({'member_of_campaign' : root_campaign})
        root_actions = adb.full_text_search('search', __query, page=-1)
        res = []
        generator = GenerateChainedRequests()
        for a in root_actions:
            res.append(generator.generate_request(a['prepid']))

        return res

class InspectChainedCampaignsRest(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager
        ##define this method as stream
        self._cp_config = {'response.stream': True}
        self.running = False

    def listAll(self):
        ccdb = database('chained_campaigns')
        all_cc = ccdb.raw_query("prepid")
        prepids_list = map(lambda x : x['id'], all_cc)
        return prepids_list

    def multiple_inspect(self, ccids):

        self.running = True
        crdb = database('chained_requests')
        try:
            for ccid in ccids.split(','):
                __query = crdb.construct_lucene_query({'member_of_campaign' : ccid,
                        'last_status' : 'done', 'status' : 'processing'})

                crlist = crdb.full_text_search('search', __query, page=-1)

                ##we yield len of cr_list so we would know how much data later on we processed
                yield dumps({'prepid': ccid, 'cr_len': len(crlist)}, indent=2)

                for cr in crlist:
                    time.sleep(0.5)
                    mcm_cr = chained_request(cr)
                    if mcm_cr:
                        __inspect_ret = mcm_cr.inspect()
                    else:
                        __inspect_ret = {"prepid":cr, "results":False,
                                'message' : '%s does not exist' % cr['prepid']}

                    self.logger.info("Inspection for: %s returned: %s" % (cr['prepid'],
                            __inspect_ret))

                    yield dumps(__inspect_ret, indent=8)

                ##force slowing-down of inspect to not abuse the DB
                time.sleep(2)

            self.running = False
            self.logger.info("ChainedCampaigns inspection finished. running: %s" % self.running)

        except Exception as ex:
            self.running = False
            self.logger.error("ChainedCampaigns inspection crashed. reason: %s" % str(ex))

            yield dumps({'message': 'crlist crashed: %s' % (str(ex)),
                    'last_used_query' : __query})

class InspectChainedRequests(InspectChainedCampaignsRest):
    def __init__(self):
        InspectChainedCampaignsRest.__init__(self)

    def GET(self, *args):
        """
        Inspect the chained requests of a provided chained campaign id
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results" : 'Error: No arguments were given'})
        return self.multiple_inspect(args[0])

class InspectChainedCampaigns(InspectChainedCampaignsRest):
    def __init__(self):
        InspectChainedCampaignsRest.__init__(self)

    def GET(self, *args):
        """
        Inspect the chained requests of all chained campaigns, requires /all
        """

        if not args:
            return dumps({"results" : 'Error: No arguments were given'})
        if args[0] != 'all':
            return dumps({"results" : 'Error: Incorrect argument provided'})

        self.logger.info('InspectChainedRequests is running: %s' % (self.running))
        if self.running:
            return dumps({"results" : 'Already running inspection'})

        #force pretify output in browser for multiple lines
        cherrypy.response.headers['Content-Type'] = 'text/plain'
        ccid_list = self.listAll()
        shuffle(ccid_list)
        return self.multiple_inspect(','.join(ccid_list))

class SelectNewChainedCampaigns(RESTResource):

    def __init__(self):
        self.access_limit = access_rights.production_manager
        self.fdb = database('flows')
        self.cdb = database('campaigns')
        self.ccdb = database('chained_campaigns')


    def GET(self, *args):
        """
        Generate the list of chained campaigns documents that can be created from the content of flows and campaigns.
        """

        if not args:
            return dumps({"results": False, "message": "No arguments were given"})
        else:
            if self.fdb.document_exists(args[0]):
                __flow = self.fdb.get(args[0])
            else:
                return dumps({"results": False, "message": "Given flow_prepid was not found"})

        self.logger.debug("Constructing newpossible chained_campaigns for flow: %s" % (
                __flow["prepid"]))

        all_cc = []
        new_prepids = []
        ##generetate the graph sstructure from selected flow
        __connected_graph = self.bfs({}, [__flow["next_campaign"]])

        ##start constructing all paths in graph to selected campaign
        ## starting from any campaign in graph
        for el in __connected_graph:
            __camp = self.cdb.get(el)
            ##check if starting campaign is root
            if __camp["root"] in [-1, 0]:
                ret = self.find_all_paths(__connected_graph, el, __flow["next_campaign"])
                self.logger.debug("all paths return:%s" % (ret))
                for path in ret:
                    __prepid = "chain_"+"_".join(flow[0] for flow in path)
                    ##safety check to not add same chained_campaigns all over
                    if __prepid not in new_prepids:
                        ##corss check if the contructed prepid is not already in DB
                        if not self.ccdb.document_exists(__prepid):
                            all_cc.append({"prepid": __prepid,
                                    "campaigns": path, "exists": False})

                            self.logger.debug("possible new chained_campaign: %s" % (
                                    __prepid))

        return dumps({"results": all_cc})

    def bfs(self, graph, start):
        """
         A breadth-first search to construct a graph with all possible
         connections from selected flow into adjacency lists
        """

        visited = set()
        queue = []
        ##start from allowed campaigns,
        ## there could be more than 1
        queue.extend(start)

        while queue:
            vertex = queue.pop(0)

            ##if we haven't checked campaign
            if vertex not in visited:

                visited.add(vertex)
                ##find all flows which goes to selected campaign
                __query = self.fdb.construct_lucene_query({"next_campaign": vertex})
                other_allowed_flows = self.fdb.full_text_search("search",
                        __query, page=-1)

                for el in other_allowed_flows:
                    ##we check those campaigns which is current flow's input
                    ##and add it to the global graph dictionary
                    for camp in el["allowed_campaigns"]:
                        if camp in graph:
                            ##in case campaign is already there
                            ## we check if the flow info is not there
                            if not (el["prepid"], el["next_campaign"]) in graph[camp]:
                                graph[camp].append((el["prepid"], el["next_campaign"]))
                        else:
                            graph[camp] = [(el["prepid"], el["next_campaign"])]

                    queue.extend(el["allowed_campaigns"])

        return graph

    def find_all_paths(self, graph, start, end, flow=None, path=[]):
        """
         Find all paths in graph from two nodes. More here:
         https://www.python.org/doc/essays/graphs/
        """

        ##start of chained_campaign has to start with root_campaign
        if not flow:
            path = path + [[start, None]]
        else:
            path = path + [[start, flow]]
        ##check if we reached the end
        if start == end:
            return [path]
        ##this is to check if the future campaign is not in graph
        if not graph.has_key(start):
            return []

        paths = []
        for node in graph[start]:
            ##go recursively until the end of the path
            newpaths = self.find_all_paths(graph, node[1], end,node[0], path)
            for newpath in newpaths:
                paths.append(newpath)

        return paths

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
        self.logger.info('All list raw_query view:%s searching for: %s' % (
                view_name, search_key))

        data = [key['value'] for key in result]
        return {"results": data}
