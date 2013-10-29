from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from json import dumps, loads
import cherrypy

class GetTags(RESTResource):
    def __init__(self):
        self.db = database('searchable')
        self.access_limit = 1

    def GET(self, *args):
        """
        Get all tags.
        """
        return dumps({"results": True, "tags": self.db.get("tags")["list"]})


class AddTag(RESTResource):
    def __init__(self):
        self.db = database('searchable')
        self.access_limit = 1

    def PUT(self, *args):
        """
        Add new tag to the list.
        """
        data = loads(cherrypy.request.body.read().strip())
        tag = data["tag"]
        doc = self.db.get("tags")
        if tag not in doc["list"]:
            doc["list"].append(tag)
        return dumps({"results": self.db.save(doc)})

class RemoveTag(RESTResource):
    def __init__(self):
        self.db = database('searchable')
        self.access_limit = 1

    def PUT(self, *args):
        """
        Remove tag from the list.
        """
        data = loads(cherrypy.request.body.read().strip())
        tag = data["tag"]
        doc = self.db.get("tags")
        if tag in doc["list"]:
            doc["list"].remove(tag)
        return dumps({"results": self.db.save(doc)})