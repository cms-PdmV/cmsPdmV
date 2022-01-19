from couchdb_layer.mcm_database import database as Database
from json_layer.json_base import json_base


class Invalidation(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'object': '',
        'status': '',
        'type': ''
    }

    # Status: 'new', "hold", 'announced', 'acknowledged'

    def set_new(self):
        self.set_attribute('status', 'new')
        self.update_history('status', self.get('status'))

    def set_hold(self):
        self.set_attribute('status', 'hold')
        self.update_history('status', self.get('status'))

    def set_announced(self):
        self.set_attribute('status', 'announced')
        self.update_history('status', self.get('status'))

    def set_acknowledged(self):
        self.set_attribute('status', 'acknowledged')
        self.update_history('status', self.get('status'))

    @classmethod
    def get_database(cls):
        """
        Return shared database instance
        """
        if not hasattr(cls, 'database'):
            cls.database = Database('invalidations')

        return cls.database
