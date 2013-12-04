#!/usr/bin/env python

from json import dumps

from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResourceIndex
from tools.locker import locker
from json_layer.chained_request import chained_request

# generates the next valid prepid 
class ChainedRequestPrepId(RESTResourceIndex):
    serial_number_cache = {}
    def __init__(self):
        self.ccamp_db_name = 'chained_campaigns'
        self.creq_db_name = 'chained_requests'

        
    def next_id(self, pwg, campaign):
        ccamp_db = database(self.ccamp_db_name)
        creq_db = database(self.creq_db_name)
        if not pwg:
            self.logger.error('Physics working group provided is None.')
            return None
        if not campaign:
            self.logger.error('Campaign id provided is None.')
            return None
        with locker.lock("{0}-{1}".format(pwg, campaign)):
            if not ccamp_db.document_exists(campaign):
                self.logger.error('Campaign id {0} does not exist.'.format(campaign))
                return None

            sn=1
            k = '%s_%s' %( pwg, campaign)
            if k in self.serial_number_cache:
                sn = self.serial_number_cache[k]
            else:
                # get the list of the prepids with the same pwg and campaign name
                results = creq_db.queries(['member_of_campaign==%s'%(campaign),
                                           'pwg==%s'%(pwg)])
                results = map(lambda cr : int(cr['prepid'].split('-')[-1]), results)
                if len(results):
                    # increase the biggest serial number by one
                    sn = max(results) + 1

            ## construct the new id
            new_prepid = pwg + '-' + campaign + '-' + str(sn).zfill(5)
            self.serial_number_cache[k]=(sn+1)
            if sn==1:
                self.logger.log('Beginning new prepid family: %s' % (new_prepid))

            new_request = chained_request({'_id':new_prepid, 'prepid':new_prepid})
            new_request.update_history({'action':'created'})
            creq_db.save(new_request.json())
            self.logger.log('New chain id: %s' % new_prepid, level='debug')

            return new_prepid

