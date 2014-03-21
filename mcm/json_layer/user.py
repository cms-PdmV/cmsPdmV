import cherrypy
from json_base import json_base


class user(json_base):

    def __init__(self, json_input={}):

        self._json_base__schema = {
            '_id': '',
            'username': '',
            'email': '',
            'role': '',
            'pwg': [],
            'fullname': '',
            'history' :[],
            'notes' :''
        }

        # update self according to json_input
        self.update(json_input)
        self.validate()

