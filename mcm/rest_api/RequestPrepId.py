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
    
    def next_prepid(self, pwg, campaign):
        if not pwg or not campaign:
            return None
        res = map(lambda doc: int(doc['prepid'].split('-')[-1]), self.db.queries(['pwg==%s'%(pwg),
                                                                                  'member_of_campaign==%s'%(campaign)]))
        lastSN=0
        if len(res)!=0:
            lastSN = max(res)
        if lastSN==0:
            self.logger.log('Beginning new prepid family: %s %s' %( pwg, campaign))
        lastSN+=1        
        pid='%s-%s-%05d'%( pwg, campaign , lastSN)
        self.logger.log('New prepid : %s '%( pid))
        return pid

    def generate_prepid(self, pwg, campaign):
        return dumps({"prepid": self.next_prepid(pwg, campaign)})

