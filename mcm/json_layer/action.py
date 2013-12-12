#!/usr/bin/env python

from couchdb_layer.mcm_database import database
from json_layer.request import request
from json_layer.json_base import json_base
from json_layer.chained_request import chained_request

class action(json_base):
    class PrepIdNotDefinedException(Exception):
        def __init__(self):
	        action.logger.error('Prepid is not defined.')
        def __str__(self):
            return 'Error: PrepId is not defined.'
            
    class PrepIdDoesNotExistException(Exception):
        def __init__(self,  pid):
            self.pid = pid
            action.logger.error('prepid %s does not exist in the database.' % (self.pid))
        def __str__(self):
            return 'Error: PrepId ' + self.pid + ' does not exist in the database.'
            
    class ChainedCampaignDoesNotExistException(Exception):
        def __init__(self,  cid):
            self.c = cid
            action.logger.error('chained_campaign %s does not exist in the database.' % (self.c))
        def __str__(self):
            return 'Error: Chained Campaign '+ self.c + ' does not exist'
    
    def __init__(self, json_input={}):
        self._json_base__schema = {
            '_id':'',
            'prepid':'',
            'history':[],
            'member_of_campaign':'', 
            'dataset_name':'',
            'analysis_id':[],
            'chains': {},  # a dictionary holding the settings for each chain
            }
        # update self according to json_input
        self.update(json_input)
        self.validate()
	
    def update(self,  json_input):
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
        except database.DatabaseAccessError as ex:
            return False
        
        # validate prepid
        if not reqdb.document_exists(self.get_attribute('prepid')):
            raise self.PrepIdDoesNotExistException(self.get_attribute('prepid'))
        
        # get campaign id
        req = request(json_input=reqdb.get(self.get_attribute('prepid')))
        
        # check if campaign exists
        campid = req.get_attribute('member_of_campaign')
        if not campid:
            self.logger.error('action %s has not a campaign defined' % (self.get_attribute('prepid')))     
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
            cdb = database('campaigns')
        except database.DatabaseAccessError as ex:
            return False
        
        # get all chains
        # '>' & '>=' operators in queries for string keys return the same
        #candidate_chains = chaindb.query('prepid>=chain_'+campid)
        candidate_chains = chaindb.query('prepid>=chain_'+campid+'_',page_num=-1)
        candidate_chains.extend(chaindb.query('prepid==chain_'+campid,page_num=-1))
        
        
        # map only prepids
        ccids = map(lambda x: x['_id'],  candidate_chains)
        chains = self.get_attribute('chains')
        new_chains = {}
        
        # cross examine (avoid deleted, keep new ones)
        for ccid in ccids:
            if ccid in chains:
                new_chains[ccid] = chains[ccid]
            else:
                new_chains[ccid] = {'flag' : False }
        
        # make persistent
        self.set_attribute('chains',  new_chains)
        
        return True

    # select a chain ( set a priority block )
    def select_chain(self,  cid):#,  value=1):
        if cid not in self.get_attribute('chains'):
            raise self.ChainedCampaignDoesNotExistException(cid)
        
        # set
        chains = self.get_attribute('chains')
        chains[cid]['flag'] = True #value
        
        # make persistent
        self.set_attribute('chains',  chains)
    
    # deselect a chain ( turn it to 0 )
    def deselect_chain(self,  cid):
        # retrieve chains attribute
        chains = self.get_attribute('chains')
        
        # check if chained_campaign is in the chain
        if cid not in chains:
            raise self.ChainedCampaignDoesNotExistException(cid)
        
        chains[cid]['flag'] = False # deselect = set 0
        
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
        
    def inspect_priority(self, forChains=None):
        ##JR: until put in the proper place
        chains=self.get_attribute('chains')
        crdb = database('chained_requests')
        okay = True
        for inCC in chains:
            ### this is the old convention
            #if 'flag' in chains[inCC] and chains[inCC]['flag']:
            #    if 'chains' in chains[inCC]:
            #        for acr in chains[inCC]['chains']:
            #            if forChains and not acr in forChains: continue
            #            cr=chained_request(crdb.get(acr))
            #            cc=cr.get_attribute('member_of_campaign')
            #            #if 'block_number' in chains[cc] and chains[cc]['block_number']:
            #            if chains[cc]['block_number']:
            #                cr.set_priority(chains[cc]['block_number'])
            #                self.logger.log('Set priority block %s to %s'%(chains[cc]['block_number'],cr.get_attribute('prepid')))
            #            else:
            #                self.logger.error('Could not set block %s to %s'%(chains[cc]['block_number'],cr.get_attribute('prepid')))
            ## new convention
            if 'chains' in chains[inCC] and type(chains[inCC]['chains'])==dict:
                for acr in chains[inCC]['chains']:
                    if forChains and not acr in forChains: continue
                    bn=chains[inCC]['chains'][acr]['block_number']
                    cr=chained_request(crdb.get(acr))
                    if bn:
                        self.logger.log('Set priority block %s to %s'%( bn , acr))
                        if not cr.set_priority( bn ):
                            okay = False
                    else:
                        self.logger.error('Could not set block %s to %s'%( bn , acr))
                        

        rd = database('requests')
        if rd.document_exists(self.get_attribute('prepid')):
            r= request(rd.get(self.get_attribute('prepid')))
            self.set_attribute('dataset_name',r.get_attribute('dataset_name'))

        return okay

    def get_chains( self, chained_campaigned_id):
        chains = self.get_attribute('chains')[chained_campaigned_id]
        if 'chains' in chains:
            return chains['chains']
        else:
            return {}

    def remove_chain(self, chained_campaigned_id, chained_request_id):
        chains = self.get_attribute('chains')
        chains[chained_campaigned_id]['chains'].pop( chained_request_id)
        self.set_attribute('chains', chains)
        self.update_history({'action':'remove', 'step' : chained_request_id})
