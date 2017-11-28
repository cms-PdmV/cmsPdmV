#!/usr/bin/env python
import logging
import cgi

from tools.user_management import access_rights, roles
from tools.user_management import authenticator, user_pack
from tools.locker import locker
from flask_restful import Resource
from flask import request, abort, make_response, current_app, render_template


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
        access_limit = self.__class__.access_limit
        if access_limit is not None:
            self.logger.info('Setting access limit to access_rights.%s (%s)' % (roles[access_limit], access_limit))
        elif request.method in self.limit_per_method:
            access_limit = self.limit_per_method[request.method]
        user_p = user_pack()
        if not user_p.get_username():
            # meaning we are going public, only allow GET.
            if 'public' not in request.path:
                self.logger.error('From within %s, adfs-login not found: \n %s \n %s' % (self.__class__.__name__, str(request.headers), str(request.path) ))
        else:
            if not authenticator.can_access(user_p.get_username(), access_limit):
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
        # counter for calls
        method = request.method
        with locker.lock("rest-call-counter"):
           key = self.__class__.__name__ + method
           print(key)
           try:
               RESTResource.call_counters[key] += 1
           except KeyError:
               RESTResource.call_counters[key] = 0


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
        methods = ['GET', 'PUT', 'POST', 'DELETE']
        data = []

        for rule in current_app.url_map.iter_rules():
            func = current_app.view_functions.get(rule.endpoint)
            if not hasattr(func, 'view_class'):
                # print('Rule ' + rule.rule + ' endpoint ' + rule.endpoint + ' has no view_class - SKIPPING')
                continue

            function_dict = {}

            rule_escaped = cgi.escape(rule.rule)
            function_name = func.view_class.__name__
            acc_limit = None

            if hasattr(func.view_class, 'access_limit'):
                acc_limit = getattr(func.view_class, 'access_limit')

            # print('Rule ' + rule.rule)
            # print('Endpoint ' + rule.endpoint)
            # print('Rule methods: ' + str(rule.methods))
            # print('Class name ' + func.view_class.__name__)
            # print('Access limit? ' + str(acc_limit))
            # print('Module ' + func.view_class.__module__)

            function_dict['path'] = rule.rule
            function_dict['function_name'] = function_name

            methods_list = []
            for m in methods:
                if m in rule.methods:
                    method_dict = {}
                    method_dict['name'] = m
                    
                    method_doc = func.view_class.__dict__.get(m.lower()).__doc__
                    if method_doc is None:
                        method_doc = 'To be documented'
                    method_dict['doc'] = method_doc

                    if acc_limit is not None:
                        method_dict['access_limit'] = roles[acc_limit]
                    else:
                        method_dict['access_limit'] = roles[func.view_class.limit_per_method[m]]

                    try:
                        c_key = function_name + m
                        c = RESTResource.call_counters[c_key]
                    except KeyError:
                        c = 0

                    method_dict['call_counter'] = '%d' % (c)

                    methods_list.append(method_dict)

            function_dict['methods'] = methods_list

            data.append(function_dict)

        # print(data)
        return self.output_text(render_template('restapi.html', data=data), 200, None)
