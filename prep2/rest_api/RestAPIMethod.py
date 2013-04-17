#!/usr/bin/env python

from tools.authenticator import authenticator as auth_obj
from tools.logger import logger as logfactory
import logging
import logging.handlers
import cherrypy
import string

class RESTResource(object):
	authenticator = auth_obj(limit=3)
	#logger = cherrypy.log
	logger = logfactory('rest')

	def __init__(self, content=''):
		self.content = content
	
	@cherrypy.expose
	def default(self, *vpath, **params):


		method = getattr(self, cherrypy.request.method, None)
		if not method:
			raise cherrypy.HTTPError(405, "Method not implemented.")
		
		if cherrypy.request.method == 'GET':
			self.authenticator.set_limit(0)
		elif cherrypy.request.method == 'PUT':
			self.authenticator.set_limit(1)
		elif cherrypy.request.method == 'POST':
			self.authenticator.set_limit(1)
		elif cherrypy.request.method == 'DELETE':
			self.authenticator.set_limit(3)
#                print '######'
#                print 
#                
#                print '######'
		#self.logger.error(cherrypy.request.headers)
		loweredHeaders={}
		findHeaders=map(string.lower, ['adfs-login','user-agent'])
		for key in cherrypy.request.headers:
			if key.lower() in findHeaders:
				loweredHeaders[key.lower()]=cherrypy.request.headers[key]
				
		if not 'adfs-login' in loweredHeaders:
			#meaning we are going public, only allow GET.
			if cherrypy.request.method != 'GET': 
				raise cherrypy.HTTPError(403, 'User credentials were not provided.')
			self.logger.error(cherrypy.request.headers)
		else:
			#self.logger.error("User name found: -%s-"%(loweredHeaders['adfs-login']))
			if not self.authenticator.can_access(loweredHeaders['adfs-login']):
				raise cherrypy.HTTPError(403, 'You cannot access this page')

		return method(*vpath, **params);
	
	def GET(self):
		pass
	def PUT(self):
		pass
	def POST(self):
		pass
	def DELETE(self):
		pass


class RESTResourceIndex(RESTResource):
	def __init__(self, data={}):

		# this is the restriction for 
		# the role of the user that can
		# access this method.
		self.access_role = 0

		self.res = ""
		self.data = data
		if not self.data:
			self.data = {'PUT':[('import_request','Request JSON', 'Import a request to the database')], 'GET':[('get_request', 'prepid', 'Retrieve a request from the database'), ('request_prepid', 'Pwg, Campaign Name', 'Generates the next available PREP_ID from the database'), ('get_cmsDriver', 'prepid', 'return a list of cmsDriver commands for a request')], 'DELETE':[('delete_request', 'prepid', 'Delete a request from the database')]}
	
	def GET(self):
		return self.index()

	def index(self):
		self.res = '<h1>REST API for PREP<h2>'
		self.res += "<ul>"
		for method in self.data:
			self.res += "<li><b>"+method+"</b><br><table style:'width:100%'>"
			self.res += "<thead><td>Name</td><td>Parameters</td><td>Description</td></thead>"
			for r in self.data[method]:
				self.res += "<tr><td>"+r[0]+"</td><td>"+r[1]+"</td><td>"+r[2]+"</td></tr>"
			self.res += "</table></li>"
		self.res += "</ul>"
		return self.res
					
	
