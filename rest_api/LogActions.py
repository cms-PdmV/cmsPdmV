#!/usr/bin/env python

import cherrypy
import re
from json import loads,dumps
from couchdb_layer.prep_database import database
from RestAPIMethod import RESTResource

class ReadInjectionLog(RESTResource):
	def __init__(self):
		self.authenticator.set_limit(2)
		self.logfile = 'logs/inject.log'
		self.db_name = 'requests'
		self.db = database(self.db_name)

	def GET(self, *args):
		if not args:
			self.logger.error('No arguments were given')
			return dumps({"results":'Error: No arguments were given'})
		return self.read_logs(args[0])

	def read_logs(self, pid):
		if not self.db.document_exists(pid):
			self.logger.error('Given prepid "%s" does not exist in the database.' % (pid))
			return dumps({"results":'Error:Given prepid "%s" does not exist in the database.' % (pid)})

		try:
			lines = open(self.logfile).readlines()
		except IOError as ex:
			self.logger.error('Could not access logs: "%s". Reason: %s' % (self.logfile, ex))
			return dumps({"results":"Error: Could not access logs."})
		res = ''
		for line in lines:
			if pid in line:
				res += '%s<br>' % (line.replace('<breakline>', '<br>'))
		return res
