import json
import flask

from rest_api.RestAPIMethod import RESTResource
from tools.settings import Settings
from tools.user_management import access_rights


class GetSetting(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, key):
        """
        Retrieve value and notes of a given setting
        """
        return {'results': Settings.get_setting(key)}


class SetSetting(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Save a new setting
        """
        data = json.loads(flask.request.data)
        results = Settings.set_setting(data['_id'], data['value'], data.get('notes'))
        return {'results': results}
