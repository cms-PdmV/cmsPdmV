import json
from flask import request
from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database as Database
from tools.locker import Locker
from tools.settings import Settings
from tools.locator import locator
from json_layer.user import Role, User


class GetUser(RESTResource):

    def get(self, username):
        """
        Retrieve the information about a provided user
        """
        user_db = Database('users')
        return {'results': user_db.get(username)}


class UpdateUser(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def put(self):
        """
        Save the information for given user
        Users can't change role of users with higher role than theirs
        e.g. PRODUCTION_MANAGER can't touch PRODUCTION_EXPERT and ADMINISTRATOR
        Users can't change role to higher than theirs
        e.g. PRODUCTION_MANAGER can set roles only up to PRODUCTION_MANAGER
        """
        user_db = Database('users')
        new_data = json.loads(request.data)
        username = new_data.get('username')
        changer = User()
        with Locker().lock(username):
            user_data = user_db.get(username)
            if not user_data:
                raise Exception('User "%s" cannot be found' % (username))

            user = User(user_data)
            updated = False
            if new_data.get('role') != user_data.get('role'):
                # Role change
                if changer.get_role() < user.get_role():
                    changer_role = str(changer.get_role())
                    user_role = str(user.get_role())
                    raise Exception('User with role "%s" is not allowed to change role '
                                    'of user with "%s" role' % (changer_role, user_role))

                new_role = Role[new_data['role']]
                if changer.get_role() < new_role:
                    changer_role = str(changer.get_role())
                    new_role = str(new_role)
                    raise Exception('User with role "%s" is not allowed to change '
                                    'role to "%s" role' % (changer_role, new_role))

                user.set_role(new_role)
                user.update_history('role change', str(new_role))
                updated = True

            old_pwgs = sorted(list(set(user_data.get('pwg'))))
            new_pwgs = sorted(list(set(pwg.upper() for pwg in new_data.get('pwg'))))
            if old_pwgs != new_pwgs:
                # PWG change
                all_pwgs = Settings.get('pwg')
                invalid_pwgs = set(new_pwgs) - set(all_pwgs)
                if invalid_pwgs:
                    raise Exception('Invalid PWGs: %s' % (','.join(invalid_pwgs)))

                user.set_pwgs(new_pwgs)
                added_pwgs = ['+%s' % (pwg) for pwg in (set(new_pwgs) - set(old_pwgs))]
                removed_pwgs = ['-%s' % (pwg) for pwg in (set(old_pwgs) - set(new_pwgs))]
                user.update_history('pwg change', ','.join(added_pwgs + removed_pwgs))
                updated = True

            if updated:
                user.save()

        return {'results': user.user_info}


class GetUserInfo(RESTResource):

    def get(self):
        """
        Retrieve the username, user name, role as string and allowed PWGS of the
        current user
        """
        user = User()
        return {'username': user.get_username(),
                'user_name': user.get_user_name(),
                'role': str(user.get_role()),
                'pwgs': user.get_user_pwgs()}


class AddCurrentUser(RESTResource):

    def post(self):
        """
        Add the current user to the user database if user is not already in db
        """
        user_db = Database('users')
        user = User()
        username = user.get_username()
        if user_db.document_exists(username):
            return {'results': False,
                    'message': 'User "%s" is already in the database' % (username)}

        user.set_role(Role.USER)
        user.update_history('created')
        # save to db
        if not user.save():
            self.logger.error('Could not save user %s to database', username)
            return {'results': False,
                    'message': 'Error adding %s to the database' % (username)}

        return {'results': True}
