#!/usr/bin/env python

import cherrypy
from json import dumps
from couchdb_layer.mcm_database import database
from json_layer.chained_request import chained_request
from json_layer.chained_campaign import chained_campaign
from json_layer.request import request
from RestAPIMethod import RESTResource
from json_layer.action import action
from tools.json import threaded_loads
from tools.user_management import access_rights

class CreateAction(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.access_limit = access_rights.production_manager
    def PUT(self):
        """
        Create an action from the provided json content
        """
        return self.import_request(cherrypy.request.body.read().strip())

    def import_request(self, data):
        adb = database(self.db_name)
        try:
            mcm_a = action(json_input=threaded_loads(data))
        except request.IllegalAttributeName as ex:
            return dumps({"results":False})

        self.logger.log('Building new action %s by hand...'%(mcm_a.get_attribute('_id')))

        priority_set = mcm_a.inspect_priority()

        saved = adb.update( mcm_a.json() )
        if saved:
            if priority_set:
                return {"results":True , "prepid": mcm_a.get_attribute('prepid')}
            else:
                return {"results":False , "prepid": mcm_a.get_attribute('prepid'), "message":"Priorities not set properly"}
        else:
            return {"results":False , "prepid": mcm_a.get_attribute('prepid')}



class UpdateAction(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def PUT(self):
        """
        update the action with the provided json content
        """
        res = self.import_action( threaded_loads(cherrypy.request.body.read().strip()) )
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
                            if spec is None:
                                specs.pop(s)
                else:
                    if value is None:
                        content.pop(o)
        mcm_a.set_attribute('chains',chains)


        priority_set = mcm_a.inspect_priority()

        saved = adb.update( mcm_a.json() )
        if saved:
            if priority_set:
                return {"results":True , "prepid": mcm_a.get_attribute('prepid')}
            else:
                return {"results":False , "prepid": mcm_a.get_attribute('prepid'), "message":"Priorities not set properly"}
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
        data = threaded_loads(cherrypy.request.body.read().strip())

        results=[]
        for single_action in data:
            results.append(self.import_action(single_action))

        return dumps({"results": results})


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

        return dumps({"results": self.get_request(args[0])})

    def get_request(self, id):
        db = database(self.db_name)
        return db.get(id)

class SelectChain(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Allows to select a given chained request for a given action id /action_id/chain_id
        """
        return dumps({"results":'not implemented'})
        if not args:
            self.logger.error('No arguments were given.')
            return dumps({"results":'Error: No arguments were given'})

        return dumps({'results':self.select_chain(args[0], args[1])})

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
            return True
        else:
            return False

class DeSelectChain(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Allows to UN-select a given chained request for a given action id /action_id/chain_id
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given'})

        return dumps({'results':self.deselect_chain(args[0], args[1])})

    def deselect_chain(self, aid, chainid):
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
            return True
        else:
            return False


class GenerateChainedRequests(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

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

    def generate_request(self, aid, reserve=False, with_notify=True,special=False):
        adb = database('actions')
        ccdb = database('chained_campaigns')
        crdb = database('chained_requests')
        rdb = database('requests')
        if not adb.document_exists(aid):
            return {'results':False, 'message':'%s does not exist'%(aid)}

        self.logger.log('Generating all selected chained_requests for action %s' % (aid))
        mcm_a = action(adb.get(aid))
        chains = mcm_a.get_attribute('chains')
        hasChainsChanged=False 
        new_chains = []
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
                ## get the root request
                req = request(json_input=rdb.get(aid))
                new_cr['last_status']= req.get_attribute('status')
                if new_cr['last_status'] in ['submitted','done']:
                    new_cr['status']='processing'

                if special:
                    new_cr['approval'] = 'none'

                if not crdb.update(new_cr):
                    return {'results':False,'message':'could not save %s'%( new_cr['prepid'])}

                ## update the cc history
                ccdb.update(mcm_cc.json())
                new_chains.append( new_cr['prepid'] )
                # then let the root request know that it is part of a chained request
                inchains=req.get_attribute('member_of_chain')
                inchains.append(new_cr['prepid'])
                inchains.sort()
                req.set_attribute('member_of_chain',list(set(inchains)))
                req.update_history({'action': 'join chain', 'step': new_cr['prepid']})
                if with_notify:
                    req.notify("Request {0} joined chain".format(req.get_attribute('prepid')), "Request {0} has successfully joined chain {1}".format(req.get_attribute('prepid'), new_cr['prepid']), Nchild=0, accumulate=True)
                mcm_a.update_history({'action':'add','step' : new_cr['prepid']})
                rdb.update(req.json())

        if hasChainsChanged:
            #the chains parameter might have changed
            mcm_a.set_attribute('chains',chains)
            adb.update(mcm_a.json())

        #and set priorities properly to all requests concerned
        priority_set = mcm_a.inspect_priority(forChains=new_chains)

        ## do the reservation of the whole chain ?
        res=[]
        if reserve:
            for cr in new_chains:
                mcm_cr = chained_request(crdb.get( cr ))
                res.append(mcm_cr.reserve())
                crdb.update( mcm_cr.json())

        if priority_set:
            return {"results":True , "prepid": mcm_a.get_attribute('prepid')}
        else:
            return {"results":False , "prepid": mcm_a.get_attribute('prepid'), "message":"Priorities not set properly"}


class GenerateAllChainedRequests(GenerateChainedRequests):
    def __init__(self):
        GenerateChainedRequests.__init__(self)

    def GET(self,  *args):
        """
        Generate all chained requests for all actions where applicable
        """
        return dumps(self.generate_requests())

    def generate_requests(self):
        adb = database('actions')
        self.logger.log('Generating all possible (and selected) chained_requests...')
        allacs = adb.get_all(-1) # no pagination
        res=[]
        for a in allacs:
            res.append(self.generate_request(a['key']))

        return res

class SetAction(GenerateChainedRequests):
    def __init__(self):
        GenerateChainedRequests.__init__(self)
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Set the action and generate the chained request for /aid/alias or cc name/block#/stage of threshold
        """
        if len(args)<3:
            return dumps("Not enough arguments")

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

        return dumps(self.set_action( aid, cc, block, staged, threshold))

    def set_action(self, aid, cc, block, staged=None, threshold=None,reserve=False,special=False):
        adb = database('actions')
        ccdb = database('chained_campaigns')

        mcm_a = action( adb.get(aid) )
        ccs = ccdb.queries(['alias==%s'% cc])
        if not len(ccs):
            ccs = ccdb.queries(['prepid==%s'% cc])
        if not len(ccs) :
            return {"results": False, "message": "%s not a chained campaigns"%( cc )}

        mcm_cc = chained_campaign( ccs[0] )
        mcm_cc_name=mcm_cc.get_attribute('prepid')

        chains = mcm_a.get_attribute('chains')        
        if mcm_cc_name not in chains:
            #detect
            mcm_a.find_chains()
            chains = mcm_a.get_attribute('chains')

        if mcm_cc_name not in chains:
            return {"results": False, "message": "Not able to find %s for %s"%( mcm_cc_name, aid)}

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
        return self.generate_request(aid, reserve=reserve, special=special)


class DetectChains(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def GET(self,  *args):
        """
        Update the action content with the possible chains
        """
        db = database('actions')
        if not args:
            return dumps(self.find_all_chains(db))
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

        return res

from rest_api.RequestActions import RequestLister
class ActionsFromFile(RequestLister,RESTResource): 
    def __init__(self):
        RequestLister.__init__(self)
        self.retrieve_db = database('actions')
        self.access_limit = access_rights.user

    def PUT(self, *args):
        """
        Parse the posted text document for request id and request ranges for display of actions
        """
        adb = database('actions')
        all_ids = self.get_list_of_ids(adb)
        return dumps(self.get_objects( all_ids, adb))

