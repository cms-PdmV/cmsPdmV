from json_layer.chained_request import chained_request as ChainedRequest
from couchdb_layer.mcm_database import database as Database
from RestAPIMethod import RESTResourceIndex
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
                query = chained_request_db.make_query({'prepid': '%s-*' % (prepid_part)})
                newest = chained_request_db.full_text_search('search', query, limit=1, sort_asc=False)
                if newest:
                    self.logger.info('Newest prepid: %s', newest[0]['prepid'])
                    number = int(newest[0]['prepid'].split('-')[-1]) + 1
                else:
                    number = 1

            # Save last used prepid
            self.serial_number_cache[prepid_part] = number
            prepid = '%s-%05d' % (prepid_part, number)
            if chained_request_db.document_exists(prepid):
                self.serial_number_cache.pop(prepid_part, None)
                return {"results": False,
                        "message": "Chained request prepid %s already exists" % (prepid)}

            chained_request = ChainedRequest({'_id': prepid,
                                              'prepid': prepid,
                                              'pwg': pwg,
                                              'member_of_campaign': campaign_name})
            chained_request.update_history({'action': 'created'})
            chained_request_db.save(chained_request.json())
            self.logger.info('New request created: %s ', prepid)
            return prepid
