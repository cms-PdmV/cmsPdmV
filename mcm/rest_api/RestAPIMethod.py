#!/usr/bin/env python
import logging
import re

from tools.user_management import access_rights, roles
from tools.user_management import authenticator, user_pack
from tools.locker import locker
from flask_restful import Resource
from flask import request, abort, make_response, current_app, render_template
import json


class RESTResource(Resource):
    logger = logging.getLogger("mcm_error")
    access_limit = None
    access_user = []
    call_counters = {}
    limit_per_method = {
        'GET': access_rights.user,
        'PUT': access_rights.generator_contact,
        'POST': access_rights.generator_contact,
        'DELETE': access_rights.administrator}

    def __init__(self, content=''):
        self.content = content

    def before_request(self):
        access_limit = self.__class__.access_limit
        if access_limit is not None:
            self.logger.info('Setting access limit to access_rights.%s (%s)' % (roles[access_limit], access_limit))
        elif request.method in self.limit_per_method:
            access_limit = self.limit_per_method[request.method]
        user_p = user_pack()
        try:
            self.user_dict = {'username': user_p.get_username(),
                              'role': authenticator.get_user_role(user_p.get_username())}
        except:
            self.user_dict = {'username': 'anonymous',
                              'role': 'user'}
        if not user_p.get_username():
            # meaning we are going public, only allow GET.
            if 'public' not in request.path:
                self.logger.error('From within %s, adfs-login not found: \n %s \n %s' % (self.__class__.__name__, str(request.headers), str(request.path)))
        else:
            if not authenticator.can_access(user_p.get_username(), access_limit):
                if user_p.get_username() in self.access_user:
                    self.logger.error('User %s allowed to get through' % user_p.get_username())
                else:
                    abort(403)

    def output_text(self, data, code, headers=None):
        """Makes a Flask response with a plain text encoded body"""
        if isinstance(data, dict):
            data = json.dumps(data)

        if isinstance(data, list):
            data = str(data)

        resp = make_response(data, code)
        if headers:
            for key, value in headers.iteritems():
                resp.headers[key] = value

        return resp

    def count_call(self):
        # counter for calls
        method = request.method
        with locker.lock("rest-call-counter"):
           key = self.__class__.__name__ + method
           try:
               RESTResource.call_counters[key] += 1
           except KeyError:
               RESTResource.call_counters[key] = 1

    def get_obj_diff(self, old, new, ignore_keys, diff=None, key_path=''):
        if diff is None:
            diff = []

        if isinstance(old, dict) and isinstance(new, dict):
            old_keys = set(old.keys())
            new_keys = set(new.keys())
            camparable_keys = old_keys.union(new_keys) - set(ignore_keys)
            for key in camparable_keys:
                key_with_prefix =  ('%s.%s' % (key_path, key)).strip('.')
                self.get_obj_diff(old.get(key), new.get(key), ignore_keys, diff, key_with_prefix)

        elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
            for index, (old_item, new_item) in enumerate(zip(old, new)):
                key_with_index = '%s[%s]' % (key_path, index)
                self.get_obj_diff(old_item, new_item, ignore_keys, diff, key_with_index)

        elif old != new:
            diff.append(key_path)

        return sorted(diff)

    def fullmatch(self, pattern, string):
        return re.match("(?:" + pattern + r")\Z", string)


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
        current_rule = request.url_rule.rule
        is_index = current_rule in ['/restapi', '/public', '/public/restapi']
        data = {}
        data['title'] = "Index for " + current_rule
        functions = []
        data['functions'] = functions
        for rule in current_app.url_map.iter_rules():
            func = current_app.view_functions.get(rule.endpoint)
            if not hasattr(func, 'view_class'):
                continue

            function_name = func.view_class.__name__
            if is_index and function_name != RESTResourceIndex.__name__:
                continue

            if not rule.rule.startswith(current_rule):
                continue

            if rule.rule == current_rule:
                # Do not include itself
                continue

            function_dict = {}
            function_dict['path'] = (rule.rule)[1:]
            function_dict['name'] = function_name
            functions.append(function_dict)
            if is_index:
                continue

            acc_limit = None
            if hasattr(func.view_class, 'access_limit'):
                acc_limit = getattr(func.view_class, 'access_limit')

            methods_list = []
            for m in methods:
                if m not in rule.methods:
                    # If rule does not have certain method - continue
                    continue

                method_dict = {}
                method_dict['name'] = m
                method_doc = func.view_class.__dict__.get(m.lower()).__doc__
                if method_doc is not None:
                    method_dict['doc'] = method_doc

                if acc_limit is not None:
                    method_dict['access_limit'] = roles[acc_limit]
                else:
                    method_dict['access_limit'] = roles[func.view_class.limit_per_method[m]]

                try:
                    call_count_key = function_name + m
                    call_count = RESTResource.call_counters[call_count_key]
                except KeyError:
                    call_count = 0

                method_dict['call_count'] = '%d' % (call_count)
                methods_list.append(method_dict)

            function_dict['methods'] = methods_list

        return self.output_text(render_template('restapi.html', data=data), 200, None)
