#!/usr/bin/env python

from tools.authenticator import authenticator as auth_obj
from tools.logger import logger as logfactory
from tools.locator import locator
import logging
import logging.handlers
import cherrypy
import string


class RESTResource(object):
    authenticator = auth_obj(limit=3)
    #logger = cherrypy.log
    logger = logfactory('rest')
    access_limit = None

    limit_per_method = {
        'GET': 0,
        'PUT': 1,
        'POST': 1,
        'DELETE': 4
    }

    def __init__(self, content=''):
        self.content = content

    @cherrypy.expose
    def default(self, *vpath, **params):


        method = getattr(self, cherrypy.request.method, None)
        if not method:
            raise cherrypy.HTTPError(405, "Method not implemented.")

        if self.access_limit!=None:
            self.logger.log('Setting access limit to %s' % self.access_limit)
            self.authenticator.set_limit(self.access_limit)
        elif cherrypy.request.method in self.limit_per_method:
            self.authenticator.set_limit(self.limit_per_method[cherrypy.request.method])
        #elif cherrypy.request.method == 'GET':
        #	self.authenticator.set_limit(0)
        #elif cherrypy.request.method == 'PUT':
        #	self.authenticator.set_limit(1)
        #elif cherrypy.request.method == 'POST':
        #	self.authenticator.set_limit(1)
        #elif cherrypy.request.method == 'DELETE':
        #	self.authenticator.set_limit(3)
        else:
            raise cherrypy.HTTPError(403, 'You cannot access this page with method %s' % ( cherrypy.request.method ))
            #                print '######'
        #                print
        #
        #                print '######'
        #self.logger.error(cherrypy.request.headers)
        loweredHeaders = {}
        findHeaders = map(string.lower, ['adfs-login', 'user-agent'])
        for key in cherrypy.request.headers:
            if key.lower() in findHeaders:
                loweredHeaders[key.lower()] = cherrypy.request.headers[key]

        l_type = locator()
        if not 'adfs-login' in loweredHeaders:
            #meaning we are going public, only allow GET.
            #if cherrypy.request.method != 'GET' or not l_type.isDev():
            #	raise cherrypy.HTTPError(403, 'User credentials were not provided.')
            if not 'public' in str(cherrypy.url()):
                self.logger.error('From within %s, adfs-login not found: \n %s \n %s'%(self.__class__.__name__, str(cherrypy.request.headers), str(cherrypy.url()) ))
        else:
            #self.logger.error("User name found: -%s-"%(loweredHeaders['adfs-login']))
            if not self.authenticator.can_access(loweredHeaders['adfs-login']):
                raise cherrypy.HTTPError(403, 'You cannot access this page')
        #self.logger.log('method: ' + str(vpath) + ' params' + str(params))
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
            self.data = {'PUT': [('import_request', 'Request JSON', 'Import a request to the database')],
                         'GET': [('get_request', 'prepid', 'Retrieve a request from the database'), (
                             'request_prepid', 'Pwg, Campaign Name',
                             'Generates the next available PREP_ID from the database'),
                                 ('get_cmsDriver', 'prepid', 'return a list of cmsDriver commands for a request')],
                         'DELETE': [('delete_request', 'prepid',
                                     'Delete a request from the d<th>GET Doc string</th>atabase and that\'s it ')]}

    def GET(self):
        """
		Returns the documentation of the resource
		"""
        return self.index()

    def index(self):
        self.res = '<h1>REST API for McM<h2>'
        methods = ['GET', 'PUT', 'POST', 'DELETE']
        #self.res += "<table border='1'><thead><tr><th>Method</th><th>Function name</th><th>Function info</th>"+''.join( map(lambda s : '<th>%s method info</th><th>Access level</th>'%(s),methods))+"</tr></thead><tbody>"
        self.res += "<table border='1'><thead><tr><th>Path</th><th>Function name</th>" + ''.join(
            map(lambda s: '<th>%s method info</th><th>Access level</th>' % (s), methods)) + "</tr></thead><tbody>"
        #for method in self.data:
        #	self.res += "<li><b>"+method+"</b><br><table style:'width:100%'>"
        #	self.res += "<thead><td>Name</td><td>Parameters</td><td>Description</td></thead>"
        #	for r in self.data[method]:
        #		self.res += "<tr><td>"+r[0]+"</td><td>"+r[1]+"</td><td>"+r[2]+"</td></tr>"
        #	self.res += "</table></li>"
        #self.res += "</ul>"
        #self.res += "<br>".join(self.__dict__.keys())

        #self.res += "<ul>"
        for key in self.__dict__.keys():
            o = getattr(self, key)

            #for m in methods:
            #	if hasattr(o,m):
            #		self.res +=' '+m
            self.res += "<tr>"
            if hasattr(o, 'access_limit'):
                self.res += "<td><a href=%s/><b>%s</b></a></td>" % (key, key)
                self.res += ' <td>%s</td>' % (o.__class__.__name__)
                #if o.__class__.__doc__:
                #self.res +=' <td> %s</td>'%(o.__class__.__doc__)
                #else:
                #	 self.res +=' <td><b>To be documented</b></td>'
                limit = None
                if o.access_limit != None:
                    limit = o.access_limit
                for m in methods:
                    if m in o.__class__.__dict__:
                        if getattr(o, m).__doc__:
                            self.res += '<td>%s</td>' % (getattr(o, m).__doc__)
                        else:
                            self.res += '<td><b>To be documented</b></td>'
                            #self.res +='<td>%s</td>'%(o.__class__.__dict__)
                        if limit != None:
                            self.res += '<td align=center>+%s</td>' % (limit)
                        else:
                            self.res += '<td align=center>%s</td>' % (self.limit_per_method[m])
                    else:
                        #self.res +='<td><small>N/A</small> </td><td> <small>N/A</small> </td>'
                        self.res += '<td>&nbsp;</small> </td><td>&nbsp;</td>'
                        #self.res += "<td>"
                        #if o.access_limit:
                        #	 self.res +=' + %s'%( o.access_limit )
                        #else:
                        #self.res +=' %s'%( o.authenticator.get_limit())
                        #	 self.res +=' %s '% ( self.limit_per_method [m])
                        #self.res += "</td></tr>"
                self.res += "</tr>"

        self.res += "</tbody></table>"
        return self.res
