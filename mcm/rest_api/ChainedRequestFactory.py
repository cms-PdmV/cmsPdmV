import logging
from json_layer.chained_request import ChainedRequest
from couchdb_layer.mcm_database import Database
from tools.locker import locker


class ChainedRequestFactory():

    logger = logging.getLogger('mcm_error')

    @classmethod
    def make(cls, data, root_request):
        """
        Create a new chained request with a unique prepid and return it
        """
        pwg = data['pwg']
        campaign_name = data['member_of_campaign']
        if not pwg or not campaign_name:
            return None

        chained_request_db = Database('chained_requests')
        prepid_part = '%s-%s' % (pwg, campaign_name)
        with Locker.get_lock('chained-request-prepid-%s' % (pwg)):
            prepid = chained_request_db.get_next_prepid(prepid_part, [campaign_name, pwg])
            data['_id'] = prepid
            data['prepid'] = prepid
            chained_request = ChainedRequest(data)
            chained_request.request_join(root_request)
            chained_request.save()
            cls.logger.info('New chained request created: %s ', prepid)

        return chained_request
