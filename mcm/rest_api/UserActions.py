from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database as Database
from tools.exceptions import BadAttributeException, NotFoundException
from tools.locker import Locker
from tools.settings import Settings
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
    @RESTResource.request_with_json
    def post(self, data):
        """
        Save the information for given user
        Users can't change role of users with higher role than theirs
        e.g. PRODUCTION_MANAGER can't touch PRODUCTION_EXPERT and ADMINISTRATOR
        Users can't change role to higher than theirs
        e.g. PRODUCTION_MANAGER can set roles only up to PRODUCTION_MANAGER
        """

        username = data.get('username', data.get('_id'))
        if not username:
            raise BadAttributeException('Missing "username" attribute')

        changer = User()
        with Locker().lock(username):
            old_user = User.fetch(username, cache=False)
            if not old_user:
                raise NotFoundException(username)

            self.logger.info('Updating user "%s"', username)
            new_user = User(data)
            new_user.get('_rev')
            old_user.get('_rev')
            if new_user.get('_rev') != old_user.get('_rev'):
                raise BadAttributeException('Provided revision does not match revision in database')

            # Unique pwgs
            all_pwgs = Settings.get('pwg')
            pwgs = new_user.get_user_info()['pwg']
            pwgs = sorted(list(set(p.upper() for p in pwgs)))
            invalid_pwgs = sorted(list(set(pwgs) - set(all_pwgs)))
            if invalid_pwgs:
                raise BadAttributeException(f'Invalid PWGs: {",".join(invalid_pwgs)}')

            # Difference
            old_role = old_user.get_role()
            new_role = new_user.get_role()
            difference = self.get_obj_diff(old_user.get_user_info(),
                                           new_user.get_user_info(),
                                           ('history', '_rev', 'role'))
            if not difference and old_role == new_role:
                self.logger.info('No updates for %s', username)
                return {'results': True, 'prepid': username}

            difference = ', '.join(difference)
            self.logger.info('Update difference for %s: %s', username, difference)
            new_user.set('history', old_user.get('history'))
            new_user.update_history('update', difference)

            if old_role != new_role:
                changer_role_str = str(changer.get_role())
                old_role_str = str(old_role)
                new_role_str = str(new_role)
                # Role change
                if changer.get_role() < old_role:
                    raise Exception(f'User with role "{changer_role_str}" is not allowed to '
                                    f'change role of user with "{old_role_str}" role')

                if changer.get_role() < new_role:
                    raise Exception(f'User with role "{changer_role_str}" is not allowed to '
                                    f'change role to "{new_role_str}"')

                new_user.update_history('role change', new_role_str)

            new_user.save()

        return {'results': True, 'message': ''}


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


class GetEditableUser(RESTResource):
    """
    Endpoing for retrieving a user and it's editing info
    """

    def get(self, prepid):
        """
        Retrieve the user and it's editing info for given id
        """
        user = User.fetch(prepid)
        if not user:
            raise NotFoundException(prepid)

        return {'results': {'object': user.get_user_info(),
                            'editing_info': user.get_editing_info()}}
