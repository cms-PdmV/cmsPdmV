from json_base import json_base
import tools.settings as settings

class user(json_base):

    _json_base__schema = {
        '_id': '',
        'username': '',
        'email': '',
        'role': '',
        'pwg': [],
        'fullname': '',
        'history': [],
        'notes': '',
        'seen_notifications': []
    }

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}

        # update self according to json_input
        self.update(json_input)
        self.validate()

    def get_pwgs(self):
        """
        return all accessible PWGs for the user
        """
        all_pwgs = settings.get_value('pwg')
        if self.get_attribute('role') in ['production_manager', 'administrator', 'generator_convener']:

            return all_pwgs
        else:
            return self.get_attribute('pwg')
