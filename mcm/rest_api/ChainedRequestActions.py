#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResource
from RequestChainId import RequestChainId
from json_layer.chained_request import chained_request
from json_layer.request import request

"""
## import the rest api for wilde request search and dereference to chained_requests using member_of_chain
class SearchChainedRequest(RESTResource):
    def __init__(self):
        self.access_limit = 0
        self.getter

    def PUT(self):
"""        


class CreateChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'
        self.db = database(self.db_name)
        self.req = None
        self.access_limit = 4

    def PUT(self):
        """
        Create a chained request from the provided json content
        """
        return self.import_request(cherrypy.request.body.read().strip())
    def import_request(self, data):
        try:
            self.req = chained_request(json_input=loads(data))
        except chained_request.IllegalAttributeName as ex:
            return dumps({"results":False})

        id = RequestChainId().generate_id(self.req.get_attribute('pwg'), self.req.get_attribute('member_of_campaign'))
        self.req.set_attribute('prepid',loads(id)['results'])

        if not self.req.get_attribute('prepid'):
            self.logger.error('prepid returned was None')
            raise ValueError('Prepid returned was None')

        self.req.set_attribute('_id', self.req.get_attribute('prepid'))
        self.json = self.req.json()

        self.logger.log('Creating new chained_request %s' % (self.json['_id']))
	
	# update history with the submission details
	self.req.update_history({'action': 'created'})

        return self.save_request()

    def save_request(self):
        if self.db.save(self.req.json()):
            self.logger.log('new chained_request successfully saved.')
            return dumps({"results":True})
        else:
            self.logger.error('Could not save new chained_request to database')
            return dumps({"results":False})

class UpdateChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'
        self.db = database(self.db_name)
        self.request = None
        self.access_limit = 4

    def PUT(self):
        """
        Update a chained request from the provided json content
        """
        return self.update_request(cherrypy.request.body.read().strip())

    def update_request(self, data):
        try:
            self.request = chained_request(json_input=loads(data))
        except chained_request.IllegalAttributeName as ex:
            return dumps({"results":False})

        if not self.request.get_attribute('prepid') and not self.request.get_attribute('_id'):
            self.logger.error('prepid returned was None') 
            raise ValueError('Prepid returned was None')
            #self.request.set_attribute('_id', self.request.get_attribute('prepid')

        self.logger.log('Updating chained_request %s' % (self.request.get_attribute('_id')))

	# update history
	self.request.update_history({'action': 'update'})

        return self.save_request()
        
    def save_request(self):
        return dumps({"results":self.db.update(self.request.json())})

class DeleteChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'
        self.db = database(self.db_name)
    
    def DELETE(self, *args):
        """
        Simply delete a chained requests
        """
        if not args:
            return dumps({"results":False})
        return self.delete_request(args[0])
    
    def delete_request(self, id):
        return dumps({"results":self.db.delete(id)})

class GetChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'
        self.db = database(self.db_name)
    
    def GET(self, *args):
        """
        Retrieve the content of a chained request id
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":{}})
        return self.get_request(args[0])
    
    def get_request(self, data):
        return dumps({"results":self.db.get(prepid=data)})

# REST method to add a new request to the chain
class AddRequestToChain(RESTResource):
    def __init__(self):
        self.rdb = database('requests')
        self.db = database('chained_requests')
        self.access_limit =4 
    def PUT(self):
        """
        Add a request to a chained request from a provided json content
        """
        return dumps({"results" : "Not implemented"})

        return self.add_to_chain(cherrypy.request.body.read().strip())
        
    def add_to_chain(self, data):

        self.logger.log('Adding a new request to chained_request')
        try:
            from json_layer.request import request
        except ImportError as ex:
            self.logger.error('Could not import request object class.', level='critical')
            return dumps({"results":False})
        try:
            req = request(json_input=loads(data))
        except request.IllegalAttributeName as ex:
            return dumps({"results":str(ex)})
            
        if not req.get_attribute("member_of_chain"):
            self.logger.error('Attribute "member_of_chain" attribute was None')
            return dumps({"results":'Error: "member_of_chain" attribute was None.'})
            
        if not req.get_attribute("member_of_campaign"):
            self.logger.error('Attribute "member_of_campaign" attribute was None.')
            return dumps({"results":'Error: "member_of_campaign" attribute was None.'})        
        
        try:
            creq = chained_request(json_input=self.db.get(req.get_attribute('member_of_chain')))
        except chained_request.IllegalAttributeName as ex:
            return dumps({"results":str(ex)})
            
        try:
            new_req = creq.add_request(req.json())
        except chained_request.CampaignAlreadyInChainException as ex:
            return dumps({"results":str(ex)})
            
        if not new_req:
            self.logger.error('Could not save newly created request to database')
            return dumps({"results":False})

        # finalize and make persistent
        self.db.update(creq.json())
        self.rdb.save(new_req)
        return dumps({"results":True})

# REST method that makes the chained request flow to the next
# step of the chain
class FlowToNextStep(RESTResource):
    def __init__(self):
        self.db = database('chained_requests')
        self.access_limit = 3

    def PUT(self):
        """
        Allows to flow a chained request with the dataset and blocks provided in the json 
        """
        return self.flow2(cherrypy.request.body.read().strip())
    
    def GET(self, *args):
        """
        Allow to flow a chained request with internal information
        """
        if not args:
            self.logger.error('No arguments were given.')
            return dumps({"results":'Error: No arguments were given.'})
        return self.multiple_flow(args[0])
        #return self.flow(args[0]) #old flow only for single request

    def multiple_flow(self, rid):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                 res.append(self.flow(r))
            return dumps(res)
        else:
            return dumps(self.flow(rid))
    
    def flow2(self,  data):
        try:
            vdata = loads(data)
        except ValueError as ex:
            self.logger.error('Could not start flowing to next step. Reason: %s' % (ex)) 
            return dumps({"results":str(ex)})
        
        try:
            creq = chained_request(json_input=self.db.get(vdata['prepid']))
        except Exception as ex:
            self.logger.error('Could not initialize chained_request object. Reason: %s' % (ex))
            return dumps({"results":str(ex)})

        self.logger.log('Attempting to flow to next step for chained_request %s' %  (creq.get_attribute('_id')))
    
        # if the chained_request can flow, do it
        inputds = ''
        inblack = []
        inwhite = []
        if 'input_filename' in vdata:
            inputds = vdata['input_filename']
        if 'block_black_list' in vdata:
            inblack = vdata['block_black_list']
        if 'block_white_list' in vdata:
            inwhite = vdata['block_white_list']
            
        return dumps(creq.flow_trial( inputds,  inblack,  inwhite))

    def flow(self,  chainid):
        try:
            creq = chained_request(json_input=self.db.get(chainid))
        except Exception as ex:
            self.logger.error('Could not initialize chained_request object. Reason: %s' % (ex)) 
            return {"results":str(ex)}

        self.logger.log('Attempting to flow to next step for chained_request %s' %  (creq.get_attribute('_id')))
        
        # if the chained_request can flow, do it
        return creq.flow_trial()

class RewindToPreviousStep(RESTResource):
    def __init__(self):
        self.crdb = database('chained_requests')
        self.rdb = database('requests')
        self.access_limit = 3

    def GET(self,  *args):
        """
        Rewind the current chained request of one step.
        """
        if not len(args):
            return dumps({"results":False})
        crid=args[0]
        mcm_cr = chained_request( self.crdb.get( crid) )
        current_step = mcm_cr.get_attribute('step')
        if current_step==0:
            ## or should it be possible to cancel the initial requests of a chained request
            return dumps({"results":False, "message":"already at the root"})

        ## supposedly all the other requests were already reset!
        for next in mcm_cr.get_attribute('chain')[current_step+1:]:
            ## what if that next one is not in the db
            if not self.rdb.document_exists( next):
                self.logger.error('%s is part of %s but does not exist'%( next, crid))
                die=now
                continue
            mcm_r = request(self.rdb.get( next ))
            if mcm_r.get_attribute('status')!='new':
                # this cannot be right!
                self.logger.error('%s is after the current request and is not new: %s' %( next, mcm_r.get_attribute('status')))
                die=now

        ##get the one to be reset
        current_id=mcm_cr.get_attribute('chain')[current_step]
        mcm_r = request( self.rdb.get( current_id ))
        mcm_r.reset()
        saved = self.rdb.update( mcm_r.json() )
        if not saved:
            return dumps({"results":False, "message":"could not save the last request of the chain"})
        mcm_cr.set_attribute('step',current_step -1 )
        # set status, last status
        mcm_cr.set_last_status()
        mcm_cr.set_processing_status()
        
        saved = self.crdb.update( mcm_cr.json())
        if saved:
            return dumps({"results":True})
        else:
            return dumps({"results":False, "message":"could not save chained requests. the DB is going to be inconsistent !"})

class ApproveRequest(RESTResource):
    def __init__(self):
        self.db = database('chained_requests')
        self.acces_limit = 3 

    def GET(self,  *args):
        """
        move the chained request approval to the next step
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
        
    def approve(self,  rid,  val=-1):
        if not self.db.document_exists(rid):
            return {"prepid": rid, "results":'Error: The given chained_request id does not exist.'}
        creq = chained_request(json_input=self.db.get(rid))
        try:
            creq.approve(val)
        except Exception as ex:
            return {"prepid": rid, "results":False, 'message' : str(ex)} 

        saved = self.db.update(creq.json())
        if saved:
            return {"prepid":rid, "results":True}
        else:
            return {"prepid":rid, "results":False , 'message': 'unable to save the updated chained request'}


class InspectChain(RESTResource):
    def __init__(self):
        self.crdb = database('chained_requests')
        self.rdb = database('requests')
        self.acces_limit = 3

    def GET(self, *args):
        """
        Inspect a chained request for next action
        """
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return self.multiple_inspect(args[0])

    def multiple_inspect(self, crid):
        crlist=crid.rsplit(',')
        res = []
        for cr in crlist:
            if self.crdb.document_exists( cr):
                mcm_cr = chained_request( self.crdb.get( cr) )
                res.append( mcm_cr.inspect() )
            else:
                res.append( {"prepid": cr, "results":False, 'message' : '%s does not exist'%(cr)})

        if len(res)>1:
            return dumps(res)
        else:
            return dumps(res[0])
