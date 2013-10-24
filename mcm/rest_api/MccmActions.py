from rest_api.RestAPIMethod import RESTResource
from json import dumps, loads
from couchdb_layer.mcm_database import database
from json_layer.mccm import mccm
from tools.locker import locker
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



class CreateMccm(RESTResource):

    def __init__(self):
        self.db = database('mccms')

    def PUT(self):
        """
        Create the mccm with the provided json content
        """
        try:
            mccm_d = mccm(loads(cherrypy.request.body.read().strip()))
        except Exception as e:
            self.logger.error(mccm_d.json())
            self.logger.error("Something went wrong with loading the mccm data:\n {0}".format(e))
            return dumps({"results": False, "message": "Something went wrong with loading the mccm data:\n {0}".format(e)})

        if not mccm_d.get_attribute('prepid'):
            self.logger.error('Non-existent prepid')
            return dumps({"results": False, "message": "The mccm ticket has no id!"})

        if mccm_d.get_attribute('prepid') == mccm_d.get_attribute('pwg'): # need to complete the pwg
            mccm_d.set_attribute('prepid', self.fill_id(mccm_d.get_attribute('pwg')))
        elif self.db.document_exists(mccm_d.get_attribute('prepid')):
            return dumps({"results": False, "message": "Mccm document {0} already exists".format(mccm_d.get_attribute('prepid'))})

        mccm_d.set_attribute('_id', mccm_d.get_attribute('prepid'))
        mccm_d.set_attribute('meeting', mccm.get_meeting_date().strftime("%Y-%m-%d"))
        mccm_d.update_history({'action': 'created'})
        self.logger.log('Saving mccm {0}'.format(mccm_d.get_attribute('prepid')))
        return dumps({"results": self.db.save(mccm_d.json()), "prepid": mccm_d.get_attribute('prepid')})


    def fill_id(self, pwg):
        mccm_id = pwg
        with locker.lock(mccm_id): # get date and number
            t = mccm.get_meeting_date()
            mccm_id += '-' + t.strftime("%Y%b%d") + '-' # date
            final_mccm_id = mccm_id + '00001'
            i = 2
            while self.db.document_exists(final_mccm_id):
                final_mccm_id = mccm_id + str(i).zfill(5)
                i += 1
            return final_mccm_id


class DeleteMccm(RESTResource):

    def __init__(self):
        self.db = database('mccms')

    def DELETE(self, *args):
        if not args:
            return dumps({"results": False, "message": "No id given to delete."})
        return dumps({"results": self.db.delete(args[0])})


class GetEditableMccmFields(RESTResource):

    def __init__(self):
        self.db_name = 'mccms'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
        Retrieve the fields that are currently editable for a given mccm
        """
        if not args:
            self.logger.error('Mccm/GetEditable: No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})
        return self.get_editable(args[0])

    def get_editable(self, prepid):
        mccm_d = mccm(self.db.get(prepid))
        editable = mccm_d.get_editable()
        return dumps({"results": editable})