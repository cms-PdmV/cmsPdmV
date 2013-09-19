from rest_api.RestAPIMethod import RESTResource
from json import dumps, loads
from couchdb_layer.prep_database import database
from json_layer.mccm import mccm
import cherrypy

class GetMccm(RESTResource):
    def __init__(self):
        self.db = database('mccms')

    def GET(self, *args):
        """
        Retreive the dictionnary for a given mccm
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": {}})
        return self.get_doc(args[0])

    def get_doc(self, data):
        if not self.db.document_exists(data):
            return dumps({"results": {}})
        mccm_doc = self.db.get(prepid=data)

        return dumps({"results": mccm_doc})

class UpdateMccm(RESTResource):
    def __init__(self):
        self.db = database('mccms')

    def PUT(self):
        """
        Updating an existing mccm with an updated dictionary
        """
        try:
            res = self.update(cherrypy.request.body.read().strip())
            return res
        except:
            self.logger.error('Failed to update an mccm from API')
            return dumps({'results': False, 'message': 'Failed to update an mccm from API'})

    def update(self, body):
        data = loads(body)
        if '_rev' not in data:
            self.logger.error('Could not locate the CouchDB revision number in object: %s' % data)
            return dumps({"results": False, 'message': 'could not locate revision number in the object'})

        if not self.db.document_exists(data['_id']):
            return dumps({"results": False, 'message': 'mccm %s does not exist' % ( data['_id'])})
        else:
            if self.db.get(data['_id'])['_rev'] != data['_rev']:
                return dumps({"results": False, 'message': 'revision clash'})

        new_version = mccm(json_input=data)

        if not new_version.get_attribute('prepid') and not new_version.get_attribute('_id'):
            self.logger.error('Prepid returned was None')
            raise ValueError('Prepid returned was None')

        ## operate a check on whether it can be changed
        previous_version = mccm(self.db.get(new_version.get_attribute('prepid')))
        editable = previous_version.get_editable()
        for (key, right) in editable.items():
            # does not need to inspect the ones that can be edited
            if right: continue
            if previous_version.get_attribute(key) != new_version.get_attribute(key):
                self.logger.error('Illegal change of parameter, %s: %s vs %s : %s' % (
                    key, previous_version.get_attribute(key), new_version.get_attribute(key), right))
                return dumps({"results": False, 'message': 'Illegal change of parameter %s' % key})

        self.logger.log('Updating mccm %s...' % (new_version.get_attribute('prepid')))


        # update history
        new_version.update_history({'action': 'update'})
        return dumps({"results": self.db.update(new_version.json())})
