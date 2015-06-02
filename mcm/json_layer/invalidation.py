#!/usr/bin/env python
from json_base import json_base
from tools.user_management import user_pack


class invalidation(json_base):

    _json_base__status = ['new', 'announced', 'acknowledged']

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'object': '',
        'status': '',
        'type': ''
    }

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}
        # set invalidation status
        self._json_base__schema['status'] = self._json_base__status[0]

        # update self according to json_input
        self.update(json_input)
        self.validate()
        user_p = user_pack()
        self.current_user_email = user_p.get_email()

    def set_announced(self):
        self.set_attribute('status', 'announced')
