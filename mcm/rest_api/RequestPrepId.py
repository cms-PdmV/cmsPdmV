#!/usr/bin/env python

from json import dumps

from couchdb_layer.prep_database import database 
from RestAPIMethod import RESTResourceIndex

# generates the next valid prepid 
class RequestPrepId(RESTResourceIndex):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)

    #def GET(self, *args):
    #    if len(args) < 2:
    #        self.logger.error('No arguments were given.')
    #        return dumps({"prepid":""})
    #    return self.generate_prepid(args[0], args[1])
    
    def generate_prepid(self, pwg, campaign):
        if not pwg:
            self.logger.error('Physics working group provided is None.')
            return dumps({"prepid":""})
        if not campaign:
            self.logger.error('Campaign prepid provided is None.') 
            return dumps({"prepid":""})

        # get the list of the prepids with the same pwg and campaign name 
        res = map(lambda x: x['value'], self.db.query('prepid ~= '+pwg+'-'+campaign+'-*', page_num=-1))
        #res = map(lambda x: x['value'], self.db.query('prepid ~= '+pwg+'-'+campaign+'-*', page_num=-1)) ##JR what is that ~=
        res = map(lambda x: x['prepid'], res)
        if not res:
            self.logger.log('Beginning new prepid family: %s' % (pwg+"-"+campaign+"-00001"), level='warning')
            return dumps({"prepid":pwg+"-"+campaign+"-00001"})
        
        sn = -1
        for pid in res:
            thisSN = int(pid.rsplit('-')[2])
            if  thisSN >= sn:
                sn = thisSN+1
        
        if sn < 0:
            # increase the serial number of the last request by one
            sn = int(res[-1].rsplit('-')[2])+1
            
        new_prepid = pwg + '-' + campaign + '-' + str(sn).zfill(5)
        self.logger.log('New prepid: %s' % (new_prepid), level='debug') 
        
        # return a json like: {'prepid': new_prepid}
        return dumps({"prepid":new_prepid})
        
