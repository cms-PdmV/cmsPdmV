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
		communicationLine=None
		if 'REMOTE-USER' in cherrypy.request.headers:
			communicationLine = cherrypy.request.headers['REMOTE-USER']
		role = self.authenticator.get_user_roles(user,email=communicationLine)
		return dumps({'username':user, 'roles':role})
