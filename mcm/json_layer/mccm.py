#!/usr/bin/env python

from json_base import json_base

class mccm(json_base):

    def __init__(self, json_input={}):
        self._json_base__approvalsteps = ['none','approved']
        self._json_base__status = ['new', 'done']
        self._json_base__schema = {
            '_id':'',
            'prepid': '',
            'approval': '',
            'block': 0,
            'deadline': '',
            'history': [],
            'message_id': '',
            'notes': '',
            'pwg': '',
            'requests': [],
            'size': 0,
            'status': ''
            }
        # update self according to json_input
        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()

    def get_editable(self):
        editable= {}
        for key in self._json_base__schema:
            editable[key] = True
        return editable