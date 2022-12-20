#!/usr/bin/env python

import itertools
import tools.settings as settings
from json import loads
from flask import request
from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from tools.communicator import communicator
from tools.locator import locator
from json_layer.invalidation import invalidation
from tools.user_management import access_rights


class Announcer:

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

            to_who = [settings.get_value('service_account')]

            try:
                elem = (r_to_be_rejected + ds_to_be_invalidated)[0]
                sender = elem.current_user_email
            except IndexError:
                sender = None

            self.com.sendMail(to_who, 'Request and Datasets to be Invalidated', text, sender)

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

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, invalidation_id):
        """
        Retrieve the content of a given invalidation object
        """
        return self.get_request(invalidation_id)

    def get_request(self, object_name):
        db = database('invalidations')
        return {"results": db.get(object_name)}


class DeleteInvalidation(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def delete(self, invalidation_id):
        """
        Delete selected invalidation from DB.
        """
        db = database("invalidations")
        self.logger.info('Deleting invalidation: %s' % (invalidation_id))
        return {"results": db.delete(invalidation_id)}


class AnnounceInvalidations(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.db_name = 'invalidations'
        self.before_request()
        self.count_call()

    def put(self):
        """
        Announce selected invalidations to Data OPS
        """
        input_data = loads(request.data)
        self.logger.info("invaldations input: %s" % (input_data))
        if len(input_data) > 0:
            return self.announce(input_data)
        else:
            return {"results": False, "message": "No elements selected"}

    def announce(self, data):
        db = database(self.db_name)
        __ds_list = []
        __r_list = []
        for doc_id in data:  # for each _id we get object from db
            tmp = db.get(doc_id)
            if tmp["type"] == "dataset" and tmp["status"] == "new":
                __ds_list.append(tmp)
            elif tmp["type"] == "request" and tmp["status"] == "new":
                __r_list.append(tmp)
            else:
                self.logger.info("Tried to ANNOUNCE non new invaldation: %s" % (tmp["object"]))

        announcer = Announcer()
        announcer.announce(map(invalidation, __ds_list), map(invalidation, __r_list))
        return {"results": True, "ds_to_invalidate": __ds_list, "requests_to_invalidate": __r_list}


class ClearInvalidations(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.db_name = "invalidations"
        self.before_request()
        self.count_call()

    def put(self):
        """
        Clear selected invalidations without announcing
        """
        input_data = loads(request.data)
        if len(input_data) > 0:
            return self.clear(input_data)
        else:
            return {"results": False, "message": "No elements selected"}

    def clear(self, data):
        db = database(self.db_name)
        __ds_list = []
        __r_list = []
        for doc_id in data:
            tmp = db.get(doc_id)  # we don't want to set clear announced objects
            if tmp["type"] == "dataset" and tmp["status"] == "new":
                __ds_list.append(tmp)
            elif tmp["type"] == "request" and tmp["status"] == "new":
                __r_list.append(tmp)
            else:
                self.logger.error("Tried to CLEAN non new invaldation: %s" % (tmp["object"]))

        __clearer = Clearer()
        __clearer.clear(map(invalidation, __ds_list), map(invalidation, __r_list))
        return {"results": True, "ds_to_invalidate": __ds_list,
                "requests_to_invalidate": __r_list}


class AcknowledgeInvalidation(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.access_user = settings.get_value('allowed_to_acknowledge')
        self.before_request()
        self.count_call()

    def get(self, invalidation_id):
        """
        Acknowledge the invalidation. By just changeing its status
        """
        idb = database('invalidations')
        doc = idb.get(invalidation_id)
        if not doc:
            return {"results": False, "message": 'Error: %s is not a doc id' % (invalidation_id)}

        doc["status"] = "acknowledged"
        saved = idb.save(doc)
        if saved:
            return {"results": True, "message": "Invalidation doc %s is acknowledged" % (invalidation_id)}

        else:
            return {"results": False, "message" : "Could not save the change in %s" % (invalidation_id)}


class PutOnHoldInvalidation(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.db_name = "invalidations"
        self.before_request()
        self.count_call()

    def put(self):
        """
        Put single invalidation on hold so DS would not be invalidated
        """
        input_data = loads(request.data)
        if not len(input_data):
            return {"results": False, "message": 'Error: No arguments were given.'}
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
                    res.append({"object": el, "results": True, "message": out})
                else:
                    res.append({"object": el, "results": False, "message": "status not new"})
            else:
                __msg = "%s dosn't exists in DB" % (el)
                res.append({"object": el, "results": False, "message": __msg})

        return {"results": res}


class PutHoldtoNewInvalidations(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.db_name = "invalidations"
        self.before_request()
        self.count_call()

    def put(self):
        """
        Move HOLD invalidations back to status new
        """
        input_data = loads(request.data)
        if not len(input_data):
            return {"results": False, "message": 'Error: No arguments were given.'}

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
                    res.append({"object": el, "results": False, "message": "status not HOLD"})
            else:
                __msg = __msg = "%s dosn't exists in DB" % (el)
                res.append({"object": el, "results": False, "message": __msg})
        return {"results": res}
