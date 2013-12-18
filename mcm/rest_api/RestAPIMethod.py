#!/usr/bin/env python

from tools.user_management import access_rights, roles
from tools.user_management import authenticator as auth_obj, user_pack
from tools.logger import logfactory
from tools.locator import locator
from tools.locker import locker
import cherrypy
from collections import defaultdict


class RESTResource(object):
    authenticator = auth_obj(limit=access_rights.production_manager)
    #logger = cherrypy.log
    logger = logfactory
    access_limit = None
    counter = defaultdict(lambda: defaultdict(int))

    limit_per_method = {
        'GET': access_rights.user,
        'PUT': access_rights.generator_contact,
        'POST': access_rights.generator_contact,
        'DELETE': access_rights.administrator
    }

    def __init__(self, content=''):
        self.content = content

    @cherrypy.expose
    def default(self, *vpath, **params):


        method = getattr(self, cherrypy.request.method, None)
        if not method:
            raise cherrypy.HTTPError(405, "Method not implemented.")

        if self.access_limit is not None:
            self.logger.log('Setting access limit to access_rights.%s (%s)' % (roles[self.access_limit], self.access_limit))
            self.authenticator.set_limit(self.access_limit)
        elif cherrypy.request.method in self.limit_per_method:
            self.authenticator.set_limit(self.limit_per_method[cherrypy.request.method])
        else:
            raise cherrypy.HTTPError(403, 'You cannot access this page with method %s' % cherrypy.request.method )

        user_p = user_pack()

        l_type = locator()
        if not user_p.get_username():
            #meaning we are going public, only allow GET.
            #if cherrypy.request.method != 'GET' or not l_type.isDev():
            #	raise cherrypy.HTTPError(403, 'User credentials were not provided.')
            if not 'public' in str(cherrypy.url()):
                self.logger.error('From within %s, adfs-login not found: \n %s \n %s' % (self.__class__.__name__, str(cherrypy.request.headers), str(cherrypy.url()) ))
        else:
            if not self.authenticator.can_access(user_p.get_username()):
                raise cherrypy.HTTPError(403, 'You cannot access this page, the limit for the page is {0} ({1})'.format(roles[self.authenticator.get_limit()],
                                                                                                                        self.authenticator.get_limit()))
        # counter for calls
        with locker.lock("rest-call-counter"):
            self.counter[method.im_class.__name__][method.__name__] += 1
        return method(*vpath, **params)

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
        self.access_role = access_rights.user

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
            map(lambda s: '<th>%s method info</th><th>Access level</th><th>Calls counter</th>' % (s), methods)) + "</tr></thead><tbody>"
        #for method in self.data:
        #	self.res += "<li><b>"+method+"</b><br><table style:'width:100%'>"
        #	self.res += "<thead><td>Name</td><td>Parameters</td><td>Description</td></thead>"
        #	for r in self.data[method]:
        #		self.res += "<tr><td>"+r[0]+"</td><td>"+r[1]+"</td><td>"+r[2]+"</td></tr>"
        #	self.res += "</table><\/li>"
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
                        self.res += '<td align=center>{0}</td>'.format(RESTResource.counter[o.__class__.__name__][m])
                    else:
                        #self.res +='<td><small>N/A</small> </td><td> <small>N/A</small> </td>'
                        self.res += '<td>&nbsp;</small> </td><td>&nbsp;</td><td>&nbsp;</small> </td>'
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
