from json_layer.json_base import json_base

class setting(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'value': None,  # so that it can be of any type
        'notes': '',
    }

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}
        # update self according to json_input
        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()

    def get_editable(self):
        editable = {}
        for key in self._json_base__schema:
            editable[key] = True
        return editable
