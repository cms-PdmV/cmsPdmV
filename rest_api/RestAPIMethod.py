#!/usr/bin/env python

class RESTResource(object):
	def __init__(self, content=''):
		self.content = content
	
	exposed = True

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
					
	
