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
import traceback

class FlowRESTResource(RESTResource):
    def __init__(self):
        self.db_name = 'flows'
        self.db = database(self.db_name)
        self.cdb = database('campaigns')
        self.ccdb = database('chained_campaigns')
        self.adb = database('actions')
        self.f = None
        self.access_limit = 3

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

    def update_actions(self,  c):
        self.logger.log('Updating actions...')

        # find all actions that belong to a campaign
        #allacs = map(lambda x: x['value'],  self.adb.query('member_of_campaign=='+c,  0))
        allacs = self.adb.queries(['member_of_campaign==%s'%(c)])
        
        # for each action
        for ac in allacs:
            # init action object
            a = action(json_input=ac)
            # calculate the available chains
            a.find_chains()
            # save to db
            self.adb.update(a.json())

    def set_default_request_parameters(self,nc):
	# add a skeleton of the sequences of the next (landing) campaign
	# in the new flow (allows for dynamic changing of sequences upon flowing)
        rp = self.f.get_attribute('request_parameters')
        if nc:
            camp = self.cdb.get(nc)
            ## that erase all previous values in the flows requests parameters ...
            if not 'sequences' in rp or len(rp['sequences'])!= len(camp['sequences']):
                rp['sequences'] = []
                for seq in camp['sequences']:
                    rp['sequences'].append({})
                self.f.set_attribute('request_parameters', rp)


    def __compare_json(self,  old,  new):
        return self.update_derived_objects(old ,new)

    def update_derived_objects(self, old, new):
        next = new['next_campaign']
        allowed = new['allowed_campaigns']
        
        # get the changes
        tbc,  tbr = self.__compare_list(old['allowed_campaigns'],  new['allowed_campaigns'])
        
        # check to see if you need to update a campaign (if next is altered, or a new allowed campaign)
        if old['next_campaign'] != new['next_campaign'] or tbc:
            try:
                self.update_campaigns(next,  allowed)
            except Exception as ex:
                self.logger.error('Could not update campaigns. Reason: %s' % (ex))
                return dumps({"results":'Error: update_campaigns returned:'+ str(ex)})
        
        # create new chained campaigns
        try:
            #self.update_chained_campaigns(next,  tbc)
            self.update_chained_campaigns(next,  allowed) #JR. to make sure everything gets propagated
        except Exception as ex:
            self.logger.error('Could not build derived chained_campaigns. Reason: %s' % (ex))
            self.logger.error(traceback.format_exc())
            return dumps({"results":'Error while creating derived chained_campaigns: '+str(ex)})
        
        # TODO: delete all chained_campaigns that contain the to_be_removed (tbr) campaigns and 
        #               use this flow.
        
        # if reached, then successful
        return dumps({'results':True})

    def update_campaigns(self, next,  allowed):
        # check to see if next is legal
        if not self.cdb.document_exists(next):
            raise ValueError('Campaign '+str(next)+' does not exist.')
        
        if not next:
            return
        
        n = self.cdb.get(next)
        if n['root'] == 0:
            raise ValueError('Campaign '+str(next)+' is a root campaign.')
        
        # iterate through all allowed campaigns and update the next field
        for c in allowed:
            camp = campaign(json_input=self.cdb.get(c))
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
        self.logger.log('investigating for next '+next)
        if n['root'] == 0:
            self.logger.error('Campaign %s is a root campaign.' % (next))
            raise ValueError('Campaign '+str(next)+' is a root campaign.')        
        
        for c in allowed:
            #self.logger.log('investigating for '+c)
            # check to see if this chained campaign is already created
            fid = self.f.get_attribute('_id')
            ##JR. could not find the reason for the next lines
            #if fid:
            #    if self.ccdb.document_exists('chain_'+c+'_'+fid):
            #        continue
            #else:
            #    if self.ccdb.document_exists('chain_'+c):
            #        continue
                        
            # init campaign objects
            camp = self.cdb.get(c)
            #if c is NOT a root campaign
            if camp['root']==1 or camp['root']==-1:
                # get all chained campaigns that have the allowed c as the last step
                ccs = self.ccdb.queries(['last_campaign==%s'%(c)]) 
                self.logger.log('for alst campaign %s'%( c ))
                self.logger.log('found %d to deal with'%(len(ccs)))
                self.logger.log('found %s'%( map(lambda doc: doc['prepid'],ccs) ))
                # for each chained campaign
                for cc in ccs:
                    ## skipping the chained campaign that has only the last campaign in it ... WHY ?
                    #if cc['_id'] == 'chain_'+camp['_id']:
                    #    continue

                    nextName = cc['_id']+'_'+self.f.get_attribute('prepid')

                    if self.ccdb.document_exists(nextName):
                        continue

                    self.logger.log('treating '+cc['_id'])

                    # init a ccamp object based on the old
                    ccamp = chained_campaign(json_input=cc)

                    # disable it
                    ccamp.stop()
                    # update to db
                    self.ccdb.update(ccamp.json())
                    
                    # append the next campaign in the chain
                    ccamp.add_campaign(next,  self.f.get_attribute('prepid'))
                    # update the id
                    ccamp.set_attribute('_id',  nextName)#ccamp.get_attribute('_id')+'_'+self.f.get_attribute('prepid'))
                    ccamp.set_attribute('prepid',  ccamp.get_attribute('_id'))
                    
                    # reset the alias
                    ccamp.set_attribute('alias','')

                    # restart chained campaign
                    ccamp.start()
                    
                    # save new chained campaign to database
                    self.ccdb.save(ccamp.json())

            # else if c is root campaign:
            #if camp['root']==0 or camp['root']==-1:
            if camp['root']==0:
                ccamp = chained_campaign()
                # add allowed root
                ccamp.add_campaign(c) # assume root. flow=None
                            
                # add next with given flow
                ccamp.add_campaign(next,  self.f.get_attribute('prepid'))
            
                # init campaign objects
                camp = campaign(self.cdb.get(c))
                # add meta (energy)
                ### not there anymore ccamp.set_attribute('energy', camp['energy'])
            
                # add a prepid
                if fid:
                    ccamp.set_attribute('prepid',  'chain_'+camp.get_attribute('prepid')+'_'+self.f.get_attribute('_id'))
                else:
                    ccamp.set_attribute('prepid',  'chain_'+camp.get_attribute('prepid'))
                    
                ccamp.set_attribute('_id',  ccamp.get_attribute('prepid'))
            
                self.ccdb.save(ccamp.json())

            # update actions
            self.update_actions(c)


class CreateFlow(FlowRESTResource):
    def __init__(self):
        FlowRESTResource.__init__(self)

    def PUT(self,  *args,  **kwargs):
        """
        Create a flow from the provided json content
        """
        return self.create_flow(cherrypy.request.body.read().strip())
        
    def create_flow(self, jsdata):
        data = loads(jsdata)
        if '_rev' in data:
            return dumps({"results":'Cannot create a flow with _rev'})
        try:
            self.f = flow(json_input=data)
        except flow.IllegalAttributeName as ex:
            return dumps({"results":str(ex)})
        except ValueError as ex:
            self.logger.error('Could not initialize flow object. Reason: %s' % (ex)) 
            return dumps({"results":str(ex)})

        if not self.f.get_attribute('prepid'):
            self.logger.error('prepid is not defined.')
            return dumps({"results":'Error: PrepId was not defined.'})

        self.f.set_attribute('_id', self.f.get_attribute('prepid'))
        
        #uniquing the allowed campaigns if passed duplicates by mistake
        if len(list(set( self.f.get_attribute('allowed_campaigns')))) != self.f.get_attribute('allowed_campaigns'):
            self.f.set_attribute('allowed_campaigns', list(set( self.f.get_attribute('allowed_campaigns'))) )
        
        self.logger.log('Creating new flow %s ...' % (self.f.get_attribute('_id')))


        nc = self.f.get_attribute('next_campaign')
        if nc:
            if not self.cdb.document_exists(nc):
                return dumps({"results":'%s is not a valid campaign for next'%( nc)})

        ## adjust the requests parameters based on what was provided as next campaign
        self.set_default_request_parameters(nc)
	
	# update history
        self.f.update_history({'action':'created'})
        
        # save the flow to db
        if not self.db.save(self.f.json()):
            self.logger.error('Could not save newly created flow %s to database.' % (self.f.get_attribute('_id')))  
            return dumps({"results":False})

        #return right away instead of trying and failing on missing next or allowed
        if not nc or not len(self.f.get_attribute('allowed_campaigns')):
            return dumps({"results": True})

        ##consistency check 
        if self.f.get_attribute('next_campaign') in self.f.get_attribute('allowed_campaigns'):
            return dumps({ "results" : False, message : "Cannot have next campaign in the allowed campaign" })
        
        # update all relevant campaigns with the "Next" parameter
        try:
            self.update_campaigns(self.f.get_attribute('next_campaign'), self.f.get_attribute('allowed_campaigns'))
        except Exception as ex:
            print 'Error: update_campaigns returned:'+ str(ex)
            return dumps({"results":'Error: update_campaigns returned:'+ str(ex)})
            
        # create all possible chained_campaigns from the next and allowed campaigns
        try:
            self.update_chained_campaigns(self.f.get_attribute('next_campaign'), self.f.get_attribute('allowed_campaigns'))
        except Exception as ex:
           self.logger.error('Could not build derived chained_campaigns for flow %s. Reason: %s' % (self.f.get_attribute('_id'), ex)) 
           return dumps({"results":'Error while creating derived chained_campaigns: '+str(ex)})
        
        # save to database
        return dumps({"results":True})
        

    """


    ## this is commmented out instead of removed, to keep an eye on what it was looking like before moving to a central rest class for flows: dead-wood
    # create all possible chained campaigns going from allowed.member to next
    def update_chained_campaigns(self,  next, allowed):
        # check to see if next is legal
        if not self.cdb.document_exists(next):
            raise ValueError('Campaign '+str(next)+' does not exist.')
        
        n = self.cdb.get(next)

        self.logger.log('Updating all derived chained_campaigns...')
         
        if n['root'] == 0:
            self.logger.error('Campaign %s is a root campaign' % (next))
            raise ValueError('Campaign '+str(next)+' is a root campaign.')        
        
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
                # get all flows, that have the allowed c as the next campaign
                vflows = self.db.query('next_campaign=='+c)
                vfs = map(lambda x: x['value'],  vflows)
                ccs = []
                
                for vf in vfs:
                    # get all campaigns that have the allowed c as the last step
                    #ccamps = self.ccdb.query('last_campaign=="%5B%22'+c+'%22%2C%22'+vf['_id']+'%22%5D"')
                    ccamps = self.ccdb.raw_query('last_campaign',  options={"key":[c,  vf['_id']]})
                    #ccamps = self.ccdb.query('last_campaign==['+c+','+vf['_id']+']')
                    ccslst = map(lambda x: x['value'],  ccamps)
                    ccs.extend(ccslst)
                
                # for each chained campaign
                for cc in ccs:
                    if cc['_id'] == 'chain_'+camp['_id']:
                        continue
                    
                    # init a ccamp object based on the old
                    ccamp = chained_campaign(json_input=cc)
                    # disable it
                    ccamp.stop()
                    # update to db
                    self.ccdb.update(ccamp.json())
                    
                    # append the next campaign in the chain
                    ccamp.add_campaign(next,  self.f.get_attribute('prepid'))
                    # update the id
                    ccamp.set_attribute('_id',  ccamp.get_attribute('_id')+'_'+self.f.get_attribute('prepid'))
                    ccamp.set_attribute('prepid',  ccamp.get_attribute('_id'))
                    ccamp.set_attribute('alias',  '')
                    
                    # restart chained campaign
                    ccamp.start()

                    # remove CouchDB revision trash
                    new_ccamp = ccamp.json()
                    del new_ccamp['_rev']
                    
                    # save new chained campaign to database
                    #self.ccdb.save(ccamp.json())
                    self.ccdb.save(new_ccamp)

            # else if c is root campaign:
            if camp['root']==0 or camp['root']==-1:
                ccamp = chained_campaign()
                # add allowed root
                ccamp.add_campaign(c) # assume root. flow=None
                            
                # add next with given flow
                ccamp.add_campaign(next,  self.f.get_attribute('prepid'))
            
                # init campaign objects
                camp = self.cdb.get(c)
                # add meta (energy)
                ## JR: this is not a member any-more
                #ccamp.set_attribute('energy', camp['energy'])
            
                # add a prepid
                if fid:
                    ccamp.set_attribute('prepid',  'chain_'+camp['prepid']+'_'+self.f.get_attribute('_id'))
                else:
                    ccamp.set_attribute('prepid',  'chain_'+camp['prepid'])
                    
                ccamp.set_attribute('_id',  ccamp.get_attribute('prepid'))
            
                self.ccdb.save(ccamp.json())

            # update actions
            self.update_actions(c)
            """

class UpdateFlow(FlowRESTResource):
    def __init__(self):
        FlowRESTResource.__init__(self)
        
    def PUT(self):
        """
        Update a flow with the provided content
        """
        return self.update_flow(cherrypy.request.body.read().strip())

    def update_flow(self, jsdata):
        data = loads(jsdata)
        if not '_rev' in data:
            return dumps({"results":"Cannot update without _rev"})
        try:
            self.f = flow(json_input=data)
        except flow.IllegalAttributeName as ex:
            return dumps({"results":str(ex)})
        
        if not self.f.get_attribute('prepid') and not self.f.get_attribute('_id'):
            self.logger.error('prepid returned was None')
            raise ValueError('Prepid returned was None')
        
        # find out what is the change
        old = self.db.get(self.f.get_attribute('_id'))

        #uniquing the allowed campaigns if passed duplicates by mistake
        if len(list(set( self.f.get_attribute('allowed_campaigns')))) != self.f.get_attribute('allowed_campaigns'):
            self.f.set_attribute('allowed_campaigns', list(set( self.f.get_attribute('allowed_campaigns'))) )

        nc = self.f.get_attribute('next_campaign')
        if nc :
            if not self.cdb.document_exists(nc):
                return dumps({"results":'%s is not a valid campaign for next'%( nc)})

        ## adjust the requests parameters based on what was provided as next campaign
        self.set_default_request_parameters(nc)

	# update history
	self.f.update_history({'action': 'update'})
        
        # save to db
        if not self.db.update(self.f.json()):
            self.logger.error('Could not update flow %s. Reason: %s' % (self.f.get_attribute('_id'), ex)) 
            return dumps({'results':False})
        
        return self.update_derived_objects(old,  self.f.json())
                


class DeleteFlow(RESTResource):
    def __init__(self):
        self.db_name = 'flows'
        self.fdb = database(self.db_name)
        self.ccdb = database('chained_campaigns')
        self.cdb = database('campaigns')
    
    def DELETE(self, *args):
        """
        Delete a flow and all related objects
        """
        if not args:
            return dumps({"results":'Error: No Arguments were provided.'})
        return self.delete_flow(args[0])
    
    def delete_flow(self, fid):

        # delete all chained campaigns with this flow
        ## exception can be thrown on impossibility of removing
        try:
            self.delete_chained_campaigns(fid)
        except Exception as ex:
            return dumps({'results':str(ex)})
        
        # update relevant campaigns
        try:
            self.update_campaigns(fid)
        except Exception as ex:
            return dumps({'results':str(ex)})
        
        return dumps({"results":self.fdb.delete(fid)})
        

    def delete_chained_campaigns(self,  fid):
        # get all campaigns that contain the flow : fid
        #ccamps = map(lambda x: x['value'],self.ccdb.query('contains=='+fid),page=-1)
        ccamps = self.ccdb.queries(['contains==%s'%(fid)])
        
        # check that all relelvant chained campaigns are empty
        crdb = database('chained_requests')
        for cc in ccamps:
            #mcm_crs = map(lambda x: x['value'], crdb.query('member_of_campaign=='+cc['prepid']),page=-1)
            mcm_crs = crdb.queries(['member_of_campaign==%s'%(cc['prepid'])])
            if len(mcm_crs) != 0:
                raise Exception('Impossible to delete flow %s, since %s is not an empty chained campaign'%(fid,
                                                                                                           cc['prepid']))
        
        ## all chained campaigns are empty : 
        #=> remove them one by one
        for cc in ccamps:
            self.ccdb.delete(cc['prepid'])


    def update_campaigns(self,  fid):
        # get the flow
        f = self.fdb.get(fid)
        
        next_c = f['next_campaign']
        # get all campaigns that contain the flow's next campaign in the campaign's next
        #camps = map(lambda x: x['value'],self.cdb.query('next=='+next_c,page=-1))
        camps = self.cdb.queries(['next==%s'%(next_c)])
        
        for c in camps:
            ##check that nothing allows to flow in it
            # get the list of chained campaign that still contain both 
            mcm_ccs = map(lambda x: x['value'],self.ccdb.queries(['contains=='+c['prepid'], 'contains=='+next_c]))
            if not len(mcm_ccs):
                #there a no chained campaign left, that uses both that campaign and next_c
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
        """
        Retrieve the json content of a given flow id
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":{}})
        return self.get_request(args[0])
    
    def get_request(self, data):
        return dumps({"results":self.db.get(prepid=data)})
        
class ApproveFlow(RESTResource):
    def __init__(self):
        self.db = database('flows')
        self.access_limit = 3

    def GET(self,  *args):
        """
        Move the given flow id to the next approval /flow_id , or the provided index /flow_id/index
        """
        if not args:
            self.logger.error('No arguments were given')
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
        
    def approve(self,  rid,  val):
        if not self.db.document_exists(rid):
            return {"prepid" : rid, "results":'Error: The given flow id does not exist.'}
        f = flow(json_input=self.db.get(rid))
        
	try:
            f.approve(int(val))
        except:
            return {"prepid": rid, "results":False}
        
        return {"prepid": rid, "results":self.db.update(f.json())}
