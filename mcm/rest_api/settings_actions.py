import json
import flask
from json_layer.user import Role

from rest_api.api_base import RESTResource
from tools.settings import Settings


class GetSetting(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def get(self, key):
        """
        Retrieve value and notes of a given setting
        """
        return {'results': Settings.get_setting(key)}


class SetSetting(RESTResource):

    @RESTResource.ensure_role(Role.ADMINISTRATOR)
    def put(self):
        """
        Save a new setting
        """
        data = json.loads(flask.request.data)
        results = Settings.set_setting(data['_id'], data['value'], data.get('notes'))
        return {'results': results}
