#!/usr/bin/env python

import cherrypy
import simplejson

#from Page import Page
from couchdb_layer.prep_database import database
import copy
from tools.locator import locator

class Search(object):

	def search(self, db_name, query, page,query_list=[]):
		self.db_name = db_name
		self.db = database(self.db_name)
		self.query = query
		self.query_list = query_list
		self.page = int(page)
		return self.run_query() 

		
	def run_query(self):
		if len(self.query_list):
			results_list= self.db.queries( self.query_list )
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
			
			query_result = self.db.unique_res(  res )
			results['results'] = query_result
			#results['results'] = res
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

		vetoed_keys = []
		for (view,f) in design['views'].items():
			if 'for(' in f['map'] or 'for (' in f['map']:
				vetoed_keys.append( view )
		allowed_key_search.sort()
		multiple_view=[]
		#### 
		## to switch on/off the view creation on the fly
		simple_search=(not locator().isDev())
		simple_search=False
		####
		for key in filter (lambda s : '-' not in s, allowed_key_search):
			if key in args:
				if key in vetoed_keys or simple_search:
					query_list.append('%s==%s'%(key,args[key]))
				else:
					multiple_view.append( (key, '"'+args[key]+'"') )
					if args[key].isdigit():
						multiple_view.append( (key, args[key]) )
					else:
						multiple_view.append( (key, '"'+args[key]+'"') )

				args.pop(key)

		if len(multiple_view)>1:
			multiple_search = '-'.join( map( lambda p:p[0], multiple_view))
			## faster query with multiple keys
			if not multiple_search in allowed_key_search:
				## try harder to find it
				really_not_there=True
				m_set = set( map( lambda p:p[0], multiple_view)  )
				for key in filter (lambda s : '-' in s, allowed_key_search):
					## parse all composite view
					if set(key.split('-')) == m_set:
						#we found one that has the same search in absolute, just the order is different
						# then re-order multiple_view so as to map to the existing view
						new_multiple_view = []
						for sv in key.split('-'):
							new_multiple_view.append( filter( lambda e : e[0]==sv, multiple_view) [0] )
						multiple_view = new_multiple_view
						multiple_search = '-'.join( map( lambda p:p[0], multiple_view))
						really_not_there=False
						break
				if really_not_there:
				        #tempatively add the view to the design
					new_func = "function(doc){ emit([%s], doc);}"%( ','.join(map( lambda k: "doc.%s"%(k), map( lambda p:p[0], multiple_view) )))
					design['views'] [ multiple_search ] = { "map" : new_func }
					saved = odb.update( design )
		                        ##### NOTE ####
				        ## the query that will follow will be super slow because the view needs to be re-build
				
				
			m_query = '%s==[%s]'%(multiple_search,
					    ','.join( map( lambda p:p[1], multiple_view))
					    )
			query_list.append( m_query )	       
			#query_list =[]
		elif len(multiple_view)==1:
			m_query = '%s==%s'%( multiple_view[0][0], multiple_view[0][1])
			query_list.append( m_query )

		#revert to simple query for one query only
		if len(query_list)==1:
			query=query_list[0]
			query_list=[]

		if len(args):
			## check whether the key is actually a member of the object in db and put back the view in the odb design
			return simplejson.dumps(args)
			#return simplejson.dumps(design['views'].keys())
		return self.search(db_name, query, page, query_list)

	search.exposed = True	
	index.exposed = True
