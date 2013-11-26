#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from couchdb_layer.mcm_database import database
from json_layer.chained_request import chained_request
from json_layer.chained_campaign import chained_campaign
from json_layer.campaign import campaign
from json_layer.request import request
from RestAPIMethod import RESTResource
from json_layer.action import action
from tools.priority import priority

class CreateAction(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.access_limit = 3
    def PUT(self):
        """
        Create an action from the provided json content
        """
        return self.import_request(cherrypy.request.body.read().strip())

    def import_request(self, data):
        db = database(self.db_name)
        try:
            action_mcm = action(json_input=loads(data))
        except request.IllegalAttributeName as ex:
            return dumps({"results":False})

        self.logger.log('Building new action %s by hand...'%(action_mcm.get_attribute('_id')))

        action_mcm.inspect_priority()

        rd = database('requests')
        if rd.document_exists(action_mcm.get_attribute('prepid')):
            r= request(rd.get(action_mcm.get_attribute('prepid')))
            action_mcm.set_attribute('dataset_name',r.get_attribute('dataset_name'))

        return dumps({'results':db.save(action_mcm.json())})


class UpdateAction(RESTResource):
    def __init__(self):
        self.access_limit = 3

    def PUT(self):
        """
        update the action with the provided json content
        """
        res = self.import_action( loads(cherrypy.request.body.read().strip()) )
        return dumps(res)

    def import_action(self, content):
        adb = database('actions')
        try:
            mcm_a = action( content ) 
        except request.IllegalAttributeName as ex:
            return {"results":False}
        self.logger.log('Updating action "%s" by hand...' % (mcm_a.get_attribute('_id')))

        ## massage the json for removing null items that could be send by the action editor interface
        chains = mcm_a.get_attribute('chains')
        for (cc,content) in chains.items():
            for (o,value) in content.items():
                if type(value)==dict:
                    for (cr,specs) in value.items():
                        for (s,spec) in specs.items():
                            if spec==None:
                                specs.pop(s)
                else:
                    if value==None:
                        content.pop(o)
        mcm_a.set_attribute('chains',chains)


        mcm_a.inspect_priority()

        saved = adb.update( mcm_a.json() )
        if saved:
            return {"results":True , "prepid": mcm_a.get_attribute('prepid')}
        else:
            return {"results":False , "prepid": mcm_a.get_attribute('prepid')}

class UpdateMultipleActions(UpdateAction):
    def __init__(self):
        UpdateAction.__init__(self)

    def PUT(self):
        """
        Update a multiple number of actions at the same time from the provided json content
        """
        self.logger.log('Updating multiple actions')
        data = loads(cherrypy.request.body.read().strip())

        results=[]
        for single_action in data:
            results.append(self.import_action(single_action))

        return dumps({"results": results})
        """
        output = []
        for elem in data["actions"]:
            single_action = loads(self.action_getter.get_request(elem["prepid"]))["results"]
            #self.logger.error(single_action)
            single_action["chains"][elem["column"]]["block_number"] = data["values"]["block_number"]
            if "staged" in data["values"]: #if staged in new values
                if data["values"]["staged"] == None:  #if None -> user should want it to be deleted
                    del single_action["chains"][elem["column"]]["staged"]
                else:  #and not a None
                    single_action["chains"][elem["column"]]["staged"] = data["values"]["staged"]
            elif "staged" in single_action["chains"][elem["column"]]: #if staged not in update then delete from chain
                del single_action["chains"][elem["column"]]["staged"]
            if "threshold" in data["values"]: 
                if data["values"]["staged"] == None:
                    del single_action["chains"][elem["column"]]["threshold"]
                else:
                    single_action["chains"][elem["column"]]["threshold"] = data["values"]["threshold"]
            elif "threshold" in single_action["chains"][elem["column"]]: #if threshold not in update then delete from chain
                del single_action["chains"][elem["column"]]["threshold"]
            if "flag" in data["values"]:
                if data["values"]["flag"] == None:
                    del single_action["chains"][elem["column"]]["flag"]
                else:
                    single_action["chains"][elem["column"]]["threshold"] = data["values"]["flag"]
            elif "flag" in single_action["chains"][elem["column"]]: #if threshold not in update then delete from chain
                del single_action["chains"][elem["column"]]["flag"]
            self.logger.error(single_action)    
            output += [self.single_updater.import_request(dumps(single_action))]
        return dumps({"results": output})
        """




class GetAction(RESTResource):
    def __init__(self):
        self.db_name = 'actions'

    def GET(self, *args):
        """
        Retrieve the json content of a given action id
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given'})

        return self.get_request(args[0])

    def get_request(self, id):
        db = database(self.db_name)
        return dumps({"results":db.get(id)})

class SelectChain(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.access_limit = 4

    def GET(self, *args):
        """
        Allows to select a given chained request for a given action id /action_id/chain_id
        """
        return dumps({"results":'not implemented'})
        if not args:
            self.logger.error('No arguments were given.')
            return dumps({"results":'Error: No arguments were given'})

        return self.select_chain(args[0],  args[1])

    def select_chain(self, aid,  chainid):
        db = database(self.db_name)
        self.logger.log('Selecting chain %s for action %s...' % (chainid, aid))
        # if action exists
        if db.document_exists(aid):
            # initialize the object
            a = action(json_input=db.get(aid))
            # and set it to 1 (default ?)
            a.select_chain(chainid)

            # save
            db.update(a.json())
            return dumps({'results':True})
        else:
            return dumps({"results":False})

class DeSelectChain(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.access_limit = 4

    def GET(self, *args):
        """
        Allows to UN-select a given chained request for a given action id /action_id/chain_id
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given'})

        return self.deselect_chain(args[0],  args[1])

    def deselect_chain(self,  aid,  chainid):
        db = database(self.db_name)
        self.logger.log('Deselecting chain %s for action %s...' % (chainid, aid))        
        # if action exists
        if db.document_exists(aid):
            # initialize the object
            a = action(json_input=db.get(aid))
            # and set it to 1 (default ?)
            a.deselect_chain(chainid)
            # save
            db.update(a.json())
            return dumps({'results':True})
        else:
            return dumps({"results":False})

class GenerateChainedRequests(RESTResource):
    def __init__(self):
        self.access_limit = 3

    def GET(self,  *args):
        """
        Generate all chained requests for a given action id
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({'results':'Error: No arguments were given'})
        res=[]
        for aid in args[0].split(','):
            res.append( self.generate_request(aid))

        if len(res)==1:
            return dumps(res[0])
        else:
            return dumps(res)

    def generate_request(self, aid):
        adb = database('actions')
        ccdb = database('chained_campaigns')
        crdb = database('chained_requests')
        rdb = database('requests')
        if not adb.document_exists(aid):
            return dumps({'results':False, 'message':'%s does not exist'%(aid)})

        self.logger.log('Generating all selected chained_requests for action %s' % (aid))
        act = action(adb.get(aid))
        chains = act.get_attribute('chains')
        hasChainsChanged=False 
        for cc in chains:  
            if 'flag' in chains[cc] and chains[cc]['flag']:
                ## in the new convention, that means that something needs to be created

                mcm_cc = chained_campaign( ccdb.get(cc) )
                new_cr = mcm_cc.generate_request( aid )
                if not 'chains' in chains[cc]:
                    chains[cc]['chains'] = {}
                chains[cc]['chains'][new_cr['prepid']] = {}
                to_transfer=['flag','threshold','staged','block_number']
                for item in to_transfer:
                    if item in chains[cc]:
                        chains[cc]['chains'][new_cr['prepid']] [item] = chains[cc][item]
                        chains[cc].pop(item)
                hasChainsChanged=True
                if not crdb.update(new_cr):
                    return dumps({'results':False,'message':'could not save %s'%( new_cr['prepid'])})

                ## update the cc history
                ccdb.update(mcm_cc.json())

                # then let the root request know that it is part of a chained request
                req = request(json_input=rdb.get(aid))
                inchains=req.get_attribute('member_of_chain')
                inchains.append(new_cr['prepid'])
                inchains.sort()
                req.set_attribute('member_of_chain',list(set(inchains)))
                req.notify("Request {0} joined chain".format(req.get_attribute('prepid')), "Request {0} has successfuly joined chain {1}".format(req.get_attribute('prepid'), new_cr['prepid']))
                act.update_history({'action':'add','step' : new_cr['prepid']})
                rdb.update(req.json())

        if hasChainsChanged:
            #the chains parameter might have changed
            act.set_attribute('chains',chains)
            adb.update(act.json())

        #and set priorities properly to all requests concerned
        act.inspect_priority()

        return dumps({'results':True})

class GenerateAllChainedRequests(GenerateChainedRequests):
    def __init__(self):
        GenerateChainedRequests.__init__(self)

    def GET(self,  *args):
        """
        Generate all chained requests for all actions where applicable
        """
        return self.generate_requests()

    def generate_requests(self):
        adb = database('actions')
        self.logger.log('Generating all possible (and selected) chained_requests...')
        allacs = adb.get_all(-1) # no pagination
        res=[]
        for a in allacs:
            res.append(self.generate_request(a['key']))

        return dumps(res)

class SetAction(GenerateChainedRequests):
    def __init__(self):
        GenerateChainedRequests.__init__(self)
        self.access_limit = 4

    def GET(self, *args):
        """
        Set the action and generate the chained request for /aid/alias or cc name/block#/stage of threshold
        """
        if len(args)<3:
            return dumps("Not enough arguments")

        adb = database('actions')
        ccdb = database('chained_campaigns')

        (aid,cc,block) = args[0:3]
        extra=None
        if len(args)==4:
            extra=args[3]
        staged=None
        threshold=None
        if extra:
            if '.' in extra:
                threshold=float(extra)
                if threshold>1 or threshold<0:
                    return dumps("A threshold is specified %s but not valid"%( threshold))
                threshold=int(threshold * 100)
            else:
                staged=int(extra)

        block=int(block)

        mcm_a = action( adb.get(aid) )
        ccs = ccdb.queries(['alias==%s'% cc])
        if not len(ccs):
            ccs = ccdb.queries(['prepid==%s'% cc])
        if not len(ccs) :
            return dumps("%s not a chained campaigns"%( cc ))

        mcm_cc = chained_campaign( ccs[0] )
        mcm_cc_name=mcm_cc.get_attribute('prepid')

        chains = mcm_a.get_attribute('chains')        
        if mcm_cc_name not in chains:
            #detect
            mcm_a.find_chains()
            chains = mcm_a.get_attribute('chains')

        if mcm_cc_name not in chains:
            return dumps("Not able to find %s for %s"%( mcm_cc_name, aid))

        #edit the chains content
        #if 'chains' in chains[mcm_cc_name]:
        #    return dumps("Something already exists for %s in %s. You'll have to do it by hand"%( mcm_cc_name,aid))

        chains[mcm_cc_name].update( { "flag":True, "block_number" : block})
        if staged:
            chains[mcm_cc_name]['staged']=staged
        if threshold:
            chains[mcm_cc_name]['threshold']=threshold

        #set back the chains
        mcm_a.set_attribute('chains',chains)

        #save it since it is retrieved from scratch later
        adb.save( mcm_a.json() )

        #and generate the chained requests
        return self.generate_request(aid)

class DetectChains(RESTResource):
    def __init__(self):
        self.access_limit = 3

    def GET(self,  *args):
        """
        Update the action content with the possible chains
        """
        db = database('actions')
        if not args:
            return self.find_all_chains(db)
        res=[]
        aids=args[0].split(',')
        if len(aids)==1:
            res=self.find_chains(aids[0],db)
        else:
            for aid in aids:
                res.append(self.find_chains(aid,db))

        return dumps(res)

    def find_chains(self,  aid, db):
        self.logger.log('Identifying all possible chains for action %s' % (aid))
        
        try:
            ac = action(json_input=db.get(aid))
            ac.find_chains()
            saved= db.update(ac.json())
            return {'results':saved,'prepid': aid}
        except Exception as ex:
            return {'results':False, 'prepid': aid, 'message' :str(ex)}

    def find_all_chains(self, db):
        self.logger.log('Identifying all possible chains for all actions in the database...')
        aids = lambda x: x['prepid'] , db.queries([])
        res=[]
        for aid in aids:
            res.append(self.find_chains(aid, db))

        return dumps(res)

from rest_api.RequestActions import RequestLister
class ActionsFromFile(RequestLister,RESTResource): 
    def __init__(self):
        RequestLister.__init__(self)
        self.retrieve_db = database('actions')
        self.access_limit = 0 

    def PUT(self, *args):
        """
        Parse the posted text document for request id and request ranges for display of actions
        """
        adb = database('actions')
        all_ids = self.get_list_of_ids( adb )
        return self.get_objects( all_ids , adb )

