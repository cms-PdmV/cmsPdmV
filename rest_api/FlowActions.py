#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from couchdb_layer.prep_database import database
from RestAPIMethod import RESTResource
from RequestPrepId import RequestPrepId
from json_layer.campaign import campaign
from json_layer.chained_campaign import chained_campaign
from json_layer.flow import flow
from json_layer.action import action

class CreateFlow(RESTResource):
    def __init__(self):
        self.db_name = 'flows'
        self.db = database(self.db_name)
        self.cdb = database('campaigns')
        self.ccdb = database('chained_campaigns')
        self.adb = database('actions')
        self.f = None

    def PUT(self):
        return self.create_flow(cherrypy.request.body.read().strip())
        
    def create_flow(self, data):
        try:
            self.f = flow('TEST', json_input=loads(data))
        except flow.IllegalAttributeName as ex:
            return dumps({"results":str(ex)})

        if not self.f.get_attribute('prepid'):
            return dumps({"results":'Error: PrepId was not defined.'})

        self.f.set_attribute('_id', self.f.get_attribute('prepid'))
        
        # save the flow to db
        if not self.db.save(self.f.json()):
            return dumps({"results":False})
        
        # update all relevant campaigns
        try:
            self.update_campaigns(self.f.get_attribute('next_campaign'), self.f.get_attribute('allowed_campaigns'))
        except Exception as ex:
            return dumps({"results":'Error: update_campaigns returned:'+ str(ex)})
            
        # create all possible chained_campaigns from the next and allowed campaigns
        try:
            self.create_chained_campaigns(self.f.get_attribute('next_campaign'), self.f.get_attribute('allowed_campaigns'))
        except Exception as ex:
           return dumps({"results":'Error while creating derived chained_campaigns: '+str(ex)})
        
        # save to database
        return dumps({"results":True})
    
    # create all possible chained campaigns going from allowed.member to next
    def create_chained_campaigns(self,  next, allowed):
        for c in allowed:
            # check to see if this chained campaign is already created
            fid = self.f.get_attribute('_id')
            if fid:
                if self.ccdb.document_exists('chain_'+c+'_'+fid):
                    continue
            else:
                if self.ccdb.document_exists('chain_'+c):
                    continue
                        
            
            # init campaign objects
            camp = self.cdb.get(c)
            
            #if c is NOT a root campaign
            if camp['root']==1 or camp['root']==-1:
                # get all campaigns that have the allowed c as the last step
                ccamps = self.ccdb.query('last_campaign==["'+c+'", '+self.f.get_attribute('prepid')+']')
                ccs = map(lambda x: x['value'],  ccamps)
                # for each chained campaign
                for cc in ccs:
                    # init a ccamp object based on the old
                    ccamp = chained_campaign('',  json_input=cc)
                    # disable it
                    ccamp.stop()
                    # update to db
                    self.ccdb.update(ccamp.json())
                    
                    
                    # append the next campaign in the chain
                    ccamp.add_campaign(next,  self.f.get_attribute('prepid'))
                    # update the id
                    ccamp.set_attribute('_id',  ccamp.get_attribute('_id')+'_'+self.f.get_attribute('prepid'))
                    ccamp.set_attribute('prepid',  ccamp.get_attribute('_id'))
                    
                    # save new chained campaign to database
                    self.ccdb.save(ccamp.json())         
                    
            # else if c is root campaign:
            elif camp['root']==0 or camp['root']==-1:
                ccamp = chained_campaign('automatic')
                # add allowed root
                ccamp.add_campaign(c) # assume root. flow=None
            
                # add next with given flow
                ccamp.add_campaign(next,  self.f.get_attribute('prepid'))
            
                # init campaign objects
                camp = self.cdb.get(c)
                # add meta (energy)
                ccamp.set_attribute('energy', camp['energy'])
            
                # add a prepid
                if fid:
                    ccamp.set_attribute('prepid',  'chain_'+camp['prepid']+'_'+self.f.get_attribute('_id'))
                else:
                    ccamp.set_attribute('prepid',  'chain_'+camp['prepid'])
                    
                ccamp.set_attribute('_id',  ccamp.get_attribute('prepid'))
            
                self.ccdb.save(ccamp.json())

            # update actions
            self.update_actions(c)
    
    def update_actions(self,  c):
        # find all actions that belong to a campaign
        allacs = map(lambda x: x['value'],  self.adb.query('member_of_campaign=='+c))
        
        # for each action
        for ac in allacs:
            # init action object
            a = action('',  json_input=ac)
            # calculate the available chains
            a.find_chains()
            # save to db
            self.adb.update(a.json())
        

    def update_campaigns(self, next,  allowed):
        # iterate through all allowed campaigns and update the next field
        for c in allowed:
            camp = campaign('test',  json_input=self.cdb.get(c))
            
            try:
                # append campaign
                camp.add_next(next)
            except campaign.CampaignExistsException as ex:
                print str(ex)
            
            print camp.json()['_rev']
            
            # save to database
            self.cdb.update(camp.json())

class UpdateFlow(RESTResource):
    def __init__(self):
        self.db_name = 'flows'
        self.db = database(self.db_name)
        self.cdb = database('campaigns')
        self.ccdb = database('chained_campaigns')
        self.adb = database('actions')        
        self.json = {}
        self.f = None
        
    def PUT(self):
        return self.update_flow(cherrypy.request.body.read().strip())

    def update_flow(self, data):
        try:
            self.f = flow('TEST', json_input=loads(data))
        except flow.IllegalAttributeName as ex:
            print str(ex)
            return dumps({"results":str(ex)})
        
        if not self.f.get_attribute('prepid') and not self.f.get_attribute('_id'):
            raise ValueError('Prepid returned was None')
        
        # find out what is the change
        old = self.db.get(self.f.get_attribute('_id'))
        
        # save to db
        if not self.db.update(self.f.json()):
            return dumps({'results':False})
        
        return self.__compare_json(old,  self.f.json())
                
    def __compare_json(self,  old,  new):
        next = new['next_campaign']
        allowed = new['allowed_campaigns']
        
        # get the changes
        tbc,  tbr = self.__compare_list(old['allowed_campaigns'],  new['allowed_campaigns'])
        
        # check to see if you need to update a campaign (if next is altered, or a new allowed campaign)
        if old['next_campaign'] != new['next_campaign'] or tbc:
            try:
                self.update_campaigns(next,  allowed)
            except Exception as ex:
                print 'Error: update_campaigns returned:'+ str(ex)
                return dumps({"results":'Error: update_campaigns returned:'+ str(ex)})
        
        # create new chained campaigns
        try:
            self.update_chained_campaigns(next,  tbc)
        except Exception as ex:
            print 'Error while creating derived chained_campaigns: '+str(ex)
            return dumps({"results":'Error while creating derived chained_campaigns: '+str(ex)})
        
        # TODO: delete all chained_campaigns that contain the to_be_removed (tbr) campaigns and 
        #               use this flow.
        
        # if reached, then successful
        return dumps({'results':True})

    # takes  a 2 lists and returns a tuple of what is present in the second and not in the first and
    # what was present in the first and not in the second
    # ( in_new_not_old, in_old_not_new)
    def __compare_list(self,  old,  new):
        # compute diff of two lists ( a - b )
        def diff(a, b):
            b = set(b)
            return [aa for aa in a if aa not in b]
        
        # init 
        to_be_removed,  to_be_created = [], []
        
        # compute old - new
        to_be_removed = diff(old,  new)
        
        # compute new - old
        to_be_created = diff(new,  old)
        
        # return the tuple
        return to_be_created,  to_be_removed

    def update_campaigns(self, next,  allowed):
        # check to see if next is legal
        if not self.cdb.document_exists(next):
            raise ValueError('Campaign '+str(next)+' does not exist.')
        
        n = self.cdb.get(next)
        if n['root'] == 0:
            raise ValueError('Campaign '+str(next)+' is not a root campaign.')
        
        # iterate through all allowed campaigns and update the next field
        for c in allowed:
            camp = campaign('',  json_input=self.cdb.get(c))
            try:
                # append campaign
                camp.add_next(next)
            except campaign.CampaignExistsException as ex:
                pass
            
            # save to database
            self.cdb.update(camp.json())
    
    # create all possible chained campaigns going from allowed.member to next
    def update_chained_campaigns(self,  next, allowed):
        # check to see if next is legal
        if not self.cdb.document_exists(next):
            raise ValueError('Campaign '+str(next)+' does not exist.')
        
        n = self.cdb.get(next)
        if n['root'] == 0:
            raise ValueError('Campaign '+str(next)+' is not a root campaign.')        
        
        for c in allowed:
            # check to see if this chained campaign is already created
            fid = self.f.get_attribute('_id')
            if fid:
                if self.ccdb.document_exists('chain_'+c+'_'+fid):
                    continue
            else:
                if self.ccdb.document_exists('chain_'+c):
                    continue
                        
            # init campaign objects
            camp = self.cdb.get(c)
            #if c is NOT a root campaign
            if camp['root']==1 or camp['root']==-1:
                # get all campaigns that have the allowed c as the last step
                ccamps = self.ccdb.query('last_campaign=='+c)
                ccs = map(lambda x: x['value'],  ccamps)

                # for each chained campaign
                for cc in ccs:
                    if cc['_id'] == 'chain_'+camp['_id']:
                        continue

                    # init a ccamp object based on the old
                    ccamp = chained_campaign('',  json_input=cc)
                    # disable it
                    ccamp.stop()
                    # update to db
                    self.ccdb.update(ccamp.json())
                    
                    # append the next campaign in the chain
                    ccamp.add_campaign(next,  self.f.get_attribute('prepid'))
                    # update the id
                    ccamp.set_attribute('_id',  ccamp.get_attribute('_id')+'_'+self.f.get_attribute('prepid'))
                    ccamp.set_attribute('prepid',  ccamp.get_attribute('_id'))
                    
                    # restart chained campaign
                    ccamp.start()
                    
                    # save new chained campaign to database
                    self.ccdb.save(ccamp.json())

            # else if c is root campaign:
            if camp['root']==0 or camp['root']==-1:
                ccamp = chained_campaign('automatic')
                # add allowed root
                ccamp.add_campaign(c) # assume root. flow=None
                            
                # add next with given flow
                ccamp.add_campaign(next,  self.f.get_attribute('prepid'))
            
                # init campaign objects
                camp = self.cdb.get(c)
                # add meta (energy)
                ccamp.set_attribute('energy', camp['energy'])
            
                # add a prepid
                if fid:
                    ccamp.set_attribute('prepid',  'chain_'+camp['prepid']+'_'+self.f.get_attribute('_id'))
                else:
                    ccamp.set_attribute('prepid',  'chain_'+camp['prepid'])
                    
                ccamp.set_attribute('_id',  ccamp.get_attribute('prepid'))
            
                self.ccdb.save(ccamp.json())

            # update actions
            self.update_actions(c)

    def update_actions(self,  c):

        # find all actions that belong to a campaign
        allacs = map(lambda x: x['value'],  self.adb.query('member_of_campaign=='+c,  0))
        
        # for each action
        for ac in allacs:
            # init action object
            a = action('',  json_input=ac)
            # calculate the available chains
            a.find_chains()
            # save to db
            self.adb.update(a.json())

class DeleteFlow(RESTResource):
    def __init__(self):
        self.db_name = 'flows'
        self.db = database(self.db_name)
        self.ccdb = database('chained_campaigns')
        self.cdb = database('campaigns')
    
    def DELETE(self, *args):
        if not args:
            return dumps({"results":'Error: No Arguments were provided.'})
        return self.delete_request(args[0])
    
    def delete_request(self, id):
        # update relevant campaigns
        try:
            self.update_campaigns(id)
        except Exception as ex:
            return dumps({'results':str(ex)})
        
        # delete all chained campaigns with this flow
        try:
            self.delete_chained_campaigns(id)
        except Exception as ex:
            return dumps({'results':str(ex)})
            
        return dumps({"results":self.db.delete(id)})
        
    # ########################################### #
    # TODO: Na kanw ta chained campaigns na diagrafontai me ton deleter apo to CHainedCampaignActions
    # ########################################### #
    def delete_chained_campaigns(self,  fid):
        # get all campaigns that contain the flow fid
        ccamps = self.ccdb.query('flow=='+fid)
        
        # delete all chained campaigns returned
        for cc in ccamps:
            try:
                self.ccdb.delete(cc['prepid'])
            except Exception as ex:
                return dumps({'results':str(ex)})
    
    def update_campaigns(self,  fid):
        # get the flow
        f = self.db.get(fid)
        
        # get all campaigns that contain the campaign in the flow's next
        camps = self.cdb.query('next=='+f['next_campaign'])
        
        for c in camps:
            c['next'].remove(fid)
            try:
                self.cdb.update(c)
            except Exception as ex:
                return dumps({'results':str(ex)})

class GetFlow(RESTResource):
    def __init__(self):
        self.db_name = 'flows'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        if not args:
            return dumps({"results":{}})
        return self.get_request(args[0])
    
    def get_request(self, data):
        return dumps({"results":self.db.get(prepid=data)})
