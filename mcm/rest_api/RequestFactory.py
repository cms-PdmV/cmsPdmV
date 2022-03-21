import logging
from json_layer.request import Request
from couchdb_layer.mcm_database import Database
from tools.locker import locker


class RequestFactory():

    logger = logging.getLogger('mcm_error')

    @classmethod
    def make(cls, data):
        """
        Create a new request with a unique prepid and return it
        """
        pwg = data['pwg']
        campaign_name = data['member_of_campaign']
        if not pwg or not campaign_name:
            return None

        request_db = Database('requests')
        prepid_part = '%s-%s' % (pwg, campaign_name)
        with Locker.get_lock('request-prepid-%s' % (pwg)):
            prepid = request_db.get_next_prepid(prepid_part, [campaign_name, pwg])
            data['_id'] = prepid
            data['prepid'] = prepid
            request = Request(data)
            request.save()
            cls.logger.info('New request created: %s ', prepid)

        return request
