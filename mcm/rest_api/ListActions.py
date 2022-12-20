from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from tools.user_management import access_rights
from flask import request
from json import loads


class GetList(RESTResource):
    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, list_id):
        """
        Retrieve certain list from McM. Pass _overview as a list id for overview
        and statistics of available lists
        """
        ldb = database('lists')
        if list_id == '_overview':
            results = []
            all_lists = ldb.get_all()
            for single_list in all_lists:
                results.append({'prepid': single_list['prepid'],
                                'notes': single_list.get('notes', ''),
                                'size': len(single_list.get('value', []))})
        else:
            results = ldb.get(list_id)

        return {"results": results, "message": ""}


class UpdateList(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Updating an existing list with an updated dictionary
        """
        try:
            data = loads(request.data.strip())
            db = database('lists')
            self.logger.info('Updating list %s...' % (data.get('prepid')))
            return {'results': db.update(data), 'message': ''}
        except Exception:
            self.logger.error('Failed to update a list from API')
            return {'results': False, 'message': 'Failed to update a list from API'}

