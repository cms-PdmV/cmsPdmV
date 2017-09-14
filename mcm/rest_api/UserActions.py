#!/usr/bin/env python

import cherrypy

from json import dumps

from RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from tools.settings import settings
from tools.communicator import communicator
from tools.locator import locator
from json_layer.user import user
from json_layer.notification import notification
from tools.user_management import user_pack, roles, access_rights
from tools.json import threaded_loads


class GetUserRole(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self):
        """
        Retrieve the role (string) of the current user
        """
        return dumps(self.get_user_role())

    def get_user_role(self):
        user_p = user_pack()
        role_index, role = self.authenticator.get_user_role_index(user_p.get_username(), email=user_p.get_email())
        return {'username': user_p.get_username(), 'role': role, 'role_index': role_index}


class GetAllRoles(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self):
        """
        Retrieve the list of possible roles
        """
        return dumps(self.get_All_roles())

    def get_All_roles(self):
        return roles


class GetUserPWG(RESTResource):
    def __init__(self):
        self.db_name = 'users'

    def GET(self, *args):
        """
        Retrieve the pwg of the provided user
        """
        ## this could be a specific database in couch, to hold the list, with maybe some added information about whatever the group does...

        all_pwgs = settings().get_value('pwg')
        db = database(self.db_name)

        all_pwgs.sort()
        if len(args) == 0:
            return dumps({"results": all_pwgs})
        user_name = args[0]
        if db.document_exists(user_name):
            mcm_user = user(db.get(args[0]))
            return dumps({"results": mcm_user.get_pwgs()})
        else:
            return dumps({"results": []})

class GetAllUsers(RESTResource):
    def __init__(self):
        self.db_name = 'users'

    def GET(self):
        """
        Retrieve the db content for all users
        """
        return dumps(self.get_Users())

    def get_Users(self):
        db = database(self.db_name)
        return {"results": db.get_all()}


class GetUser(RESTResource):
    def __init__(self):
        self.db_name = 'users'

    def GET(self, *args):
        """
        Retrieve the information about a provided user
        """
        db = database(self.db_name)
        return dumps({"results": db.get(args[0])})


class SaveUser(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.access_limit = access_rights.generator_convener

    def PUT(self):
        """
        Save the information about a given user
        """

        db = database(self.db_name)
        data = threaded_loads(cherrypy.request.body.read().strip())
        new_user = user(data)
        self.logger.debug("is trying to update entry for %s" % (new_user.get_attribute('username')))
        if '_rev' in data:
            new_user.update_history({'action': 'updated'})
            return dumps({"results": db.update(new_user.json())})
        else:
            new_user.update_history({'action': 'created'})
            return dumps({"results": db.save(new_user.json())})


class AskRole(RESTResource):
    def __init__(self):
        self.db_name = 'users'

    def GET(self, *args):
        """
        Ask for the increase of the role of the current user to the given pwg
        """
        if not args:
            return dumps({"results" : False, "Message" : "not pwg provided"})

        ## get who's there
        user_p = user_pack()
        udb = database(self.db_name)
        mcm_u = user( udb.get( user_p.get_username()))

        ## get the requested pwgs
        pwgs = args[0].split(',')
        #### set the pwgs to the current user
        current = mcm_u.get_attribute('pwg')
        current = list(set(current+pwgs))
        mcm_u.set_attribute('pwg', current)
        mcm_u.update_history({'action':'ask role','step' : args[0]})
        udb.update(mcm_u.json())

        ## get the production managers emails
        __query = udb.construct_lucene_query({'role' : 'production_manager'})
        production_managers = udb.full_text_search('search', __query, page=-1)
        ### send a notification to prod manager + service
        to_who = map(lambda u: u['email'], production_managers) + [settings().get_value('service_account')]
        to_who.append( user_p.get_email() )
        com = communicator()
        l_type = locator()
        subject = 'Increase role for user %s' % mcm_u.get_attribute('fullname')
        message = 'Please increase the role of the user %s to the next level.\n\n%susers?prepid=%s' % (
            mcm_u.get_attribute('username'),
            l_type.baseurl(),
            mcm_u.get_attribute('username')
        )
        notification.create_notification(
            subject,
            message,
            group=notification.USERS,
            action_objects=[mcm_u.get_attribute('prepid')],
            object_type='users',
            target_role='production_manager'
        )
        com.sendMail(to_who, subject, message)

        return dumps({"results" : True, "message" : "user %s in for %s" %( mcm_u.get_attribute('username'), current)})


class AddRole(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.access_limit = access_rights.user

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

    def GET(self):
        """
        Add the current user to the user database if not already
        """
        return dumps(self.add_user())


class ChangeRole(RESTResource):
    def __init__(self):
        self.db_name = 'users'
        self.all_roles = roles
        self.access_limit = access_rights.production_manager

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

    def GET(self, *args):
        """
        Increase /1 or decrease /-1 the given user role by one unit of role
        """
        if not args:
            self.logger.error("No Arguments were given")
            return dumps({"results": 'Error: No arguments were given'})
        return dumps(self.change_role(args[0], args[1]))


class FillFullNames(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Goes through database and fills full names of all the users, who have not had it filled yet
        """
        db = database('users')
        users = db.get_all()
        results = []
        for u_d in users:
            u = user(u_d)
            if not u.get_attribute('fullname'):
                import subprocess
                import re

                output = subprocess.Popen(
                    ["phonebook", "-t", "firstname", "-t", "surname", "--login", u.get_attribute('username')],
                    stdout=subprocess.PIPE)
                split_out = [x for x in re.split("[^a-zA-Z0-9_\-]", output.communicate()[0]) if x and x != "-"]
                fullname = " ".join(split_out)
                u.set_attribute('fullname', fullname)
                results.append((u.get_attribute('username'), db.save(u.json())))
        return dumps({"results": results})


class NotifyPWG(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def PUT(self):
        """
        Notifying given PWG
        """
        try:
            res = self.notify(cherrypy.request.body.read().strip())
            return dumps(res)
        except Exception as e:
            self.logger.error('Failed to notify pwg: ' + str(e))
            return dumps({'results': False, 'message': 'Failed to notify pwg'})

    def notify(self, body):
        db = database('users')
        data = threaded_loads(body)
        list_of_mails = [x["value"] for x in db.raw_query('pwg-mail', {'key': data["pwg"]})]
        com = communicator()
        com.sendMail(list_of_mails, data["subject"], data["content"], user_pack().get_email())
        return {'results': True, 'message': 'Sent message to {0}'.format(list_of_mails)}
