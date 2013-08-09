#!/usr/bin/env python
import cherrypy
from json_base import json_base


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
        self.current_user_email = cherrypy.request.headers['ADFS-EMAIL'] if 'ADFS-EMAIL' in cherrypy.request.headers \
            else None

    def set_announced(self):
        self.set_attribute('status', 'announced')

    def set_next_status(self):
        current_status_id = self._json_base__status.index(self.get_attribute('status'))
        if current_status_id + 1 != len(self._json_base__status):
            self.set_attribute('status', self._json_base__status[current_status_id + 1])