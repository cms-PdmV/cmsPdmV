#!/usr/bin/env python

from json_base import json_base


class flow(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'next_campaign': '',
        'allowed_campaigns': [],
        'request_parameters': {},
        #'description': '',
        'notes': '',
        'history': [],
        #'label': '', ## something that one needs to add in the processing string ?
        'approval': ''
    }

    _json_base__approvalsteps = ['none', 'flow', 'submit']

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}

        self._json_base__schema['approval'] = self.get_approval_steps()[0]

        ##JR. would that function ? self.__approvalsteps = [ 'flow' , 'inject' ]
        # update self according to json_input
        self.update(json_input)
        self.validate()

    def add_allowed_campaign(self,  cid):
        self.logger.log('Adding new allowed campaign to flow %s' % (self.get_attribute('_id')))
        
        # import database connector
        try:
            from couchdb_layer.mcm_database import database
        except ImportError as ex:
            self.logger.error('Could not import database connector class. Reason: %s' % (ex), level='critical')
            return False
        
        # initialize database connector
        try:
            cdb = database('campaigns')
        except database.DatabaseAccessError as ex:
            return False
            
        # check campaign exists
        if not cdb.document_exists(cid):
            raise self.CampaignDoesNotExistException(cid)
        
        # check for duplicate
        allowed = self.get_attribute('allowed_campaigns')
        if cid in allowed:
            raise self.DuplicateCampaignEntry(cid)
        
        # append and make persistent
        allowed.append(cid)
        self.set_attribute('allowed_campaigns',  allowed)

        # update history
        self.update_history({'action':'add allowed campaign', 'step':cid})
        
        return True
        
    def remove_allowed_campaign(self,  cid):
        allowed = self.get_attribute('allowed_campaigns')
        if cid not in allowed:
            raise self.CampaignDoesNotExistException(cid)
        
        # remove it and make persistent
        allowed.remove(cid)
        self.set_attribute('allowed_campaigns',  allowed)

        # update history
        self.update_history({'action':'remove allowed campaign', 'step':cid})
