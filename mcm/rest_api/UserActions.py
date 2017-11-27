#!/usr/bin/env python

from simplejson import dumps, loads
from flask import request

from RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
import tools.settings as settings
from tools.communicator import communicator
from tools.locator import locator
from json_layer.user import user
from json_layer.notification import notification
from tools.user_management import user_pack, roles, access_rights, authenticator



class GetUserRole(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        self.before_request()
        self.count_call()

    def get(self):
        """
        Retrieve the role (string) of the current user
        """
        return self.get_user_role()

    def get_user_role(self):
        user_p = user_pack()
        role_index, role = authenticator.get_user_role_index(user_p.get_username(), email=user_p.get_email())
        return {'username': user_p.get_username(), 'role': role, 'role_index': role_index}


class GetUserPWG(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, user_id=None):
        """
        Retrieve the pwg of the provided user
        """
        ## this could be a specific database in couch, to hold the list, with maybe some added information about whatever the group does...

        all_pwgs = settings.get_value('pwg')
        db = database('users')

        all_pwgs.sort()
        if user_id is None:
            return {"results": all_pwgs}
        if db.document_exists(user_id):
            mcm_user = user(db.get(user_id))
            return {"results": mcm_user.get_pwgs()}
        else:
            return {"results": []}


class GetUser(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.before_request()
        self.count_call()

    def get(self, user_id):
        """
        Retrieve the information about a provided user
        """
        db = database(self.db_name)
        return {"results": db.get(user_id)}


class SaveUser(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.access_limit = access_rights.generator_convener
        self.before_request()
        self.count_call()

    def put(self):
        """
        Save the information about a given user
        """

        db = database(self.db_name)
        data = loads(request.data.strip())
        new_user = user(data)
        self.logger.debug("is trying to update entry for %s" % (new_user.get_attribute('username')))
        if '_rev' in data:
            new_user.update_history({'action': 'updated'})
            return {"results": db.update(new_user.json())}
        else:
            new_user.update_history({'action': 'created'})
            return {"results": db.save(new_user.json())}


class AskRole(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.before_request()
        self.count_call()

    def get(self, pwgs):
        """
        Ask for the increase of the role of the current user to the given pwg
        """
        ## get who's there
        user_p = user_pack()
        udb = database(self.db_name)
        mcm_u = user( udb.get( user_p.get_username()))

        ## get the requested pwgs
        pwgs = pwgs.split(',')
        #### set the pwgs to the current user
        current = mcm_u.get_attribute('pwg')
        current = list(set(current+pwgs))
        mcm_u.set_attribute('pwg', current)
        mcm_u.update_history({'action':'ask role','step' : pwgs})
        udb.update(mcm_u.json())

        ## get the production managers emails
        __query = udb.construct_lucene_query({'role' : 'production_manager'})
        production_managers = udb.full_text_search('search', __query, page=-1)
        ### send a notification to prod manager + service
        to_who = map(lambda u: u['email'], production_managers) + [settings.get_value('service_account')]
        to_who.append( user_p.get_email() )
        com = communicator()
        l_type = locator()
        subject = 'Increase role for user %s' % mcm_u.get_attribute('fullname')
        message = 'Please increase the role of the user %s to the next level.\n\n%susers?prepid=%s' % (
            mcm_u.get_attribute('username'),
            l_type.baseurl(),
            mcm_u.get_attribute('username')
        )
        notification(
            subject,
            message,
            [],
            group=notification.USERS,
            action_objects=[mcm_u.get_attribute('prepid')],
            object_type='users',
            target_role='production_manager'
        )
        com.sendMail(to_who, subject, message)

        return {"results" : True, "message" : "user %s in for %s" %( mcm_u.get_attribute('username'), current)}


class AddRole(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.access_limit = access_rights.user
        self.before_request()
        self.count_call()

    def add_user(self):
        db = database(self.db_name)
        user_p = user_pack()
        if db.document_exists(user_p.get_username()):
            return {"results": "User {0} already in database".format(user_p.get_username())}
        mcm_user = user({"_id": user_p.get_username(),
                         "username": user_p.get_username(),
                         "email": user_p.get_email(),
                         "role": roles[access_rights.user],
                         "fullname": user_p.get_fullname()})

        # save to db
        if not mcm_user.reload():
            self.logger.error('Could not save object to database')
            return {"results": False}

        mcm_user.update_history({'action':'created'})
        mcm_user.reload()
        return {"results": True}

    def get(self):
        """
        Add the current user to the user database if not already
        """
        return self.add_user()


class ChangeRole(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.all_roles = roles
        self.access_limit = access_rights.production_manager
        self.before_request()
        self.count_call()

    def change_role(self, username, action):
        db = database(self.db_name)
        doc = user(db.get(username))
        user_p = user_pack()
        current_user = user(db.get(user_p.get_username()))
        current_role = doc.get_attribute("role")
        if action == '-1':
            if current_role != self.all_roles[0]:
                doc.set_attribute("role", self.all_roles[self.all_roles.index(current_role) - 1])
                self.authenticator.set_user_role(username, doc.get_attribute("role"))
                doc.update_history({'action': 'decrease' , 'step':doc.get_attribute("role")})
                return {"results": db.update(doc.json())}
            return {"results": username + " already is user"} #else return that hes already a user
        if action == '1':
            if len(self.all_roles) != self.all_roles.index(current_role) + 1: #if current role is not the top one
                doc.set_attribute("role", self.all_roles[self.all_roles.index(current_role) + 1])
                self.authenticator.set_user_role(username, doc.get_attribute("role"))
                doc.update_history({'action': 'increase' , 'step':doc.get_attribute("role")})
                return {"results": db.update(doc.json())}
            return {"results": username + " already has top role"}
        return {"results": "Failed to update user: " + username + " role"}

    def get(self, user_id, action):
        """
        Increase /1 or decrease /-1 the given user role by one unit of role
        """
        return self.change_role(user_id, action)


class NotifyPWG(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        self.before_request()
        self.count_call()

    def put(self):
        """
        Notifying given PWG
        """
        try:
            res = self.notify(request.data.strip())
            return res
        except Exception as e:
            self.logger.error('Failed to notify pwg: ' + str(e))
            return {'results': False, 'message': 'Failed to notify pwg'}

    def notify(self, body):
        db = database('users')
        data = loads(body)
        list_of_mails = [x["value"] for x in db.raw_query('pwg-mail', {'key': data["pwg"]})]
        com = communicator()
        com.sendMail(list_of_mails, data["subject"], data["content"], user_pack().get_email())
        return {'results': True, 'message': 'Sent message to {0}'.format(list_of_mails)}
