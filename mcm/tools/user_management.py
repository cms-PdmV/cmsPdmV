#!/usr/bin/env python

import logging
import sys

from collections import defaultdict
from tools.locker import locker
from couchdb_layer.mcm_database import database
from tools.enum import Enum
from flask import request, has_request_context
from cachelib import SimpleCache


class user_pack:
    """
    Class used for transmission between user representation in requests and packed user representation
    """
    __db = database('users')
    __user_cache = SimpleCache()

    # Cache timeout in seconds
    CACHE_TIMEOUT = 30 * 60

    def __init__(self, db=False):
        self.user_dict = user_pack.get_request_header_dictionary()
        if db:
            username = self.get_username()
            if username:
                # the user name could be not provided in case of public/ apis
                user = self.__user_cache.get(username)
                if not user:
                    user = self.__db.get(username)
                    self.__user_cache.set(username, user, timeout=self.CACHE_TIMEOUT)

                self.user_dict['role'] = user['role']
                # we take email from DB if user is registered, else we use ADFS
                if user and "email" in user:
                    self.user_dict['email'] = user['email']

    @staticmethod
    def get_request_header_dictionary():
        """
        Parse flask request header and get what's in there
        """
        if not has_request_context():
            return defaultdict(lambda: None)
        user_dict = defaultdict(lambda: None, [(key.lower().replace('-', '_'), value) if not key.lower().startswith('adfs-') else (key.lower()[5:], value) for (key, value) in request.headers.items()])
        return user_dict

    def __getattr__(self, name):
        if name.startswith('get_'):
            return lambda: self.user_dict['_'.join(name.split('_')[1:])]
        else:
            return self.user_dict[name]

    def get_username(self):
        return self.user_dict['login']

    def get_email(self):
        return self.email if self.email else self.remote_user

    def get_name(self):
        return self.user_dict.get('firstname')

    def get_surname(self):
        return self.user_dict.get('lastname')

    def get_fullname(self):
        first_name = self.get_name()
        last_name = self.get_surname()
        if first_name and last_name:
            return '%s %s' % (first_name, last_name)
        else:
            return None

    @classmethod
    def cache_size(cls):
        """
        Return number of elements in cache and cache size in bytes
        """
        return len(cls.__user_cache._cache), sys.getsizeof(cls.__user_cache._cache)

    @classmethod
    def clear_cache(cls):
        """
        Clear cache
        """
        size = cls.cache_size()
        cls.__user_cache.clear()
        return size


roles = ('user', 'generator_contact', 'generator_convener', 'production_manager', 'administrator')
access_rights = Enum(*roles)


class authenticator:
    logger = logging.getLogger("mcm_error")

    # roles list is a list of valid roles for a page
    __db = database('users')
    __users_roles_cache = SimpleCache()

    # Cache timeout in seconds
    CACHE_TIMEOUT = 30 * 60

    # get the roles that are registered to a specific username
    @classmethod
    def get_user_role(cls, username, email=None):
        if not username:
            return 'user'

        with locker.lock(username):
            cached_value = cls.__users_roles_cache.get(username)
            if cached_value:
                return cached_value

            user_role = 'user'
            user = cls.__db.get(username)
            if user:
                user_role = user.get('role', roles[0])
                if email and user.get('email') != email:
                    user['email'] = email
                    cls.__db.update(user)

            cls.__users_roles_cache.set(username, user_role, timeout=cls.CACHE_TIMEOUT)
            return user_role

    @classmethod
    def get_user_role_index(cls, username, email=None):
        r = cls.get_user_role(username, email)
        return getattr(access_rights, r), r

    @classmethod
    def set_user_role(cls, username, role):
        with locker.lock(username):
            cls.__users_roles_cache.set(username, role, timeout=cls.CACHE_TIMEOUT)

    @classmethod
    def can_access(cls, username, limit):
        """
        returns True, if a user matches the base role or higher
        returns False, otherwise.
        """
        role = cls.get_user_role(username)
        try:
            if getattr(access_rights, role) >= limit:
                return True
            return False
        except AttributeError:
            raise ValueError('Role {0} is not recognized'.format(role))

    @classmethod
    def cache_size(cls):
        """
        Return number of elements in cache and cache size in bytes
        """
        return len(cls.__users_roles_cache._cache), sys.getsizeof(cls.__users_roles_cache._cache)

    @classmethod
    def clear_cache(cls):
        """
        Clear cache
        """
        size = cls.cache_size()
        cls.__users_roles_cache.clear()
        return size
