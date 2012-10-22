#!/usr/bin/env python

from couchdb_layer.prep_database import database
from json_layer.request import request
from json_layer.json_base import json_base
from json_layer.submission_details import submission_details

class action(json_base):
    class PrepIdNotDefinedException(Exception):
        def __str__(self):
            return 'Error: PrepId is not defined.'
            
    class PrepIdDoesNotExistException(Exception):
        def __init__(self,  pid):
            self.pid = pid
        def __str__(self):
            return 'Error: PrepId ' + self.pid + ' does not exist in the database.'
            
    class ChainedCampaignDoesNotExistException(Exception):
        def __init__(self,  cid):
            self.c = cid
        def __str__(self):
            return 'Error: Chained Campaign '+ self.c + ' does not exist'
    
    def __init__(self, author_name, author_cmsid=-1, author_inst_code='', author_project='', json_input={}):
        self._json_base__schema = {
            '_id':'',
            'prepid':'', 
            'member_of_campaign':'', 
            'chains': {},  # a dictionary holding the settings for each chain
            'submission_details':submission_details().build(author_name,  author_cmsid,  author_inst_code,  author_project    ),
            }
        # update self according to json_input
        self.__update(json_input)
        self.__validate()

    def __validate(self):
        if not self._json_base__json:
            return 
        for key in self._json_base__schema:
            if key not in self._json_base__json:
                raise self.IllegalAttributeName(key)
    
    # for all parameters in json_input store their values 
    # in self._json_base__json
    def __update(self,  json_input):
        self._json_base__json = {}
        if not json_input:
            self._json_base__json = self._json_base__schema
        else:
            for key in self._json_base__schema:
                if key in json_input:
                    self._json_base__json[key] = json_input[key]
                else:
                    self._json_base__json[key] = self._json_base__schema[key]
            if '_rev' in json_input:
                self._json_base__json['_rev'] = json_input['_rev']
            
            # fix the member_of_campaign parameter
            if not self._json_base__json['member_of_campaign']:
                if self._json_base__json['prepid']:
                    self._json_base__json['member_of_campaign'] = self._json_base__json['prepid'].rsplit('-')[1]
    
    def find_chains(self):
        # validate request
        if not self.get_attribute('prepid'):
            raise self.PrepIdNotDefinedException()
        
        # initialize db connections
        try:
            reqdb = database('requests')
            campaigndb = database('campaigns')
        except datase.DatabaseAccessError as ex:
            print str(ex)
            return False
        
        # validate prepid
        if not reqdb.document_exists(self.get_attribute('prepid')):
            raise self.PrepIdDoesNotExistException(self.get_attribute('prepid'))
        
        # get campaign id
        req = request('test',  json_input=reqdb.get(self.get_attribute('prepid')))
        
        # check if campaign exists
        campid = req.get_attribute('member_of_campaign')
        if not campid:
            raise ValueError('Error: Campaign was not set for',  self.get_attribute('prepid'))
        if not campaigndb.document_exists(campid):
            raise self.PrepIdDoesNotExistException(campid)
        
        # get all chains
        return self.__retrieve_chains(self.get_attribute('prepid'),  campid)
    
    # Returns true if it calculated the correct chains, False otherwise
    def __retrieve_chains(self,  prepid,  campid):
        # initialize db connections
        try:
            chaindb = database('chained_campaigns')
        except datase.DatabaseAccessError as ex:
            print str(ex)
            return False
        
        # get all chains
        # '>' & '>=' operators in queries for string keys return the same
        candidate_chains = chaindb.query('prepid>=chain_'+campid)
        
        # map only prepids
        ccids = map(lambda x: x['value']['_id'],  candidate_chains)
        chains = self.get_attribute('chains')
        new_chains = {}
        
        # cross examine (avoid deleted, keep new ones)
        for id in ccids:
            if id in chains:
                new_chains[id] = chains[id]
            else:
                new_chains[id] = 0
        
        # make persistent
        self.set_attribute('chains',  new_chains)
        
        return True

    # select a chain ( set a priority block )
    def select_chain(self,  cid,  value=1):
        if cid not in self.get_attribute('chains'):
            raise self.ChainedCampaignDoesNotExistException(cid)
        
        # set
        chains = self.get_attribute('chains')
        chains[cid] = value
        
        # make persistent
        self.set_attribute('chains',  chains)
    
    # deselect a chain ( turn it to 0 )
    def deselect_chain(self,  cid):
        # retrieve chains attribute
        chains = self.get_attribute('chains')
        
        # check if chained_campaign is in the chain
        if cid not in chains:
            raise self.ChainedCampaignDoesNotExistException(cid)
        
        chains[cid] = 0 # deselect = set 0
        
        # make persistent
        self.set_attribute('chains',  chains)
    
    # remove a chain from the dictionary ( shows N/A)
    def remove_chain(self,  cid):
        if cid not in self.get_attribute('chains'):
            raise self.ChainedCampaignDoesNotExistException(cid)
            
        chains = self.get_attribute('chains')
        new_chains = {}
        
        # clear
        for c in chains:
            if c == cid:
                continue
            new_chains[c] = chains[c]
        
        # persistent
        self.set_attribute('chains',  new_chains)
