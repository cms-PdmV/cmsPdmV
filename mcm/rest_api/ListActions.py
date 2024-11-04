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
            if '_rev' not in data:
                self.logger.error('Could not locate the CouchDB revision number (_rev) in object: %s' % data)
                return self.output_text(
                    {"results": False, 'message': 'Could not locate revision number (_rev) in the object'},
                    400,
                    {'Content-Type': 'application/json'}
                )
            if '_id' not in data:
                self.logger.error("List '_id' has not been provided")
                return self.output_text(
                    {"results": False, 'message': "List '_id' has not been provided"},
                    400,
                    {'Content-Type': 'application/json'}
                )
            if 'prepid' not in data:
                self.logger.error("List 'prepid' has not been provided")
                return self.output_text(
                    {"results": False, 'message': "List 'prepid' has not been provided"},
                    400,
                    {'Content-Type': 'application/json'}
                )
            if data['_id'] != data['prepid']:
                self.logger.error("List '_id' and 'prepid' do not have the same value")
                return self.output_text(
                    {"results": False, 'message': "List '_id' and 'prepid' do not have the same value"},
                    400,
                    {'Content-Type': 'application/json'}
                )
            if not db.document_exists(data['_id']):
                return self.output_text(
                    {"results": False, 'message': 'List %s does not exist' % (data['_id'])},
                    404,
                    {'Content-Type': 'application/json'}
                )
            else:
                if db.get(data['_id'])['_rev'] != data['_rev']:
                    response_body =  {
                        "results": False,
                        'message': 'Revision clash, retrieve the latest document version, modifiy it and try again'
                    }
                    return self.output_text(response_body, 400, {'Content-Type': 'application/json'})

            self.logger.info('Updating list %s...' % (data.get('prepid')))
            return {'results': db.update(data), 'message': ''}
        except Exception:
            self.logger.error('Failed to update a list from API')
            return {'results': False, 'message': 'Failed to update a list from API'}

