from json_layer.json_base import json_base
from couchdb_layer.mcm_database import database as Database


class ChainedCampaign(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'campaigns': [],  # list of lists [[campaign, flow]]
        'check_cmssw_version': True,
        'enabled': True,
        'history': [],
        'notes': '',
        'threshold': 0,
    }

    def generate_request(self, root_request):
        """
        Create a new chained request using this chained campaign and given
        root request
        """
        prepid = self.get_attribute('prepid')
        root_request_id = root_request.get_attribute('prepid')
        self.logger.info('Building a new chained request using %s and %s as root',
                         prepid,
                         root_request_id)

        # Use PWG of root request
        pwg = root_request.get('pwg')
        request_status = root_request.get_attribute('status')
        chained_request_data = {'pwg': pwg,
                                'member_of_campaign': self.get('prepid'),
                                'enabled': True,
                                'dataset_name': root_request.get('dataset_name'),
                                'last_status': request_status}
        from rest_api.ChainedRequestFactory import ChainedRequestFactory
        chained_request = ChainedRequestFactory.make(chained_request_data, root_request)
        chained_request.validate()
        if request_status in {'submitted', 'done'}:
            chained_request.set('status', 'processing')

        chained_request.update_history('created')
        return chained_request

    def __getitem__(self, index):
        """
        Given index, return flow-campaign pair at index in the chain
        """
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]

        if isinstance(index, int):
            return self.get_attribute('campaigns')[index]

        raise TypeError('Expected int or slice, but got %s' % (type(index)))

    def __len__(self):
        """
        Return length of chain
        """
        return len(self.get_attribute('campaigns'))

    def flow(self, index):
        """
        Return flow at given index
        """
        return self[index][1]

    def campaign(self, index):
        """
        Return campaign at given index
        """
        return self[index][0]

    @classmethod
    def get_database(cls):
        """
        Return shared database instance
        """
        if not hasattr(cls, 'database'):
            cls.database = Database('chained_campaigns')

        return cls.database

    def flow(self, index):
        """
        Return flow name at given index
        """
        return self[index][1]

    def campaign(self, index):
        """
        Return campaign name at given index
        """
        return self[index][0]
