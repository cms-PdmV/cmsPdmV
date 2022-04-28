import logging
from model.request import Request
from tools.locker import Locker


class RequestFactory():

    logger = logging.getLogger()

    @classmethod
    def make(cls, data):
        """
        Create a new request with a unique prepid and return it
        """
        pwg = data['pwg']
        campaign_name = data['member_of_campaign']
        if not pwg or not campaign_name:
            return None

        request_db = Request.get_database()
        prepid_part = f'{pwg}-{campaign_name}'
        with Locker.get_lock(f'request-prepid-{prepid_part}'):
            prepid = request_db.get_next_prepid(prepid_part, [campaign_name, pwg])
            data['_id'] = prepid
            data['prepid'] = prepid
            request = Request(data)
            request.save()
            cls.logger.info('New request created: %s ', prepid)

        return request
