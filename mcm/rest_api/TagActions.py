from json import dumps, loads

from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from tools.user_management import access_rights
from flask import request



class GetTags(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.generator_contact
        self.before_request()
        self.count_call()

    def get(self):
        """
        Get all tags.
        """
        db = database('searchable')
        return {"results": True, "tags": db.get("tags")["list"]}


class AddTag(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.generator_contact
        self.before_request()
        self.count_call()

    def put(self):
        """
        Add new tag to the list.
        """
        db = database('searchable')
        data = loads(request.data.strip())
        tag = data["tag"]
        doc = db.get("tags")
        if tag not in doc["list"]:
            doc["list"].append(tag)
        return {"results": db.save(doc)}

class RemoveTag(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.generator_contact
        self.before_request()
        self.count_call()

    def put(self):
        """
        Remove tag from the list.
        """
        db = database('searchable')
        data = loads(request.data.strip())
        tag = data["tag"]
        doc = db.get("tags")
        if tag in doc["list"]:
            doc["list"].remove(tag)
        return {"results": db.save(doc)}