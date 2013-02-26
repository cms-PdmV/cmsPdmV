#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from RestAPIMethod import RESTResource

class GetUserRoles(RESTResource):
	def __init__(self):
		self.authenticator.set_limit(0)

	def GET(self):
		return self.get_user_role()

	def get_user_role(self):
                user = cherrypy.request.headers['ADFS-LOGIN']
		role = self.authenticator.get_user_roles(user)
		return dumps({'username':user, 'roles':role})
