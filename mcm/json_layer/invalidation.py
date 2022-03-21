from json_layer.model_base import ModelBase


class Invalidation(ModelBase):

    _ModelBase__schema = {
        '_id': '',
        'prepid': '',
        'object': '',
        'status': '',
        'type': ''
    }
    dataset_name = 'invalidations'

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
