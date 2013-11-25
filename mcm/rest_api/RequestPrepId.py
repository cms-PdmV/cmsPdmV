#!/usr/bin/env python

from json import dumps

from json_layer.request import request
from json_layer.campaign import campaign
from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResourceIndex
from tools.locker import locker

# generates the next valid prepid 
class RequestPrepId(RESTResourceIndex):
    def __init__(self):
        self.db_name = 'requests'

    #def GET(self, *args):
    #    if len(args) < 2:
    #        self.logger.error('No arguments were given.')
    #        return dumps({"prepid":""})
    #    return self.generate_prepid(args[0], args[1])
    
    def next_prepid(self, pwg, camp):
        if not pwg or not camp:
            return None
        with locker.lock("{0}-{1}".format(pwg, camp)):
            db = database(self.db_name)
            res = map(lambda doc: int(doc['prepid'].split('-')[-1]), db.queries(['pwg==%s'%(pwg),
                                                                                      'member_of_campaign==%s'%(camp)]))
            lastSN=0
            if len(res)!=0:
                lastSN = max(res)
            if lastSN==0:
                self.logger.log('Beginning new prepid family: %s %s' %( pwg, camp))
            lastSN+=1
            pid='%s-%s-%05d'%( pwg, camp , lastSN)
            db_camp = database('campaigns')
            req_camp = campaign(db_camp.get(camp))
            new_request = request(req_camp.add_request({'_id':pid, 'prepid':pid}))
            new_request.update_history({'action':'created'})
            db.save(new_request.json())
            self.logger.log('New prepid : %s '%( pid))
            return pid

    def generate_prepid(self, pwg, campaign):
        return dumps({"prepid": self.next_prepid(pwg, campaign)})

