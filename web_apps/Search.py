#!/usr/bin/env python

import cherrypy
import simplejson
from Page import Page
from couchdb_layer.prep_database import database


class Search(object):

	def search(self, db_name, query, page):
		self.db_name = db_name
		self.db = database(self.db_name)
		self.query = query
		self.page = int(page)
		return self.run_query() 

	def run_query(self):
		results = {}
		results['results'] = []
		if not self.query or self.query=='""':
			res = self.db.get_all(page_num=self.page)
		else:
			res = self.db.query(self.query, page_num=self.page)
		for r in res:
                	results['results'].append(r['value']) 
                final = simplejson.dumps(results)
		return final

	def index(self, db_name='campaigns',query='', page=0):
		return self.search(db_name,query, page)

	search.exposed = True	
	index.exposed = True
