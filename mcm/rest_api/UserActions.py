#!/usr/bin/env python

import cherrypy
from json import loads, dumps
from RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from tools.settings import settings
from json_layer.user import user
from tools.user_management import user_pack, roles, access_rights


class GetUserRole(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self):
        """
        Retrieve the role (string) of the current user
        """
        return dumps(self.get_user_role())

    def get_user_role(self):
        user_p = user_pack()
        role_index, role = self.authenticator.get_user_role_index(user_p.get_username(), email=user_p.get_email())
        return {'username': user_p.get_username(), 'role': role, 'role_index': role_index}


class GetAllRoles(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self):
        """
        Retrieve the list of possible roles
        """
        return dumps(self.get_All_roles())

    def get_All_roles(self):
        return roles


class GetUserPWG(RESTResource):
    def __init__(self):
        self.db_name = 'users'

    def GET(self, *args):
        """
        Retrieve the pwg of the provided user
        """
        ## this could be a specific database in couch, to hold the list, with maybe some added information about whatever the group does...

        all_pwgs = settings().get_value('pwg')
        db = database(self.db_name)

        all_pwgs.sort()
        if len(args) == 0:
            return dumps({"results": all_pwgs})
        user_name = args[0]
        if db.document_exists(user_name):
            mcm_user = user(db.get(args[0]))
            if mcm_user.get_attribute('role') in ['production_manager', 'administrator', 'generator_convener']:
                return dumps({"results": all_pwgs})
            else:
                return dumps({"results": mcm_user.get_attribute('pwg')})
        else:
            return dumps({"results": []})


class GetAllUsers(RESTResource):
    def __init__(self):
        self.db_name = 'users'

    def GET(self):
        """
        Retrieve the db content for all users
        """
        return dumps(self.get_Users())

    def get_Users(self):
        db = database(self.db_name)
        return {"results": db.get_all()}


class GetUser(RESTResource):
    def __init__(self):
        self.db_name = 'users'

    def GET(self, *args):
        """
        Retrieve the information about a provided user
        """
        db = database(self.db_name)
        return dumps({"results": db.get(args[0])})


class SaveUser(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.access_limit = access_rights.production_manager

    def PUT(self):
        """
        Save the information about a given user
        """
        db = database(self.db_name)
        return dumps({"results": db.save(loads(cherrypy.request.body.read().strip()))})


class AddRole(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.access_limit = access_rights.user

    def add_user(self):
        db = database(self.db_name)
        user_p = user_pack()
        if db.document_exists(user_p.get_username()):
            return {"results": "User {0} already in database".format(user_p.get_username())}
        mcm_user = user({"_id": user_p.get_username(),
                         "username": user_p.get_username(),
                         "email": user_p.get_email(),
                         "role": roles[access_rights.user],
                         "fullname": user_p.get_fullname()})

        # save to db
        if not db.save(mcm_user.json()):
            self.logger.error('Could not save object to database')
            return {"results": False}
        return {"results": True}

    def GET(self):
        """
        Add the current user to the user database if not already
        """
        return dumps(self.add_user())


class ChangeRole(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.all_roles = roles
        self.access_limit = access_rights.production_manager

    def change_role(self, username, action):
        db = database(self.db_name)
        doc = user(db.get(username))
        user_p = user_pack()
        current_user = user(db.get(user_p.get_username()))
        current_role = doc.get_attribute("role")
        if action == '-1':
            if current_role != 'user': #if not the lowest role -> then him lower himself
                doc.set_attribute("role", self.all_roles[self.all_roles.index(current_role) - 1])
                self.authenticator.set_user_role(username, doc.get_attribute("role"))
                return {"results": db.update(doc.json())}
            return {"results": username + " already is user"} #else return that hes already a user
        if action == '1':
            if current_user.get_attribute("role") != "administrator":
                return {"results": "Only administrators can upgrade roles"}
            if len(self.all_roles) != self.all_roles.index(current_role) + 1: #if current role is not the top one
                doc.set_attribute("role", self.all_roles[self.all_roles.index(current_role) + 1])
                self.authenticator.set_user_role(username, doc.get_attribute("role"))
                return {"results": db.update(doc.json())}
            return {"results": username + " already has top role"}
        return {"results": "Failed to update user: " + username + " role"}

    def GET(self, *args):
        """
        Increase /1 or decrease /-1 the given user role by one unit of role
        """
        if not args:
            self.logger.error("No Arguments were given")
            return dumps({"results": 'Error: No arguments were given'})
        return dumps(self.change_role(args[0], args[1]))


class FillFullNames(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Goes through database and fills full names of all the users, who have not had it filled yet
        """
        db = database('users')
        users = db.get_all()
        results = []
        for u_d in users:
            u = user(u_d)
            if not u.get_attribute('fullname'):
                import subprocess
                import re

                output = subprocess.Popen(
                    ["phonebook", "-t", "firstname", "-t", "surname", "--login", u.get_attribute('username')],
                    stdout=subprocess.PIPE)
                split_out = [x for x in re.split("[^a-zA-Z0-9_\-]", output.communicate()[0]) if x and x != "-"]
                fullname = " ".join(split_out)
                u.set_attribute('fullname', fullname)
                results.append((u.get_attribute('username'), db.save(u.json())))
        return dumps({"results": results})
