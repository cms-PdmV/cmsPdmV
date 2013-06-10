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
from tools.priority import priority

class CreateAction(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.db = database(self.db_name)
        self.action = None

    def PUT(self):
        return self.import_request(cherrypy.request.body.read().strip())

    def import_request(self, data):
        try:
            self.action = action(json_input=loads(data))
        except request.IllegalAttributeName as ex:
            return dumps({"results":False})

        self.logger.log('Building new action %s by hand...'%(self.action.get_attribute('_id')))
        
        self.action.inspect_priority()

        rd = database('requests')
        if rd.document_exists(self.action.get_attribute('prepid')):
            r= request(rd.get(self.action.get_attribute('prepid')))
            self.action.set_attribute('dataset_name',r.get_attribute('dataset_name'))

	return dumps({'results':self.db.save(self.action.json())})


class UpdateAction(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.db = database(self.db_name)
        self.action = None

    def PUT(self):
        return self.import_request(cherrypy.request.body.read().strip())

    def import_request(self, data):
        try:
            self.action = action(json_input=loads(data))
        except request.IllegalAttributeName as ex:
            return dumps({"results":False})

        self.logger.log('Updating action "%s" by hand...' % (self.action.get_attribute('_id')))

        self.action.inspect_priority()
        """
        ##JR: until put in the proper place
        chains=self.action.get_attribute('chains')
        crdb = database('chained_requests')
        
        ## solution with db query, which might make things extra slow at some point
        #acrs = map(lambda x: x['value'],  crdb.query('root_request=='+self.action.get_attribute('_id')))
        #for acr in acrs:
        #    cr=chained_request(acr)
        #    cc=cr.get_attribute('member_of_campaign')
        #    if cc in chains and chains[cc]['flag'] and chains[cc]['block_number']:
        #        cr.set_priority(chains[cc]['block_number'])
        #        self.logger.log('Set priority block %s to %s'%(chains[cc]['block_number'],cr.get_attribute('prepid')))
        #    else:
        #        self.logger.error('Could not set block %s to %s'%(chains[cc]['block_number'],cr.get_attribute('prepid')))

        ##alternative, using a new member of action['chains'][<cc>]['chains'] containing the list of chained request created for that action
        #chains=self.action.get_attribute('chains')
        for inchain in chains:
            if chains[inchain]['flag']:
                if 'chains' in chains[inchain]:
                    for acr in chains[inchain]['chains']:
                        cr=chained_request(crdb.get(acr))
                        cc=cr.get_attribute('member_of_campaign')
                        if chains[cc]['block_number']:
                            cr.set_priority(chains[cc]['block_number'])
                            self.logger.log('Set priority block %s to %s'%(chains[cc]['block_number'],cr.get_attribute('prepid')))
                        else:
                            self.logger.error('Could not set block %s to %s'%(chains[cc]['block_number'],cr.get_attribute('prepid')))
        """
        rd = database('requests')
        if rd.document_exists(self.action.get_attribute('prepid')):
            r= request(rd.get(self.action.get_attribute('prepid')))
            self.action.set_attribute('dataset_name',r.get_attribute('dataset_name'))
            
        return dumps({'results':self.db.update(self.action.json())})

class UpdateMultipleActions(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.db = database(self.db_name)
        self.single_updater = UpdateAction()
        self.action_getter = GetAction()

    def PUT(self):
        self.logger.log('Updating multiple actions')
        data = loads(cherrypy.request.body.read().strip())
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

class GetAction(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given'})
            
        return self.get_request(args[0])
    
    def get_request(self, id):
        return dumps({"results":self.db.get(id)})

class SelectChain(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        if not args:
            self.logger.error('No arguments were given.')
            return dumps({"results":'Error: No arguments were given'})
            
        return self.select_chain(args[0],  args[1])
    
    def select_chain(self, id,  chainid):
        self.logger.log('Selecting chain %s for action %s...' % (chainid, id))
        # if action exists
        if self.db.document_exists(id):
            # initialize the object
            a = action(json_input=self.db.get(id))
            # and set it to 1 (default ?)
            a.select_chain(chainid)
            
            # save
            self.db.update(a.json())
            return dumps({'results':True})
        else:
            return dumps({"results":False})

class DeSelectChain(RESTResource):
    def __init__(self):
        self.db_name = 'actions'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given'})
            
        return self.deselect_chain(args[0],  args[1])
    
    def deselect_chain(self,  aid,  chainid):
        self.logger.log('Deselecting chain %s for action %s...' % (chainid, aid))        
        # if action exists
        if self.db.document_exists(aid):
            # initialize the object
            a = action(json_input=self.db.get(aid))
            # and set it to 1 (default ?)
            a.deselect_chain(chainid)
            # save
            self.db.update(a.json())
            return dumps({'results':True})
        else:
            return dumps({"results":False})

class GenerateChainedRequests(RESTResource):
    def __init__(self):
        self.db = database('actions')
        self.ccdb = database('chained_campaigns')
        self.crdb = database('chained_requests')
        self.rdb = database('requests')

    def GET(self,  *args):
        if not args:
            self.logger.error('No arguments were given')
            return dumps({'results':'Error: No arguments were given'})
        
        return self.generate_request(args[0])
    
    def generate_request(self,  pid):
        if not self.db.document_exists(pid):
            return dumps({'results':'Error: PrepId '+pid+' does not exist in the database.'})
        
        self.logger.log('Generating all selected chained_requests for action %s' % (pid)) 
        
        # init action
        act = action(json_input=self.db.get(pid))
 
        ##this needs to go AFTER the chained requests are generated
        #act.inspect_priority()

        # get chains
        chains = act.get_attribute('chains')
        hasChainsChanged=False
        # iterate through chains
        for cc in chains:
            if chains[cc]['flag']:
                # check if the chain already exists
                accs = map(lambda x: x['value'],  self.crdb.query('root_request=='+pid))
                flag = False
                for acc in accs:
                    if cc == acc['_id'].split('-')[1]:
                        flag = acc['_id']
                        break

                if not 'chains' in chains[cc]:
                    chains[cc]['chains']=[]
                    hasChainsChanged=True
                if flag:
                    #backward filling: could be removed at some point
                    if not flag in chains[cc]['chains']:
                        chains[cc]['chains'].append(flag)
                        hasChainsChanged=True
                    self.logger.error('A chained request "%s" already exists for chained_campaign %s' % (flag,cc), level='warning')
                    ## then let the root request know that it is part of a chained request, in case not already done
                    req = request(json_input=self.rdb.get(pid))
                    inchains=req.get_attribute('member_of_chain')
                    if not flag in inchains:
                        inchains.append(flag)
                        req.set_attribute('member_of_chain',list(set(inchains)))
                        self.rdb.update(req.json())
                    continue
                
                # init chained campaign
                ccamp = chained_campaign(json_input=self.ccdb.get(cc))
                # create the chained request
                new_req = ccamp.generate_request(pid)
                
                chains[cc]['chains'].append(new_req['prepid'])
                hasChainsChanged=True

                # save to database
                if not self.crdb.save(new_req):
                    self.logger.error('Could not save modified action %s to database.' % (pid))  
                    return dumps({'results':False})
                    
                ##I am not sure it is necessary to update the chained_campaign itself: legacy 
                self.ccdb.update(ccamp.json())

                # then let the root request know that it is part of a chained request
                req = request(json_input=self.rdb.get(pid))
                inchains=req.get_attribute('member_of_chain')
                inchains.append(new_req['prepid'])
                req.set_attribute('member_of_chain',list(set(inchains)))
                self.rdb.update(req.json())
        
        if hasChainsChanged:
            #the chains parameter might have changed
            act.set_attribute('chains',chains)
            self.db.update(act.json())

        #and set priorities properly to all requests concerned
        act.inspect_priority()

        return dumps({'results':True})

class GenerateAllChainedRequests(GenerateChainedRequests):
    def __init__(self):
        GenerateChainedRequests.__init__(self)
        
    def GET(self,  *args):
        return self.generate_requests()
    
    def generate_requests(self):
        self.logger.log('Generating all possible (and selected) chained_requests...')
        allacs = self.db.get_all(-1) # no pagination
        for a in allacs:
            self.generate_request(a['key'])
        
        return dumps({'results':True})

"""
class GenerateAllChainedRequests(RESTResource):
    def __init__(self):
        self.db = database('actions')
        self.ccdb = database('chained_campaigns')
        self.crdb = database('chained_requests')
        self.rdb = database('requests')

    def GET(self,  *args):
        return self.generate_requests()
        
    def generate_requests(self):
        self.logger.log('Generating all possible (and selected) chained_requests...')
        allacs = self.db.get_all(-1) # no pagination
        for a in allacs:
            self.generate_request(a['key'])
        
        return dumps({'results':True})
            
    def generate_request(self,  id):
        if not self.db.document_exists(id):
            return dumps({'results':'Error: PrepId '+id+' does not exist in the database.'})
        
        # init action
        act = action(json_input=self.db.get(id))

        act.inspect_priority() 
        # get chains
        chains = act.get_attribute('chains')
        hasChainsChanged=False

        # iterate through chains
        for cc in chains:
            if chains[cc]['flag']:
                # check if the chain already exists
                accs = map(lambda x: x['value'],  self.crdb.query('root_request=='+id))
                flag = False
                for acc in accs:
                    if cc == acc['_id'].split('-')[1]:
                        flag = acc['_id']
                        break
                    
                if not 'chains' in chains[cc]:  
                    chains[cc]['chains']=[]      
                    hasChainsChanged=True     

                if flag:
                    #backward filling: could be removed at some point
                    if not flag in chains[cc]['chains']:
                        chains[cc]['chains'].append(flag)
                        hasChainsChanged=True
                    self.logger.error('A chained request "%s" already exists for chained_campaign %s' % (flag,cc), level='warning')
                    ## then let the root request know that it is part of a chained request, in case not already done
                    req = request(json_input=self.rdb.get(id))
                    inchains=req.get_attribute('member_of_chain')
                    if not flag in inchains:
                        inchains.append(flag)
                        req.set_attribute('member_of_chain',list(set(inchains)))
                        self.rdb.update(req.json())
                    continue
                
                # init chained campaign
                ccamp = chained_campaign(json_input=self.ccdb.get(cc))
                # create the chained request
                new_req = ccamp.generate_request(id)

                chains[cc]['chains'].append(new_req['prepid'])
                hasChainsChanged=True
                # save to database
                if not self.crdb.save(new_req):
                    self.logger.error('Could not save newly created chained_request %s to database' % (id))
                    return dumps({'results':False})
                    
                self.ccdb.update(ccamp.json())
                # then let the root request know that it is part of a chained request
                req = request(json_input=self.rdb.get(id))
                inchains=req.get_attribute('member_of_chain')
                inchains.append(new_req['prepid'])
                req.set_attribute('member_of_chain',list(set(inchains)))
                self.rdb.update(req.json())
        
        if hasChainsChanged: 
            #the chains parameter might have changed 
            act.set_attribute('chains',chains)        
            self.db.update(act.json())   

        return dumps({'results':True})
"""            
        
class DetectChains(RESTResource):
    def __init__(self):
        self.db = database('actions')
    
    def GET(self,  *args):
        if not args:
            return self.find_all_chains()
        return self.find_chains(args[0])
    
    def find_chains(self,  aid):
        self.logger.log('Identifying all possible chains for action %s' % (aid))
        ac = action(json_input=self.db.get(aid))
        ac.find_chains()
        return dumps({'results':self.db.update(ac.json())})
    
    def find_all_chains(self):
        self.logger.log('Identifying all possible chains for all actions in the database...')
        try:
            map(lambda x: self.find_chains(x['key']),  self.db.get_all(-1))
        except Exception as ex:
            self.logger.error('Could not finish detecting chains. Reason: %s' % (ex))   
            return dumps({'results': str(ex)})
        return dumps({'results': True})
        
