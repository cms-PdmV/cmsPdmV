from json_layer.chained_request import chained_request as ChainedRequest
from couchdb_layer.mcm_database import database as Database
from .RestAPIMethod import RESTResourceIndex
from tools.locker import locker


class ChainedRequestPrepId(RESTResourceIndex):

    serial_number_cache = {}

    def next_prepid(self, pwg, campaign_name):
        if not pwg or not campaign_name:
            return None

        chained_request_db = Database('chained_requests')
        prepid_part = '%s-%s' % (pwg, campaign_name)
        with locker.lock('chained-request-prepid-%s' % (pwg)):
            if prepid_part in self.serial_number_cache:
                number = self.serial_number_cache[prepid_part] + 1
            else:
                newest = chained_request_db.raw_query_view('requests',
                                                           'serial_number',
                                                           page=0,
                                                           limit=1,
                                                           options={'group': True,
                                                                    'include_docs': False,
                                                                    'key': [campaign_name, pwg]})
                number = 1
                if newest:
                    self.logger.info('Highest prepid number: %05d', newest[0])
                    number = newest[0] + 1

            # Save last used prepid
            # Make sure to include all deleted ones
            prepid = '%s-%05d' % (prepid_part, number)
            while chained_request_db.document_exists(prepid, include_deleted=True):
                number += 1
                prepid = '%s-%05d' % (prepid_part, number)

            self.serial_number_cache[prepid_part] = number
            chained_request = ChainedRequest({'_id': prepid,
                                              'prepid': prepid,
                                              'pwg': pwg,
                                              'member_of_campaign': campaign_name})
            chained_request.update_history({'action': 'created'})
            chained_request_db.save(chained_request.json())
            self.logger.info('New request created: %s ', prepid)
            return prepid
