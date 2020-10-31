from json import loads

from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from json_layer.setting import setting
import tools.settings as settings
from tools.user_management import access_rights
from flask import request


class GetSetting(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, setting_id):
        """
        Retrieve dictionary regarding given setting
        """
        return self.get_setting(setting_id)

    def get_setting(self, data):
        db = database('settings')
        if not db.document_exists(data):
            self.logger.error('Setting for {0} does not exist'.format(data))
            return {"results": {}}

        return {"results": settings.get(data)}


class SaveSetting(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Save a new setting
        """
        try:
            res = self.update(request.data.strip())
            return res
        except Exception as ex:
            self.logger.error('Failed to update a setting from API. Reason: %s' % (str(ex)))
            return {'results': False, 'message': 'Failed to update a setting from API'}

    def update(self, body):
        data = loads(body)
        db = database('settings')
        if '_rev' in data:
            return {"results": False, 'message': 'could save an object with revision'}

        if '_id' in data and db.document_exists(data['_id']):
            return {"results": False, 'message': 'setting %s already exists.' % (data['_id'])}
        if 'prepid' in data and db.document_exists(data['prepid']):
            return {"results": False, 'message': 'setting %s already exists.' % (data['prepid'])}

        if 'prepid' not in data and '_id' not in data:
            return {"results": False, 'message': 'could save an object with no name'}

        new_setting = setting(data)

        return {"results": settings.add(new_setting.get_attribute('prepid'), new_setting.json())}


class UpdateSetting(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Updating an existing setting with an updated dictionary
        """
        try:
            res = self.update(request.data.strip())
            return res
        except Exception:
            self.logger.error('Failed to update a setting from API')
            return {'results': False, 'message': 'Failed to update a setting from API'}

    def update(self, body):
        data = loads(body)
        db = database('settings')
        if '_rev' not in data:
            self.logger.error('Could not locate the CouchDB revision number in object: %s' % data)
            return {"results": False, 'message': 'could not locate revision number in the object'}

        if not db.document_exists(data['_id']):
            return {"results": False, 'message': 'mccm %s does not exist' % (data['_id'])}
        else:
            if db.get(data['_id'])['_rev'] != data['_rev']:
                return {"results": False, 'message': 'revision clash'}

        new_version = setting(json_input=data)

        if not new_version.get_attribute('prepid') and not new_version.get_attribute('_id'):
            self.logger.error('Prepid returned was None')
            raise ValueError('Prepid returned was None')

        # operate a check on whether it can be changed
        previous_version = setting(db.get(new_version.get_attribute('prepid')))
        editable = previous_version.get_editable()
        for (key, right) in editable.items():
            # does not need to inspect the ones that can be edited
            if right:
                continue
            if previous_version.get_attribute(key) != new_version.get_attribute(key):
                self.logger.error('Illegal change of parameter, %s: %s vs %s : %s' % (
                    key, previous_version.get_attribute(key), new_version.get_attribute(key), right))
                return {"results": False, 'message': 'Illegal change of parameter %s' % key}

        self.logger.info('Updating setting %s...' % (new_version.get_attribute('prepid')))
        return {"results": settings.set(new_version.get_attribute('prepid'), new_version.json())}
