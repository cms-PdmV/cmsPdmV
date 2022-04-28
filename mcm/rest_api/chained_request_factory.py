import logging
from model.chained_request import ChainedRequest
from tools.locker import Locker


class ChainedRequestFactory():

    logger = logging.getLogger()

    @classmethod
    def make(cls, data, root_request):
        """
        Create a new chained request with a unique prepid and return it
        """
        pwg = data['pwg']
        campaign_name = data['member_of_campaign']
        if not pwg or not campaign_name:
            return None

        chained_request_db = ChainedRequest.get_database()
        prepid_part = f'{pwg}-{campaign_name}'
        with Locker.get_lock(f'chained-request-prepid-{prepid_part}'):
            prepid = chained_request_db.get_next_prepid(prepid_part, [campaign_name, pwg])
            data['_id'] = prepid
            data['prepid'] = prepid
            chained_request = ChainedRequest(data)
            chained_request.request_join(root_request)
            chained_request.save()
            cls.logger.info('New chained request created: %s ', prepid)

        return chained_request
