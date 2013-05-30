#!/usr/bin/env python

import cherrypy
import simplejson

#from Page import Page
from couchdb_layer.prep_database import database
import copy

class Search(object):

	def search(self, db_name, query, page,query_list=[]):
		self.db_name = db_name
		self.db = database(self.db_name)
		self.query = query
		self.query_list = query_list
		self.page = int(page)
		return self.run_query() 

		
	def run_query(self):
		def unique_res(query_result):
			docids = map(lambda doc : doc['_id'] , query_result)
			docids_s = list(set(docids))
			if len(docids) != len(docids_s):
				docids_s = []
				return_dict= copy.deepcopy( query_result )
				for doc in query_result:
					if not doc['_id'] in docids_s:
						docids_s.append(doc['_id'])
					else:
						return_dict.remove(doc)		
				return return_dict
			return query_result

		if len(self.query_list):
			results_list=[]
			##make each query separately and retrieve only the doc with counting == len(query_list)
			for (i,query) in enumerate(self.query_list):
				res = self.db.query(query, page_num=-1)
				query_result = unique_res( map(lambda r : r['value'], res) )
				if i!=0:
					## get only the one already in the intersection
					id_list = map(lambda doc : doc['_id'], results_list)
					results_list = filter(lambda doc : doc['_id'] in id_list, query_result)
				else:
					results_list= query_result
			results = { 'results' : results_list}
			
			final = simplejson.dumps(results)
			return final
		else:
			results = {}
			results['results'] = []
			if not self.query or self.query=='""':
				res = self.db.get_all(page_num=self.page)
			else:
				res = self.db.query(self.query, page_num=self.page)
			query_result = unique_res( map(lambda r : r['value'], res) )
			results['results'] = query_result
			final = simplejson.dumps(results)
			return final

	#def index(self, db_name='campaigns',query='', page=0):
	def index(self, **args):
		db_name='requests'
		query=''
		query_list=[]
		page=0
		manual_keys=['db_name','query','page']
		if 'db_name' in args:
			db_name=args['db_name']
			args.pop('db_name')
		if 'query' in args:
			query=args['query']
			args.pop('query')
		if 'page' in args:
			page=args['page']
			args.pop('page')
		# retrieve the _design/object document
		odb=database(db_name)
		design = odb.get('_design/%s'%(db_name))
		allowed_key_search = design['views'].keys()
		for key in allowed_key_search:
			if key in args:
				query_list.append('%s==%s'%(key,args[key]))
				args.pop(key)

		if len(args):
			return simplejson.dumps(args)
			#return simplejson.dumps(design['views'].keys())
		return self.search(db_name, query, page, query_list)

	search.exposed = True	
	index.exposed = True
