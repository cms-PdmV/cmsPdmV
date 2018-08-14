from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database


class GetList(RESTResource):

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
