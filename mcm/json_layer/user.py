"""
This module handles User class
"""
from copy import deepcopy
from enum import IntEnum
from flask import request
from flask import g as request_context
from cachelib import SimpleCache
from couchdb_layer.mcm_database import database as Database


class Role(IntEnum):
    """
    Roles in McM enum
    """
    ANONYMOUS = 0
    USER = 1
    MC_CONTACT = 2
    GEN_CONVENER = 3
    PRODUCTION_MANAGER = 4
    PRODUCTION_EXPERT = 5
    ADMINISTRATOR = 6

    def __str__(self):
        return self.name.lower()


class User():
    """
    User class is responsible for handling user objects as well as providing
    convenience methods such as returning user's role or PWGs
    Information is obtained from headers supplied by SSO proxy
    """
    cache = SimpleCache(default_timeout=3600) # Cache timeout 1h

    def __init__(self, data=None):
        if data:
            self.user_info = deepcopy(data)
        else:
            if hasattr(request_context, 'user_info'):
                self.user_info = request_context.user_info
            else:
                self.user_info = self.get_user_info(request.headers)
                setattr(request_context, 'user_info', self.user_info)

    def get_user_info(self, headers):
        """
        Check request headers and parse user information
        Also fetch info from the database and update the database if needed
        """
        username = headers.get('Adfs-Login')
        if username is None:
            # Not in a request context
            user_info = {'fullname': '',
                         'email': '',
                         'username': 'automatic',
                         'role': str(Role.ADMINISTRATOR)}
            return user_info

        if self.cache.has(username):
            return self.cache.get(username)

        email = headers.get('Adfs-Email')
        fullname = headers.get('Adfs-Fullname')
        user_info = {'fullname': fullname,
                     'email': email,
                     'username': username,
                     'role': str(Role.ANONYMOUS),
                     'history': [],
                     'notes': '',
                     'pwg': []}
        user_json = self.get_database().get(username)
        if not user_json:
            return user_info

        user_json.pop('_id', None)
        user_info['role'] = user_json['role']
        user_info['history'] = user_json['history']
        user_info['notes'] = user_json['notes']
        user_info['pwg'] = user_json['pwg']
        if email != user_json['email'] or fullname != user_json['fullname']:
            # If email or full name changed, update in database
            self.save()

        self.cache.set(username, user_info)
        return user_info

    @classmethod
    def fetch(cls, username):
        """
        Return a single user if it exists in database
        """
        if cls.cache.has(username):
            return cls.cache.get(username)

        user_json = cls.get_database().get(username)
        if not user_json:
            return None

        return cls(user_json)

    @classmethod
    def clear_cache(cls):
        """
        Clear users cache
        """
        cls.cache.clear()

    @classmethod
    def get_database(cls):
        """
        Return shared database instance
        """
        if not hasattr(cls, 'database'):
            cls.database = Database('users')

        return cls.database

    def save(self):
        """
        Save object to persistent storage
        """
        user_info = deepcopy(self.user_info)
        user_info['_id'] = self.get_username()
        user_info['role'] = str(user_info['role'])
        if '_rev' in user_info:
            saved = self.get_database().update(user_info)
        else:
            saved = self.get_database().save(user_info)

        if saved:
            self.cache.set(self.get_username(), user_info)

        return saved

    def get_username(self):
        """
        Get username, i.e. login name
        """
        return self.user_info['username']

    def get_user_name(self):
        """
        Get user name and last name
        """
        return self.user_info['name']

    def get_email(self):
        """
        Get user's email
        """
        return self.user_info['email']

    def get_role(self):
        """
        Get user role
        """
        return Role[self.user_info['role']]

    def set_role(self, role):
        """
        Set user role
        """
        self.user_info['role'] = role.name
