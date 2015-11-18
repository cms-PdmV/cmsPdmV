#!/usr/bin/env python

from json_layer.request import request
from json_layer.campaign import campaign
from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResourceIndex
from tools.locker import locker

# generates the next valid prepid
class RequestPrepId(RESTResourceIndex):
    def __init__(self):
        self.db_name = 'requests'

    def next_prepid(self, pwg, camp):
        if not pwg or not camp:
            return None
        with locker.lock("{0}-{1}".format(pwg, camp)):
            db = database(self.db_name)
            query_results = db.raw_query('serial_number', {'group': True, 'key': [camp, pwg]})
            sn = 1
            if query_results:
                sn = query_results[0]['value'] + 1
            pid = '%s-%s-%05d' % (pwg, camp , sn)
            if sn == 1:
                self.logger.log('Beginning new prepid family: %s-%s' % (pwg, camp))
            db_camp = database('campaigns', cache=True)
            req_camp = campaign(db_camp.get(camp))
            new_request = request(req_camp.add_request({'_id': pid, 'prepid': pid,
                    'pwg': pwg, 'member_of_campaign': camp}))

            new_request.update_history({'action':'created'})
            db.save(new_request.json())
            self.logger.log('New prepid : %s ' % pid)
            return pid

    def generate_prepid(self, pwg, campaign):
        return {"prepid": self.next_prepid(pwg, campaign)}
