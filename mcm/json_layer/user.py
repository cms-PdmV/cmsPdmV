from json_base import json_base

class user(json_base):

    _json_base__schema = {
        '_id': '',
        'username': '',
        'email': '',
        'role': '',
        'pwg': [],
        'fullname': '',
        'history': [],
        'notes': ''
    }

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}

        # update self according to json_input
        self.update(json_input)
        self.validate()

