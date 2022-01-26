import logging
import re
import json
import time

from tools.locker import locker
from flask_restful import Resource
from flask import request, make_response, current_app, render_template
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
                        import traceback
                        self.logger.error(traceback.format_exc())
                        return {'results': False,
                                'message': str(ex)}
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
                logger = logging.getLogger('mcm_error')
                logger.debug('Ensuring user %s (%s) is allowed to acces API %s limited to %s',
                             user.get_username(),
                             user_role,
                             request.path,
                             role)
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
            ensure_role_wrapper_wrapper.__func__ = func
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
            logger = logging.getLogger('mcm_error')
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

        if hasattr(func, '__func__'):
            ensure_request_data_wrapper.__func__ = func.__func__

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

    def do_multiple_items(self, prepids, object_class, func):
        """
        Call the func function with an objects of object_class for each prepid
        "prepids" can be either a single prepid or a list of prepids
        """
        prepids_list = True
        if not isinstance(prepids, list):
            prepids_list = False
            prepids = [prepids]

        results = []
        for prepid in prepids:
            object_instance = object_class.fetch(prepid)
            if not object_instance:
                results.append({"results": False,
                                "prepid": prepid,
                                'message': 'Object "%s" does not exist' % (prepid)})
                continue

            try:
                func(object_instance)
                if not object_instance.save():
                    results.append({'results': False,
                                    'prepid': prepid,
                                    'message': 'Could not save %s to database' % (prepid)})
                else:
                    results.append({'results': True, 'prepid': prepid})
            except Exception as ex:
                import traceback
                self.logger.error(traceback.format_exc())
                results.append({'results': False,
                                'prepid': prepid,
                                'message': str(ex)})

        if not prepids_list and results:
            return results[0]

        return results


class DeleteRESTResource(RESTResource):

    def delete_check(self, obj):
        pass

    def delete_object(self, prepid, object_class):
        """
        Delete an object
        """
        database = object_class.get_database()
        if not database.document_exists(prepid):
            self.logger.error('%s could not be found', prepid)
            return {'results': False,
                    'prepid': prepid,
                    'message': '%s could not be found' % (prepid)}

        try:
            self.delete_check(object_class.fetch(prepid))
        except Exception as ex:
            import traceback
            self.logger.error(traceback.format_exc())
            return {'results': False,
                    'prepid': prepid,
                    'message': str(ex)}

        if not database.delete(prepid):
            self.logger.error('Could not delete %s from database', prepid)
            return {'results': False,
                    'prepid': prepid,
                    'message': 'Could not delete %s from database' % (prepid)}

        return {'results': True, 'prepid': prepid}
