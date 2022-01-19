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

    def validate(self):
        prepid = self.get('prepid')
        if not self.flow_prepid_regex(prepid):
            raise Exception('Invalid flow prepid')

        # Make allowed campaigns unique
        allowed_campaigns = sorted(list(set(self.get('allowed_campaigns'))))
        self.set('allowed_campaigns', allowed_campaigns)

        request_parameters = self.get('request_parameters')
        allowed_parameters = {'time_event', 'size_event', 'process_string', 'keep_output',
                              'pileup_dataset_name', 'sequences', 'sequences_name'}
        invalid_parameters = set(list(request_parameters.keys())) - allowed_parameters
        if invalid_parameters:
            raise Exception('Not allowed parameters: %s' % (', '.join(list(invalid_parameters))))

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
