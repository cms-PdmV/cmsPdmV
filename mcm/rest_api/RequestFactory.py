import logging
from json_layer.request import Request
from json_layer.campaign import Campaign
from couchdb_layer.mcm_database import database as Database
from tools.locker import locker


class RequestFactory():

    logger = logging.getLogger('mcm_error')

    @classmethod
    def make(cls, data, pwg, campaign_name):
        """
        Create a new request with a unique prepid and return it
        """
        pwg = data.get('pwg')
        campaign_name = data.get('member_of_campaign')
        if not pwg or not campaign_name:
            return None

        request_db = Database('requests')
        campaign_db = Database('campaigns')
        prepid_part = '%s-%s' % (pwg, campaign_name)
        with locker.lock('request-prepid-%s' % (pwg)):
            prepid = request_db.get_next_prepid(prepid_part, [campaign_name, pwg])
            campaign = Campaign(campaign_db.get(campaign_name))
            data['_id'] = prepid
            data['prepid'] = prepid
            request = Request(campaign.add_request(data))
            request_db.save(request.json())
            cls.logger.info('New request created: %s ', prepid)
            return prepid
