from copy import deepcopy
import logging
import re
import json
import time
from tools.exceptions import BadAttributeException, CouldNotSaveException, McMException, NotFoundException

import flask
from tools.locker import LockedException, Locker
from flask_restful import Resource
from flask import request, make_response, current_app, render_template
from model.user import User, Role


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
                            result = self.build_response(result)

                        status_code = result.status_code
                    except McMException as mex:
                        status_code = 400
                        return {'results': False,
                                'message': str(mex)}
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

    def do_multiple_items(self, prepids, object_class, func, blocking=False):
        """
        Call the func function with an objects of object_class for each prepid
        "prepids" can be either a single prepid or a list of prepids
        """
        prepids_list = True
        if not isinstance(prepids, list):
            prepids_list = False
            prepids = [prepids]

        results = []
        if blocking:
            lock_func = Locker.get_lock
        else:
            lock_func = Locker.get_nonblocking_lock

        for prepid in prepids:
            try:
                with lock_func(prepid):
                    object_instance = object_class.fetch(prepid)
                    if not object_instance:
                        results.append({'results': False,
                                        'prepid': prepid,
                                        'message': f'Object "{prepid}" does not exist'})

                    try:
                        func(object_instance)
                        if not object_instance.save():
                            results.append({'results': False,
                                            'prepid': prepid,
                                            'message': f'Could not save "{prepid}" to database'})

                        results.append({'results': True,
                                        'prepid': prepid})
                    except Exception as ex:
                        import traceback
                        self.logger.error(traceback.format_exc())
                        results.append({'results': False,
                                        'prepid': prepid,
                                        'message': str(ex)})

            except LockedException:
                results.append({'results': False,
                                'prepid': prepid,
                                'message': f'"{prepid}" is locked'})

        if not prepids_list and results:
            return results[0]

        return results

    def check_if_edits_are_allowed(self, changes, editing_info, prefix=None):
        """
        Check if all done changes are allowed based on editing info
        """
        if prefix is None:
            prefix = ''

        if isinstance(editing_info, bool):
            if not editing_info:
                raise BadAttributeException(f'Not allowed to change "{prefix}"')

        for changed_key, changed_value in changes.items():
            value_editing_info = editing_info.get(changed_key, False)
            key_with_prefix = f'{prefix}.{changed_key}'.lstrip('.')
            if isinstance(value_editing_info, bool):
                if value_editing_info:
                    continue

                raise BadAttributeException(f'Not allowed to change "{key_with_prefix}"')

            if isinstance(changed_value, list):
                for i, value in enumerate(changed_value):
                    self.check_if_edits_are_allowed(value,
                                                    value_editing_info,
                                                    f'{key_with_prefix}[{i}]')

            elif isinstance(changed_value, dict):
                self.check_if_edits_are_allowed(changed_value,
                                                value_editing_info,
                                                key_with_prefix)

    def get_changes(self, reference, target):
        """
        Get changes between reference and target objects/values
        If reference and target are dicts, return a dict with keys of values
        that changed
        If reference and target are lists, return a list where each item is a
        boolean that shows whether value changed
        If reference and target are neither dicts nor lists, return a boolean
        indicating whether values changed
        If dict or list values are other dicts or lists, this function
        recursively iterates through all inner structures
        If neither value or any inner values of dict changed, then the key
        will not be included in the return value at all, i.e. this function
        returns only changes
        Example:
        reference = {'a': 1, 'b': [2,3], 'c': [4,5],   'd': {'dx': 6, 'dy': 7}}
        target =    {'a': 1, 'b': [2,4], 'c': [4,5,6], 'd': {'dx': 9, 'dy': 7}}
                                     ^             ^               ^
        changes =   {'b': [false, true], 'c': true,    'd': {'dx': true}}
        """
        if isinstance(reference, dict) and isinstance(target, dict):
            # Comparing two dictionaries
            changed_dict = {}
            keys = set(reference.keys()).union(set(target.keys()))
            for key in keys:
                reference_item = reference.get(key)
                target_item = target.get(key)
                changed_dict[key] = self.get_changes(reference_item, target_item)

            return {k: v for k, v in changed_dict.items() if v}

        if isinstance(reference, list) and isinstance(target, list):
            # Comparing two lists
            if len(reference) != len(target):
                return True

            changed_list = []
            for reference_item, target_item in zip(reference, target):
                changed_list.append(self.get_changes(reference_item, target_item))

            if all(not v for v in changed_list):
                return []

            return changed_list

        # Comparing two values
        return reference != target

    def stringify_changes(self, changes, prefix='', stringified=None):
        """
        Make a list of a human readable change strings
        """
        if stringified is None:
            stringified = []

        if isinstance(changes, dict):
            for key, value in changes.items():
                self.stringify_changes(value, f'{prefix}.{key}', stringified)

            return stringified

        if isinstance(changes, list):
            for index, value in enumerate(changes):
                self.stringify_changes(value, f'{prefix}[{index}]', stringified)

            return stringified

        if changes:
            stringified.append(prefix.lstrip('.'))

        return stringified


class CreateRESTResource(RESTResource):

    def before_create(self, obj):
        pass

    def after_create(self, obj):
        pass

    def create_object(self, data, object_class):
        """
        Create an object
        """
        prepid = data.get('prepid', data.get('_id'))
        if not prepid:
            self.logger.error('Missing "prepid" attribute')
            return {'results': False,
                    'prepid': prepid,
                    'message': 'Missing "prepid" attribute'}

        database = object_class.get_database()
        if database.document_exists(prepid):
            self.logger.error('Object with prepid "%s" already exists', prepid)
            return {'results': False,
                    'prepid': prepid,
                    'message': 'Object with prepid "%s" already exists' % (prepid)}

        data.pop('history', None)
        data.pop('_rev', None)
        obj = object_class(data)
        self.logger.info('Creating new object "%s"', prepid)
        # Validate
        obj.validate()
        # Mandatory attributes
        obj.set('prepid', prepid)
        obj.set('_id', prepid)
        obj.update_history('created')
        # Allow updates
        self.before_create(obj)

        # Save to DB
        self.logger.info('Saving new object "%s"', prepid)
        if not obj.reload(save=True):
            self.logger.error('Could not save %s to database', prepid)
            return {'results': False,
                    'prepid': prepid,
                    'message': 'Could not save %s to database' % (prepid)}

        # After update callback
        self.after_create(obj)
        return {'results': True, 'prepid': prepid}


class UpdateRESTResource(RESTResource):

    def before_update(self, old_obj, new_obj):
        pass

    def after_update(self, old_obj, new_obj, changes):
        pass

    def update_object(self, data, object_class):
        """
        Update an object
        """
        prepid = data.get('prepid', data.get('_id'))
        if not prepid:
            self.logger.error('Missing "prepid" attribute')
            return {'results': False,
                    'prepid': prepid,
                    'message': 'Missing "prepid" attribute'}

        with Locker.get_nonblocking_lock(prepid):
            old_obj = object_class.fetch(prepid)
            if not old_obj:
                self.logger.error('%s could not be found', prepid)
                return {'results': False,
                        'prepid': prepid,
                        'message': '%s could not be found' % (prepid)}

            self.logger.info('Updating object "%s"', prepid)
            new_obj = object_class(data)
            if new_obj.get('_rev') != old_obj.get('_rev'):
                self.logger.error('Provided revision does not match revision in database')
                return {'results': False,
                        'prepid': prepid,
                        'message': 'Provided revision does not match revision in database'}

            new_obj.set('history', old_obj.get('history'))
            # Validate
            new_obj.validate()
            # Allow updates
            self.before_update(old_obj, new_obj)
            # Difference
            changes = self.get_changes(old_obj.json(), new_obj.json())
            if not changes:
                self.logger.info('No updates for "%s"', prepid)
                return {'results': True,
                        'prepid': prepid,
                        'message': 'Nothing changed'}

            editing_info = old_obj.get_editing_info()
            self.logger.info('Changes of %s update: %s', prepid, changes)
            self.logger.debug('Editing info %s', editing_info)
            self.check_if_edits_are_allowed(changes, editing_info)
            changes_str = ', '.join(sorted(self.stringify_changes(changes)))
            new_obj.update_history('update', changes_str)

            # Save to DB
            self.logger.info('Saving updated object "%s"', prepid)
            if not new_obj.reload(save=True):
                self.logger.error('Could not save %s to database', prepid)
                return {'results': False,
                        'prepid': prepid,
                        'message': 'Could not save %s to database' % (prepid)}

        # After update callback
        self.after_update(old_obj, new_obj, changes)
        return {'results': True, 'prepid': prepid}


class DeleteRESTResource(RESTResource):

    def delete_check(self, obj):
        pass

    def before_delete(self, obj):
        pass

    def after_delete(self, obj):
        pass

    def delete_object(self, prepid, object_class):
        """
        Delete an object
        """
        database = object_class.get_database()
        with Locker.get_nonblocking_lock(prepid):
            object = object_class.fetch(prepid)
            if not object:
                self.logger.error('%s could not be found', prepid)
                return {'results': False,
                        'prepid': prepid,
                        'message': '%s could not be found' % (prepid)}

            try:
                self.logger.info('Performing pre-delete checks for %s', prepid)
                self.delete_check(object)
                self.logger.info('%s passed pre-delete checks', prepid)
            except McMException as mex:
                return {'results': False,
                        'prepid': prepid,
                        'message': str(mex)}
            except Exception as ex:
                import traceback
                self.logger.error(traceback.format_exc())
                return {'results': False,
                        'prepid': prepid,
                        'message': str(ex)}

            self.before_delete(object)
            if not database.delete(prepid):
                self.logger.error('Could not delete %s from database', prepid)
                return {'results': False,
                        'prepid': prepid,
                        'message': 'Could not delete %s from database' % (prepid)}

        self.after_delete(object)
        return {'results': True, 'prepid': prepid}


class GetRESTResource(RESTResource):
    """
    Endpoing for retrieving an object
    """

    def get(self, prepid):
        """
        Retrieve the object for given id
        """
        obj = self.object_class.get_database().get(prepid)
        if not obj:
            raise NotFoundException(prepid)

        return {'results': obj}


class GetEditableRESTResource(RESTResource):
    """
    Endpoing for retrieving an object and it's editing info
    """

    def get(self, prepid=None):
        """
        Retrieve the object and it's editing info for given id
        """
        if prepid:
            obj = self.object_class.fetch(prepid)
            if not obj:
                raise NotFoundException(prepid)
        else:
            obj = self.object_class()

        return {'results': {'object': obj.json(),
                            'editing_info': obj.get_editing_info()}}


class GetUniqueValuesRESTResource(RESTResource):
    """
    Endpoint for getting unique values of object attributes
    """

    def get(self):
        """
        Get unique values of certain attribute
        """
        args = flask.request.args.to_dict()
        attribute = args.get('attribute')
        value = args.get('value')
        if not attribute or not value:
            return {'results': []}

        limit = int(args.get('limit', 10))
        limit = min(100, max(1, limit))
        database = self.object_class.get_database()
        return {'results': database.query_unique(attribute, value, limit)}


class CloneRESTResource(CreateRESTResource):
    """
    Endpoint for making an identical clone of an object with new prepid
    """

    def before_create(self, obj):
        obj.set('history', [])
        obj.update_history('clone', self.prepid)
        return super().before_create(obj)

    def clone_object(self, data, object_class):
        """
        Make a clone of an object
        """
        prepid = data.get('prepid')
        new_prepid = data.get('new_prepid')
        if not prepid or not new_prepid:
            self.logger.error('Missing either old or new "prepid" attribute')
            return {'results': False,
                    'message': 'Missing either old or new "prepid" attribute'}

        if prepid == new_prepid:
            self.logger.error('Old and new "prepid" cannot be the same')
            return {'results': False,
                    'prepid': prepid,
                    'message': 'Old and new "prepid" cannot be the same'}

        object = object_class.fetch(prepid)
        if not object:
            self.logger.error('%s could not be found', prepid)
            return {'results': False,
                    'prepid': prepid,
                    'message': '%s could not be found' % (prepid)}

        database = object_class.get_database()
        if database.document_exists(new_prepid):
            self.logger.error('Object with prepid "%s" already exists', new_prepid)
            return {'results': False,
                    'prepid': new_prepid,
                    'message': 'Object with prepid "%s" already exists' % (new_prepid)}

        new_data = deepcopy(object.json())
        new_data['prepid'] = new_prepid
        new_data['_id'] = new_prepid

        self.prepid = prepid
        return self.create_object(new_data, object_class)
