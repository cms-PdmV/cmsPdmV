import logging
import re
import json
import time

from tools.locker import locker
from flask_restful import Resource
from flask import request, abort, make_response, current_app, render_template
from json_layer.user import User, Role


class RESTResource(Resource):
    logger = logging.getLogger("mcm_error")

    def __getattribute__(self, name):
        """
        Catch GET, PUT, POST and DELETE methods and wrap them
        """
        if name in {'get', 'put', 'post', 'delete'}:
            attr = object.__getattribute__(self, name)
            if hasattr(attr, '__call__'):
                def wrapped_function(*args, **kwargs):
                    start_time = time.time()
                    try:
                        result = attr(*args, **kwargs)
                        if isinstance(result, (list, dict)):
                            result = RESTResource.build_response(result)

                        status_code = result.status_code
                    except Exception as ex:
                        status_code = 500
                        raise ex
                    finally:
                        end_time = time.time()
                        self.logger.info('[%s] %s %.4fs %s',
                                         name.upper(),
                                         request.path,
                                         end_time - start_time,
                                         status_code)
                    return result

                return wrapped_function

        return super().__getattribute__(name)

    @classmethod
    def ensure_role(cls, role):
        """
        Ensure that user has appropriate roles for this API call
        """
        def ensure_role_wrapper(func):
            """
            Wrapper
            """
            def ensure_role_wrapper_wrapper(*args, **kwargs):
                """
                Wrapper inside wrapper
                """
                if '/public/' in request.path:
                    # Public API, no need to ensure role
                    return func(*args, **kwargs)

                user = User()
                user_role = user.get_role()
                if user_role >= role:
                    return func(*args, **kwargs)

                username = user.get_username()
                api_role = role.name
                message = 'API not allowed. User "%s" has role "%s", required "%s"' % (username,
                                                                                       user_role,
                                                                                       api_role)
                return cls.build_response({'results': None, 'message': message}, code=403)

            ensure_role_wrapper_wrapper.__name__ = func.__name__
            ensure_role_wrapper_wrapper.__doc__ = func.__doc__
            ensure_role_wrapper_wrapper.__role__ = role
            return ensure_role_wrapper_wrapper

        return ensure_role_wrapper

    @classmethod
    def request_with_json(cls, func):
        """
        Ensure that request has data (POST, PUT requests) that's a valid JSON.
        Parse the data to a dict it and pass it as a keyworded 'data' argument
        """
        def ensure_request_data_wrapper(*args, **kwargs):
            """
            Wrapper around actual function
            """
            data = request.data
            logger = logging.getLogger("mcm_error")
            logger.debug('Ensuring request data for %s', request.path)
            if not data:
                logger.error('No data was found in request %s', request.path)
                return cls.build_response({'results': None,
                                           'message': 'No data was found in request'},
                                          code=400)

            try:
                data = json.loads(data)
            except json.decoder.JSONDecodeError as ex:
                logger.error('Invalid JSON: %s\nException: %s', data, ex)
                return cls.build_response({'results': None,
                                           'message': f'Invalid JSON {ex}'},
                                          code=400)

            kwargs['data'] = data
            return func(*args, **kwargs)

        ensure_request_data_wrapper.__name__ = func.__name__
        ensure_request_data_wrapper.__doc__ = func.__doc__
        if hasattr(func, '__role__'):
            ensure_request_data_wrapper.__role__ = func.__role__

        return ensure_request_data_wrapper

    @staticmethod
    def build_response(data, code=200, headers=None, content_type='application/json'):
        """
        Makes a Flask response with a plain text encoded body
        """
        if content_type == 'application/json':
            resp = make_response(json.dumps(data, indent=1, sort_keys=True), code)
        else:
            resp = make_response(data, code)

        resp.headers.extend(headers or {})
        resp.headers['Content-Type'] = content_type
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp

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
