#!/usr/bin/env python

from collections import defaultdict
import cherrypy
from tools.locker import locker
from tools.settings import settings
from couchdb_layer.mcm_database import database

class user_pack:
    """
    Class used for transmission between user representation in requests and packed user representation
    """
    def __init__(self,db=False):
        self.user_dict = user_pack.get_request_header_dictionary()
        if db:
            if  self.get_username():
                ## the user name could be not provided in case of public/ apis
                udb = database('users')
                u = udb.get( self.get_username())
                self.user_dict['email'] = u['email']

    @staticmethod
    def get_request_header_dictionary():
        """
        Parse cherrypy header and get what's in there
        """
        if not cherrypy.request.headers:
            return defaultdict(lambda: None)
        user_dict = defaultdict(lambda: None, [(key.lower().replace('-','_'), value) if 'adfs' not in key.lower() else (key.lower().replace('adfs-', ''), value) for (key, value) in cherrypy.request.headers.iteritems()])
        return user_dict

    def __getattr__(self, name):
        if name.startswith('get_'):
            return lambda : self.user_dict['_'.join(name.split('_')[1:])]
        else:
            return self.user_dict[name]

    def get_username(self):
        return self.get_login()

    def get_email(self):
        return self.email if self.email else self.remote_user

    def get_name(self):
        return self.get_firstname()

    def get_surname(self):
        return self.get_lastname()

    def get_fullname(self):
        return self.get_firstname() + " " + self.get_lastname() if self.get_firstname() and self.get_lastname() else None



class authenticator:
    def __init__(self, limit=0):
        # roles list is a list of valid roles for a page
        self.__roles = ['user', 'generator_contact', 'generator_convener', 'production_manager', 'administrator']
        self.__db = database('users')
        self.__users_roles = dict()
        self.__lookup_counter = defaultdict(int)

        # limit is the numeric representation of a base role that cane
        # access a specific page
        self.__limit = 0

        # base role is the minimum requirement of a user to have in
        # order to access a specific page
        self.__base_role = ''

        self.set_limit(limit)

    # get the roles that are registered to a specific username
    def get_user_role(self, username, email=None):
        with locker.lock(username):
            if username not in self.__users_roles:
                if not self.__db.document_exists(username):
                    self.__users_roles[username] = self.__roles[0]
                else:
                    user = self.__db.get(username)
                    if email and ('email' not in user or user['email'] != email):
                        user['email'] = email
                        self.__db.update(user)
                    role = None
                    while not role:
                        try:
                            role = user['role']
                        except:
                            ## how to print an error from here ?
                            user = self.__db.get(username)
                            pass
                    self.__users_roles[username] = user['role']
            else:
                if self.__lookup_counter[username] == settings().get_value("user_cache_refresh_counter"):
                    if self.__db.document_exists(username):
                        self.__users_roles[username] = self.__db.get(username)['role']
                    self.__lookup_counter[username] = 0
                else:
                    self.__lookup_counter[username] += 1
            return self.__users_roles[username]

    def get_user_role_index(self, username, email=None):
        r = self.get_user_role(username, email)
        return self.__roles.index(r), r

    # aux: get the list of __roles
    def get_roles(self):
        return self.__roles

    # aux: get the numeric access limit
    def get_limit(self):
        return self.__limit

    def get_base_role(self):
        return self.__base_role

    # aux: set the list of valid roles
    def set_roles(self, roles=[]):
        if not roles:
            return
        self.__roles = roles

    def set_user_role(self, username, role):
        with locker.lock(username):
            self.__users_roles[username] = role

    def set_limit(self, limit=0):
        if limit < 0:
            raise ValueError('Access Limit provided is invalid: ' + str(self.__limit))

        if limit >= len(self.__roles):
            raise ValueError('Access Limit provided is illegal: ' + str(self.__limit))

        self.__limit = limit

        self.__base_role = self.__roles[self.__limit]

    # returns True, if a user matches the base role or higher
    # returns False, otherwise.
    def can_access(self, username):
        role = self.get_user_role(username)

        if self.__base_role == role:
            return True

        # if the user does not match the given role, then
        # maybe he has higher access rights.
        if role not in self.__roles:
            ###exception actually
            raise ValueError('role %s is not recognized' % ( role ))
        if self.__roles.index(role) >= self.__limit:
            return True
        return False

    def get_login_box(self, username):
        res = '<div id="login_box" style="float: right; display: block;"> '
        res += str(username)

        role = self.get_user_role(username)

        res += '\t(\tRole: ' + str(role)
        res += "\t)\t<a href='https://login.cern.ch/adfs/ls/?wa=wsignout1.0' style='float: right'>logout</a>"
        res += "</div>"
        return res

    @classmethod
    def user_has_access(cls, username, limit):
        auth = cls(limit)
        try:
            flag = auth.can_access(username)
        except ValueError as ex:
            print 'Error: ' + str(ex)
            return False
        return flag

    #def get_random_product_manager_email(self):
    #    pms = self.__db.query(query="role==production_manager", page_num=-1)
    #    from random import choice
    #    while True:
    #        pick = choice(pms)
    #        if "email" in pick and pick["email"]:
    #            return pick["email"]

