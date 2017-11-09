#!/usr/bin/env python
import logging

from tools.user_management import access_rights, roles
from tools.user_management import authenticator, user_pack
from flask_restful import Resource
from flask import request, abort, make_response


class RESTResource(Resource):
    logger = logging.getLogger("mcm_error")
    access_limit = None
    access_user = []
    call_counters = {}

    limit_per_method = {
        'GET': access_rights.user,
        'PUT': access_rights.generator_contact,
        'POST': access_rights.generator_contact,
        'DELETE': access_rights.administrator
    }

    def __init__(self, content=''):
        self.content = content

    def before_request(self):
        if self.access_limit is not None:
            self.logger.info('Setting access limit to access_rights.%s (%s)' % (roles[self.access_limit], self.access_limit))
        elif request.method in self.limit_per_method:
            self.access_limit = self.limit_per_method[request.method]
        user_p = user_pack()
        if not user_p.get_username():
            # meaning we are going public, only allow GET.
            if 'public' not in request.path:
                self.logger.error('From within %s, adfs-login not found: \n %s \n %s' % (self.__class__.__name__, str(request.headers), str(request.path) ))
        else:
            if not authenticator.can_access(user_p.get_username(), self.access_limit):
                if user_p.get_username() in self.access_user:
                    self.logger.error('User %s allowed to get through'% user_p.get_username())
                else:
                    abort(403)

    def output_text(self, data, code, headers=None):
        """Makes a Flask response with a plain text encoded body"""
        resp = make_response(data, code)
        resp.headers.extend(headers or {})
        return resp

    def count_call(self):
        pass
        # counter for calls
        # method = getattr(self, request.method, None)
        # with locker.lock("rest-call-counter"):
        #    key = method.im_class.__name__ + method.__name__
        #    try:
        #        RESTResource.call_counters[key] += 1
        #    except KeyError:
        #        RESTResource.call_counters[key] = 0

    def GET(self):
        pass

    def PUT(self):
        pass

    def POST(self):
        pass

    def DELETE(self):
        pass


class RESTResourceIndex(RESTResource):
    def __init__(self, data=None):

        # this is the restriction for
        # the role of the user that can
        # access this method.
        self.access_role = access_rights.user

        self.res = ""
        if not data:
            self.data = {'PUT': [('import_request', 'Request JSON', 'Import a request to the database')],
                         'GET': [('get_request', 'prepid', 'Retrieve a request from the database'), (
                             'request_prepid', 'Pwg, Campaign Name',
                             'Generates the next available PREP_ID from the database'),
                                 ('get_cmsDriver', 'prepid', 'return a list of cmsDriver commands for a request')],
                         'DELETE': [('delete_request', 'prepid',
                                     'Delete a request from the d<th>GET Doc string</th>atabase and that\'s it ')]}
        else:
            self.data = data
        self.before_request()

    def get(self):
        """
        Returns the documentation of the resource
        """
        return self.index()

    def index(self):
        self.res = '<h1>REST API for McM<h2>'
        methods = ['GET', 'PUT', 'POST', 'DELETE']
        self.res += "<table border='1'><thead><tr><th>Path</th><th>Function name</th>" + ''.join(
            map(lambda s: '<th>%s method info</th><th>Access level</th><th>Calls counter</th>' % (s), methods)) + "</tr></thead><tbody>"
        keys = self.__dict__.keys()
        keys.sort()
        print keys
        for key in keys:
            o = getattr(self, key)
            self.res += "<tr>"
            if hasattr(o, 'access_limit'):
                self.res += "<td><a href=%s/><b>%s</b></a></td>" % (key, key)
                self.res += ' <td>%s</td>' % (o.__class__.__name__)
                limit = None
                if o.access_limit is not None:
                    limit = o.access_limit
                for m in methods:
                    if m in o.__class__.__dict__:
                        if getattr(o, m).__doc__:
                            self.res += '<td>%s</td>' % (getattr(o, m).__doc__)
                        else:
                            self.res += '<td><b>To be documented</b></td>'
                        if limit is not None:
                            self.res += '<td align=center>+%s</td>' % (roles[limit])
                        else:
                            self.res += '<td align=center>%s</td>' % (roles[self.limit_per_method[m]])
                        try:
                            c_key = o.__class__.__name__ + m
                            c = RESTResource.call_counters[c_key]
                        except KeyError:
                            c = 0
                        self.res += '<td align=center>{0}</td>'.format(c)
                    else:
                        self.res += '<td>&nbsp;</small> </td><td>&nbsp;</td><td>&nbsp;</small> </td>'
                self.res += "</tr>"

        self.res += "</tbody></table>"
        return self.res
