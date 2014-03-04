from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from json import dumps
import cherrypy
from tools.user_management import access_rights
from tools.json import threaded_loads


class GetTags(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.generator_contact

    def GET(self, *args):
        """
        Get all tags.
        """
        db = database('searchable')
        return dumps({"results": True, "tags": db.get("tags")["list"]})


class AddTag(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.generator_contact

    def PUT(self, *args):
        """
        Add new tag to the list.
        """
        db = database('searchable')
        data = threaded_loads(cherrypy.request.body.read().strip())
        tag = data["tag"]
        doc = db.get("tags")
        if tag not in doc["list"]:
            doc["list"].append(tag)
        return dumps({"results": db.save(doc)})

class RemoveTag(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.generator_contact

    def PUT(self, *args):
        """
        Remove tag from the list.
        """
        db = database('searchable')
        data = threaded_loads(cherrypy.request.body.read().strip())
        tag = data["tag"]
        doc = db.get("tags")
        if tag in doc["list"]:
            doc["list"].remove(tag)
        return dumps({"results": db.save(doc)})