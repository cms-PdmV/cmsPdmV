#!/usr/bin/env python
from json_base import json_base
from tools.user_management import user_pack


class invalidation(json_base):
    def __init__(self, json_input={}):
        # set invalidation status
        self._json_base__status = ['new', 'announced']

        self._json_base__schema = {
            '_id': '',
            'prepid': '',
            'object': '',
            'status': self._json_base__status[0],
            'type': ''
        }

        # update self according to json_input
        self.update(json_input)
        self.validate()
        user_p = user_pack()
        self.current_user_email = user_p.get_email()

    def set_announced(self):
        self.set_attribute('status', 'announced')
