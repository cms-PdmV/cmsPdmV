#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from RestAPIMethod import RESTResource
from couchdb_layer.prep_database import database

class GetUserRoles(RESTResource):
	def __init__(self):
		self.authenticator.set_limit(0)

	def GET(self):
		return self.get_user_role()

	def get_user_role(self):
                user = cherrypy.request.headers['ADFS-LOGIN']
		communicationLine=None
		if 'REMOTE-USER' in cherrypy.request.headers:
			communicationLine = cherrypy.request.headers['REMOTE-USER']
		role = self.authenticator.get_user_roles(user,email=communicationLine)
		role_index = self.authenticator.get_roles().index(role[0])
		return dumps({'username':user, 'roles':role, 'role_index':  role_index})

class GetAllRoles(RESTResource):
	def __init__(self):
	    self.authenticator.set_limit(0)

	def GET(self):
	    return self.get_All_roles()

	def get_All_roles(self):
   	    roles = self.authenticator.get_roles()
	    return dumps(roles)

class GetAllUsers(RESTResource):
    def __init__(self):
	    self.db_name = 'users'
	    self.db = database(self.db_name)

    def GET(self):
	    return self.get_Users()

    def get_Users(self):
   	    # roles = self.authenticator.get_roles()
   	    return dumps({"results":self.db.get_all()})
	    # return dumps("test")

class GetUser(RESTResource):
    def __init__(self):
	    self.db_name = 'users'
	    self.db = database(self.db_name)
	    
    def GET(self, *args):
	    return dumps({"results":self.db.get( args[0])})

    def get_Users(self):
   	    # roles = self.authenticator.get_roles()
   	    return dumps({"results":self.db.get_all()})
	    # return dumps("test")

class AddRole(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.db = database(self.db_name)
        self.authenticator.set_limit(0)
        #self.user = None

    def add_user(self):
        username = cherrypy.request.headers['ADFS-LOGIN']
        email = cherrypy.request.headers['REMOTE-USER']
        role = self.authenticator.get_roles()[0]
        user = {}
        user["_id"] = username
        user["username"] = username
        user["email"] = email
        user["roles"] = [role]
        # save to db
        if not self.db.save(user):
            self.logger.error('Could not save object to database')
            return dumps({"results":False})
        return dumps({"results":True})

    def GET(self):
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
        current_role = doc["roles"][0]
        if action == '-1':
            if current_role != 'user': #if not the lowest role -> then him lower himself
                doc["roles"] = [self.all_roles[self.all_roles.index(current_role)-1]]
                return dumps({"results":self.db.update(doc)})
            return dumps({"results":username+" already is user"}) #else return that hes already a user
        if action == '1':
            if current_user["roles"][0] != "administrator":
                return dumps({"results":"Only administrators can upgrade roles"})
            if len(self.all_roles) != self.all_roles.index(current_role)+1: #if current role is not the top one
                doc["roles"] = [self.all_roles[self.all_roles.index(current_role)+1]]
                return dumps({"results":self.db.update(doc)})
            return dumps({"results":username+" already has top role"})
        return dumps({"results":"Failed to update user: "+username+" role"})
    def GET(self, *args):
        if not args:
            self.logger.error("No Arguments were given")
            return dumps({"results":'Error: No arguments were given'})
        return self.change_role(args[0],args[1])
