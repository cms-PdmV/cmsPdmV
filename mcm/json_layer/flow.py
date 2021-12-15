from couchdb_layer.mcm_database import database as Database
from json_layer.json_base import json_base


class Flow(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'next_campaign': '',
        'allowed_campaigns': [],
        'request_parameters': {},
        'notes': '',
        'history': [],
        'approval': 'none'
    }

    _prepid_pattern = 'flow[a-zA-Z0-9]{2,60}'

    def validate(self):
        prepid = self.get_attribute('prepid')
        if not self.fullmatch(self._prepid_pattern, prepid):
            raise Exception('Invalid prepid, allowed pattern: %s' % (self._prepid_pattern))

        return super().validate()

    def toggle_approval(self):
        approval_steps = ('none', 'flow', 'submit', 'tasksubmit')
        approval = self.get_attribute('approval')
        index = approval_steps.index(approval)
        new_approval = approval_steps[(index + 1) % (len(approval_steps))]
        self.set_attribute('approval', new_approval)
        self.update_history('approve', new_approval)

    @classmethod
    def get_database(cls):
        """
        Return shared database instance
        """
        if not hasattr(cls, 'database'):
            cls.database = Database('flows')

        return cls.database
