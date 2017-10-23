#!/usr/bin/env python

import itertools

from json import dumps, loads
from cherrypy import request

from RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from tools.communicator import communicator
from tools.locator import locator
from json_layer.invalidation import invalidation
from tools.settings import settings
from tools.user_management import access_rights


class SetStatus(RESTResource):

    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Set the status of an invalidation to the next status
        """
        if not len(args):
            return dumps({'results': False, 'message': 'not id has been provided'})

        docid = args[0]
        invalidations = database('invalidations')
        if not invalidations.document_exists(docid):
            return dumps({'results': False, 'message': '%s does not exists' % (docid)})

        invalid = invalidation(invalidations.get(docid))
        invalid.set_status()
        invalidations.update(invalid.json())
        return dumps({'results': True})

class Announcer():

    def __init__(self):
        self.db_name = "invalidations"
        self.com = communicator()
        self.l_type = locator()

    def print_invalidations(self, invalids):
        a_text = ''
        for invalid in invalids:
            a_text += ' %s\n' % (invalid.get_attribute('object'))
        return a_text

    def announce(self, ds_to_be_invalidated, r_to_be_rejected):
        if (len(ds_to_be_invalidated) != 0 or len(r_to_be_rejected) != 0):
            text = 'Dear Data Operation Team,\n\n'
            if len(r_to_be_rejected) != 0:
                text += 'please reject or abort the following requests:\n'
                text += self.print_invalidations(r_to_be_rejected)
            if len(ds_to_be_invalidated) != 0:
                text += '\nPlease invalidate the following datasets:\n'
                text += self.print_invalidations(ds_to_be_invalidated)
            text += '\nas a consequence of requests being reset.\n'

            to_who = [settings().get_value('service_account')]
            if self.l_type.isDev():
                to_who.append( settings().get_value('hypernews_test'))
            else:
                to_who.append( settings().get_value('dataops_announce' ))

            try:
                elem = (r_to_be_rejected + ds_to_be_invalidated)[0]
                sender = elem.current_user_email
            except IndexError:
                sender = None

            self.com.sendMail(to_who,
                    'Request and Datasets to be Invalidated', text, sender)

            for to_announce in itertools.chain(r_to_be_rejected, ds_to_be_invalidated):
                to_announce.set_announced()
                idb = database(self.db_name)
                idb.update(to_announce.json())

class Clearer():
    def __init__(self):
        self.db_name = "invalidations"

    def clear(self, ds_to_be_invalidated, r_to_be_rejected):
        if (len(ds_to_be_invalidated) != 0 or len(r_to_be_rejected) != 0):
            for to_announce in itertools.chain(r_to_be_rejected, ds_to_be_invalidated):
                to_announce.set_announced()
                idb = database(self.db_name)
                idb.update(to_announce.json())

class GetInvalidation(RESTResource):

    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Retrieve the content of a given invalidation object
        """
        if not args:
            self.logger.error('No arguments were given.')
            return dumps({"results": False})
        return dumps(self.get_request(args[0]))

    def get_request(self, object_name):
        db = database('invalidations')
        return {"results": db.get(object_name)}

class DeleteInvalidation(RESTResource):
    def __init__(self):
        self.db_name = 'invalidations'
        self.access_limit = access_rights.administrator

    def DELETE(self, *args):
        """
        Delete selected invalidation from DB.
        """
        if not args:
            self.logger.error('Delete invalidations: no arguments were given')
            return dumps({"results": False})
        db = database("invalidations")
        self.logger.info('Deleting invalidation: %s' % (args[0]))
        return dumps({"results": db.delete(args[0])})

class AnnounceInvalidations(RESTResource):
    def __init__(self):
        self.db_name = 'invalidations'
        self.access_limit = access_rights.production_manager

    def PUT(self):
        """
        Announce selected invalidations to Data OPS
        """
        input_data = loads(request.body.read().strip())
        self.logger.info("invaldations input: %s" % (input_data))
        if len(input_data) > 0:
            return self.announce(input_data)
        else:
            return dumps({"results":False, "message": "No elements selected"})

    def announce(self, data):
        db = database(self.db_name)
        __ds_list = []
        __r_list = []
        for doc_id in data: #for each _id we get object from db
            tmp = db.get(doc_id)
            if tmp["type"] == "dataset" and tmp["status"] == "new":
                __ds_list.append(tmp)
            elif tmp["type"] == "request" and tmp["status"] == "new":
                __r_list.append(tmp)
            else:
                self.logger.info("Tried to ANNOUNCE non new invaldation: %s" % (
                        tmp["object"]))

        announcer = Announcer()
        announcer.announce(map(invalidation, __ds_list), map(invalidation, __r_list))
        return dumps({"results":True, "ds_to_invalidate": __ds_list,
                "requests_to_invalidate": __r_list})

class ClearInvalidations(RESTResource):
    def __init__(self):
        self.db_name = "invalidations"
        self.access_limit = access_rights.production_manager

    def PUT(self):
        """
        Clear selected invalidations without announcing
        """
        input_data = loads(request.body.read().strip())
        if len(input_data) > 0:
            return self.clear(input_data)
        else:
            return dumps({"results":False, "message": "No elements selected"})

    def clear(self, data):
        db = database(self.db_name)
        __ds_list = []
        __r_list = []
        for doc_id in data:
            tmp = db.get(doc_id) #we don't want to set clear announced objects
            if tmp["type"] == "dataset" and tmp["status"] == "new":
                __ds_list.append(tmp)
            elif tmp["type"] == "request" and tmp["status"] == "new":
                __r_list.append(tmp)
            else:
                self.logger.error("Tried to CLEAN non new invaldation: %s" %
                    (tmp["object"]))

        __clearer = Clearer()
        __clearer.clear(map(invalidation, __ds_list), map(invalidation, __r_list))
        return dumps({"results":True, "ds_to_invalidate": __ds_list,
                "requests_to_invalidate": __r_list})

class AcknowledgeInvalidation(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator
        self.access_user = settings().get_value('allowed_to_acknowledge')

    def GET(self, *args):
        """
        Acknowledge the invalidation. By just changeing its status
        """
        idb = database('invalidations')
        if not len(args):
            return dumps({"results": False, "message": 'Error: No arguments were given.'})

        doc = idb.get(args[0])
        if not doc:
            return dumps({"results": False, "message": 'Error: %s is not a doc id' % (
                    args[0])})

        doc["status"] = "acknowledged"
        saved = idb.save(doc)
        if saved:
            return dumps({"results": True, "message": "Invalidation doc %s is acknowledged" % (
                    args[0])})

        else:
            return dumps({"results": False, "message" : "Could not save the change in %s" % (
                    args[0])})

class PutOnHoldInvalidation(RESTResource):
    def __init__(self):
        self.db_name = "invalidations"
        self.access_limit = access_rights.production_manager

    def PUT(self):
        """
        Put single invalidation on hold so DS would not be invalidated
        """
        input_data = loads(request.body.read().strip())
        if not len(input_data):
            return dumps({"results": False, "message": 'Error: No arguments were given.'})
        self.logger.info("Putting invalidation on HOLD. input: %s" % (input_data))
        db = database(self.db_name)
        res = []
        for el in input_data:
            if db.document_exists(el):
                doc = db.get(el)
                __invl = invalidation(doc)
                if __invl.get_attribute("status") == "new":
                    ret = __invl.set_attribute('status', 'hold')
                    out = db.update(ret)
                    res.append({"object": el, "results" : True, "message" : out})
                else:
                    res.append({"object" : el, "results" : False, "message" : "status not new"})
            else:
                __msg = "%s dosn't exists in DB" % (el)
                res.append({"object": el, "results" : False, "message" : __msg})

        return dumps({"results" : res})

class PutHoldtoNewInvalidations(RESTResource):
    def __init__(self):
        self.db_name = "invalidations"
        self.access_limit = access_rights.production_manager

    def PUT(self):
        """
        Move HOLD invalidations back to status new
        """
        input_data = loads(request.body.read().strip())
        if not len(input_data):
            return dumps({"results": False, "message": 'Error: No arguments were given.'})

        self.logger.info("Putting invalidation from HOLD back to new. input: %s" % (input_data))
        db = database(self.db_name)
        res = []
        for el in input_data:
            if db.document_exists(el):
                doc = db.get(el)
                __invl = invalidation(doc)
                if __invl.get_attribute("status") == "hold":
                    ret = __invl.set_attribute("status", "new")
                    out = db.update(ret)
                    res.append(out)
                else:
                    res.append({"object" : el, "results" : False, "message" : "status not HOLD"})
            else:
                __msg = __msg = "%s dosn't exists in DB" % (el)
                res.append({"object" : el, "results" : False, "message" : __msg})
        return dumps({"results" : res})
