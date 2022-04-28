import logging
import re
import time

from tools.communicator import Communicator
from tools.locker import Locker
from copy import deepcopy
from model.user import Role, User
from tools.utils import make_regex_matcher
from couchdb_layer.mcm_database import Database


class ModelBase:
    __schema = {}
    logger = logging.getLogger("mcm_error")

    # String pattern checkers
    __campaign_prepid_pattern = '[a-zA-Z0-9]{3,60}'
    campaign_prepid_regex = make_regex_matcher(__campaign_prepid_pattern)
    __cmssw_pattern = 'CMSSW_[0-9]{1,3}_[0-9]{1,3}_[0-9]{1,3}.{0,20}'
    cmssw_regex = make_regex_matcher(__cmssw_pattern)
    __dataset_pattern = '^/[a-zA-Z0-9\\-_]{1,99}/[a-zA-Z0-9\\.\\-_]{1,199}/[A-Z\\-]{1,50}$'
    dataset_regex = make_regex_matcher(__dataset_pattern)
    __flow_prepid_pattern = 'flow[a-zA-Z0-9]{2,60}'
    flow_prepid_regex = make_regex_matcher(__flow_prepid_pattern)
    __primary_dataset_pattern = '^[A-Za-z][A-Za-z0-9\-_]{5,99}$'
    primary_dataset_regex = make_regex_matcher(__primary_dataset_pattern)
    __processing_string_pattern = '[a-zA-Z0-9_]{3,100}'
    processing_string_regex = make_regex_matcher(__processing_string_pattern)


    def __init__(self, data=None, validate=False):
        if not data:
            # If no data is provided, use default values from schema
            self.__json = deepcopy(self.schema())
        else:
            self.__json = deepcopy(data)
            self.ensure_schema_attributes()
            if validate:
                self.before_validate_attributes()
                self.validate()
                self.before_validate_attributes()

    def before_validate_attributes(self):
        """
        Called before attribute validation
        """

    def after_validate_attributes(self):
        """
        Called after attrubte validation
        """

    def ensure_schema_attributes(self, data_dict=None, schema=None, key_prefix=None):
        """
        Recursively iterate through data_dict and ensure that all atributes
        that are in given schema are present in data_dict and all that are not
        in schema are removed from the data_dict
        """
        if data_dict is None:
            data_dict = self.__json

        if schema is None:
            schema = self.schema()

        if key_prefix is None:
            key_prefix = ''

        data_keys = set(data_dict.keys())
        data_keys -= {'_rev', '_id'}
        obj_id = self.get_id()
        for key, default_value in schema.items():
            key_path = f'{key_prefix}.{key}'.lstrip('.')
            if key not in data_dict:
                self.logger.debug('Adding "%s"="%s" to %s', key_path, default_value, obj_id)
                data_dict[key] = deepcopy(default_value)
            else:
                data_keys.discard(key)
                if isinstance(default_value, dict) and isinstance(data_dict[key], dict):
                    # Only check if dictionary in schema is not empty,
                    # otherwise it would delete user-defined dictionary keys
                    if default_value:
                        self.ensure_schema_attributes(data_dict[key], default_value, key_path)

        for key in data_keys:
            key_path = f'{key_prefix}.{key}'.lstrip('.')
            if data_dict[key]:
                self.logger.debug('Removing "%s"="%s" of %s', key_path, data_dict[key], obj_id)
            else:
                self.logger.debug('Removing "%s" of %s', key_path, obj_id)

            del data_dict[key]

    def get_editing_info(self):
        """
        Return a dictionary of that specifies which attributes can be edited
        If attribute value is a dict, then the editing info value can be either
        a boolean that would indicate whether edits of the dict are allowed at
        all or another dict that specifies whether nested attributes can be
        edited
        If attribute value is a list, then the editign info value can be either
        a boolean that would indicate whether edits of the list are allwoed at
        all (including adding or removing elements) or a more complex structure
        that would be applied to each element of the list
        {
          "prepid": False,
          "notes": True,
          "some_list": False,
          "another_list": { # <- This dict will be applied to each item of
                            #    "another_list", index cannot be specified
              "list_item_attribute_1": False,
              "list_item_attribute_2": True
          }
          "some_dict": True,
          "another_dict": {
              "dict_item_attribute_1": True,
              "dict_item_attribute_2": False
          }
        }
        """
        self.logger.debug('Getting default editing info for %s', self.get_id())
        return {k: False for k in self.keys()}

    def validate(self):
        """
        Iterate through all attributes and validate the value
        """
        pass

    @classmethod
    def get_database(cls):
        """
        Return shared database instance
        """
        if not hasattr(cls, 'database'):
            if not hasattr(cls, 'database_name') or not cls.database_name:
                raise Exception('Database name not set')

            cls.database = Database(cls.database_name)

        return cls.database

    def get_actors(self):
        """
        Get tuples of username and email of all interested in the object people
        """
        actors = []
        seen_usernames = {'automatic'}
        history = self.get_attribute('history')
        for entry in history:
            updater = entry['updater']
            username = updater['author_username']
            if username in seen_usernames:
                continue

            action = entry['step']
            user = User.fetch(username)
            # Skip all users unless they specifically registered to receive
            # notifications
            if user.get_role() <= Role.USER and action != 'register':
                continue

            user_tuple = (username, user.get_email())
            actors.append(user_tuple)
            seen_usernames.add(username)

        return sorted(list(set(actors)))

    def notify(self, subject, body, sender=None):
        """
        Send notification to all people of the given object
        """
        recipients = [actor[1] for actor in self.get_actors() if actor[1]]
        user = User()
        sender = sender if sender else user.get_email()
        prepid = self.get_id()
        self.logger.info('Notification on %s from %s about "%s" body length %s',
                         prepid,
                         sender,
                         subject,
                         len(body))

        communicator = Communicator()
        return communicator.send_mail(recipients, subject, body, sender)

    def reload(self, save=True):
        """
        If `save` is set, save object to database first
        Re-fecth object from database and update the attributes
        """
        object_id = self.get_id()
        database = self.get_database()
        with Locker.get_lock(object_id):
            if save:
                if not self.save():
                    return False

            object_json = database.get(object_id)
            self.__init__(data=object_json, validate=False)

        return True

    def save(self):
        """
        Update if exists or create document in the database
        """
        object_id = self.get_id()
        database = self.get_database()
        with Locker.get_lock(object_id):
            object_json = self.json()
            if database.document_exists(object_id):
                success = database.update(object_json)
            else:
                success = database.save(object_json)

        self.set('_rev', object_json['_rev'])
        return success

    def update_history(self, action, step=''):
        """
        Add history entry
        Automatically add user info and timestamp
        """
        history = self.get_attribute('history') or []
        entry = {'action': action}
        if step:
            entry['step'] = step

        user = User()
        # Get current date and time as YYYY-mm-dd-HH-MM
        date_and_time = time.strftime('%Y-%m-%d-%H-%M', time.localtime(time.time()))
        entry['updater'] = {'author_username': user.get_username(),
                            'author_name': user.get_user_name(),
                            'author_email': user.get_email(),
                            'submission_date': date_and_time}

        history.append(entry)
        self.set_attribute('history', history)

    def set_attribute(self, attribute, value):
        if attribute not in self.schema() and attribute != '_rev':
            raise Exception('Cannot set "%s" because it does not exist in schema' % (attribute))

        self.__json[attribute] = value
        return self.__json

    def get_attribute(self, attribute):
        if attribute not in self.schema() and attribute != '_rev':
            raise Exception('Cannot get "%s" because it does not exist in schema' % (attribute))

        return self.__json[attribute]

    def set(self, attribute, value):
        return self.set_attribute(attribute, value)

    def get(self, attribute):
        return self.get_attribute(attribute)

    def get_id(self):
        """
        Attempt to return an object id
        """
        if 'prepid' in self.__json:
            return self.__json['prepid']

        if '_id' in self.__json:
            return self.__json['_id']

        class_name = self.__class__.__name__
        return f'<no-id-{class_name}>'

    def json(self):
        return self.__json

    @classmethod
    def schema(cls):
        return cls.__schema

    @classmethod
    def keys(cls):
        return list(cls.schema().keys())

    def correct_types(self):
        for key in self.__schema:
            value = self.__json[key]
            expected_type = type(self.__schema[key])
            got_type = type(value)
            if expected_type is float and got_type is int:
                continue

            if not isinstance(value, expected_type):
                self.logger.error('Wrong type for %s, expected %s, got %s', key, expected_type, got_type)
                return False
        return True

    def fullmatch(self, pattern, string):
        return re.match("(?:" + pattern + r")\Z", string)

    @classmethod
    def fetch(cls, prepid):
        data = cls.get_database().get(prepid)
        if not data:
            return None

        return cls(data)
