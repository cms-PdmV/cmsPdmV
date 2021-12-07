from json_layer.request import request as Request
from json_layer.campaign import campaign as Campaign
from couchdb_layer.mcm_database import database as Database
from RestAPIMethod import RESTResourceIndex
from tools.locker import locker


class RequestPrepId(RESTResourceIndex):

    serial_number_cache = {}

    def next_prepid(self, pwg, campaign_name):
        if not pwg or not campaign_name:
            return None

        request_db = Database('requests')
        campaign_db = Database('campaigns')
        prepid_part = '%s-%s' % (pwg, campaign_name)
        with locker.lock('request-prepid-%s' % (pwg)):
            if prepid_part in self.serial_number_cache:
                number = self.serial_number_cache[prepid_part] + 1
            else:
                newest = request_db.raw_query_view('requests',
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
            while request_db.document_exists(prepid, include_deleted=True):
                number += 1
                prepid = '%s-%05d' % (prepid_part, number)

            self.serial_number_cache[prepid_part] = number
            campaign = Campaign(campaign_db.get(campaign_name))
            request = Request(campaign.add_request({'_id': prepid,
                                                    'prepid': prepid,
                                                    'pwg': pwg,
                                                    'member_of_campaign': campaign_name}))
            request.update_history({'action': 'created'})
            request_db.save(request.json())
            self.logger.info('New request created: %s ', prepid)
            return prepid
