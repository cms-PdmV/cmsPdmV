#!/usr/bin/env python

from json import dumps

from couchdb_layer.prep_database import database 
from RestAPIMethod import RESTResourceIndex

# generates the next valid prepid 
class RequestChainId(RESTResourceIndex):
    def __init__(self):
        self.ccamp_db_name = 'chained_campaigns'
        self.ccamp_db = database(self.ccamp_db_name)
        self.creq_db_name = 'chained_requests'
        self.creq_db = database(self.creq_db_name)
    
    def generate_id(self, pwg, campaign):
        if not pwg:
            self.logger.error('Physics working group provided is None.')
            return dumps({"results":""})
        if not campaign:
            self.logger.error('Campaign id provided is None.')
            return dumps({"results":""})
        
        if not self.ccamp_db.document_exists(campaign):
            return dumps({"results":""})
 
        # get the list of the prepids with the same pwg and campaign name 
        results = self.creq_db.get_all()
        results = filter(lambda x: pwg+'-'+campaign+'-' in x,map(lambda x: x['_id'], results))
        if not results:
            self.logger.log('Beginning new prepid family: %s' % (pwg+"-"+campaign+"-00001"))
            return dumps({"results":pwg+"-"+campaign+"-00001"})

        # increase the serial number of the request by one
        sn = int(results[-1].rsplit('-')[2])+1
        new_prepid = pwg + '-' + campaign + '-' + str(sn).zfill(5)

        self.logger.log('New chain id: %s' % (new_prepid), level='debug')

        return dumps({"results":new_prepid})
