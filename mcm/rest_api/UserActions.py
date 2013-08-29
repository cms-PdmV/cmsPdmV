#!/usr/bin/env python

import cherrypy
from json import loads, dumps
from RestAPIMethod import RESTResource
from couchdb_layer.prep_database import database


class GetUserRole(RESTResource):
    def __init__(self):
        self.authenticator.set_limit(0)

    def GET(self):
        """
		Retrieve the role (string) of the current user
		"""
        return self.get_user_role()

    def get_user_role(self):
        user = cherrypy.request.headers['ADFS-LOGIN']
        communicationLine = None
        if 'REMOTE-USER' in cherrypy.request.headers:
            communicationLine = cherrypy.request.headers['REMOTE-USER']
        role = self.authenticator.get_user_role(user, email=communicationLine)
        role_index = self.authenticator.get_roles().index(role)
        return dumps({'username': user, 'role': role, 'role_index': role_index})


class GetAllRoles(RESTResource):
    def __init__(self):
        self.authenticator.set_limit(0)

    def GET(self):
        """
		Retrieve the list of possible roles 
		"""
        return self.get_All_roles()

    def get_All_roles(self):
        role = self.authenticator.get_roles()
        return dumps(role)


class GetUserPWG(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
	    Retrieve the pwg of the provided user
	    """
        ## this could be a specific database in couch, to hold the list, with maybe some added information about whatever the group does...
        all_pwgs = ['BPH', 'B2G', 'BTV', 'EGM', 'EWK', 'EXO', 'FWD', 'HIG', 'HIN', 'JME', 'MUO', 'QCD', 'SUS', 'TAU',
                    'TRK', 'TOP', 'TSG', 'SMP','L1T']
        all_pwgs.sort()
        if len(args) == 0:
            return dumps({"results": all_pwgs})
        user_name = args[0]
        if self.db.document_exists(user_name):
            user = self.db.get(args[0])
            if user['role'] in ['production_manager', 'administrator', 'generator_convener']:
                return dumps({"results": all_pwgs})
            else:
                return dumps({"results": user['pwg']})
        else:
            return dumps({"results": []})


class GetAllUsers(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.db = database(self.db_name)

    def GET(self):
        """
	    Retrieve the db content for all users
	    """
        return self.get_Users()

    def get_Users(self):
        # roles = self.authenticator.get_roles()
        return dumps({"results": self.db.get_all()})
        # return dumps("test")


class GetUser(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
	    Retrieve the information about a provided user
	    """
        return dumps({"results": self.db.get(args[0])})


class SaveUser(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.db = database(self.db_name)
        self.access_limit = 3

    def PUT(self):
        """
	    Save the information about a given user
	    """
        return dumps({"results": self.db.save(loads(cherrypy.request.body.read().strip()))})


class AddRole(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.db = database(self.db_name)
        self.authenticator.set_limit(0)
        #self.user = None

    def add_user(self):
        username = cherrypy.request.headers['ADFS-LOGIN']
        if self.db.document_exists(username):
            return dumps({"results": False})
        email = cherrypy.request.headers['REMOTE-USER']
        role = self.authenticator.get_roles()[0]
        user = {}
        user["_id"] = username
        user["username"] = username
        user["email"] = email
        #user["roles"] = [role]
        user["role"] = role
        user['pwg'] = []
        # save to db
        if not self.db.save(user):
            self.logger.error('Could not save object to database')
            return dumps({"results": False})
        return dumps({"results": True})

    def GET(self):
        """
	    Add the current user to the user database if not already
	    """
        return self.add_user()


class ChangeRole(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.db = database(self.db_name)
        self.all_roles = self.authenticator.get_roles()
        self.access_limit = 3

    def change_role(self, username, action):
        doc = self.db.get(username)
        current_user = self.db.get(cherrypy.request.headers['ADFS-LOGIN'])
        current_role = doc["role"]
        if action == '-1':
            if current_role != 'user': #if not the lowest role -> then him lower himself
                doc["role"] = self.all_roles[self.all_roles.index(current_role) - 1]
                self.authenticator.set_user_role(username, doc["role"])
                return dumps({"results": self.db.update(doc)})
            return dumps({"results": username + " already is user"}) #else return that hes already a user
        if action == '1':
            if current_user["role"] != "administrator":
                return dumps({"results": "Only administrators can upgrade roles"})
            if len(self.all_roles) != self.all_roles.index(current_role) + 1: #if current role is not the top one
                doc["role"] = self.all_roles[self.all_roles.index(current_role) + 1]
                self.authenticator.set_user_role(username, doc["role"])
                return dumps({"results": self.db.update(doc)})
            return dumps({"results": username + " already has top role"})
        return dumps({"results": "Failed to update user: " + username + " role"})

    def GET(self, *args):
        """
	Increase /1 or decrease /-1 the given user role by one unit of role
	"""
        if not args:
            self.logger.error("No Arguments were given")
            return dumps({"results": 'Error: No arguments were given'})
        return self.change_role(args[0], args[1])
