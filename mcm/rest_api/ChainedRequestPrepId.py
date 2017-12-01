#!/usr/bin/env python

from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResourceIndex
from tools.locker import locker
from json_layer.chained_request import chained_request


# generates the next valid prepid
class ChainedRequestPrepId(RESTResourceIndex):
    def __init__(self):
        self.ccamp_db_name = 'chained_campaigns'
        self.creq_db_name = 'chained_requests'

    serial_number_cache = {}

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
            if (campaign, pwg) in self.serial_number_cache:
                sn = self.serial_number_cache[(campaign, pwg)] + 1
            else:
                sn = 1
                serial_number_lookup = creq_db.raw_query('serial_number', {'group': True, 'key': [campaign, pwg]})
                if serial_number_lookup:
                    sn = serial_number_lookup[0]['value'] + 1

            # construct the new id
            new_prepid = pwg + '-' + campaign + '-' + str(sn).zfill(5)
            if sn == 1:
                self.logger.info('Beginning new prepid family: %s' % (new_prepid))

            new_request = chained_request({'_id': new_prepid, 'prepid': new_prepid, 'pwg': pwg, 'member_of_campaign': campaign})
            new_request.update_history({'action': 'created'})
            creq_db.save(new_request.json())
            self.serial_number_cache[(campaign, pwg)] = sn
            self.logger.info('New chain id: %s' % new_prepid)

            return new_prepid

