from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database as Database
from json_layer.user import Role, User
from json_layer.invalidation import Invalidation
from tools.settings import Settings


class GetInvalidation(RESTResource):

    def get(self, invalidation_id):
        """
        Retrieve the invalidation for given id
        """
        invalidation_db = Database('invalidations')
        return {'results': invalidation_db.get(invalidation_id)}


class DeleteInvalidation(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_EXPERT)
    def delete(self, invalidation_id):
        """
        Delete an invalidation
        """
        invalidation_db = Database('invalidations')
        if not invalidation_db.document_exists(invalidation_id):
            self.logger.error('%s could not be found', invalidation_id)
            return {'results': False,
                    'prepid': invalidation_id,
                    'message': '%s could not be found' % (invalidation_id)}

        if not invalidation_db.delete(invalidation_id):
            self.logger.error('Could not delete %s from database', invalidation_id)
            return {'results': False,
                    'prepid': invalidation_id,
                    'message': 'Could not delete %s from database' % (invalidation_id)}

        return {'results': True, 'prepid': invalidation_id}


class AnnounceInvalidation(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        def announce(invalidation):
            if invalidation.get('status') != 'new':
                raise Exception('Only new invalidations can be announced')

            invalidation.set_announced()

        return self.do_multiple_items(data['prepid'], Invalidation, announce)


class AcknowledgeInvalidation(RESTResource):

    def allowed_to_acknowledge(self):
        """
        Return whether current user is allowed to acknowledge the invalidation
        """
        user = User()
        if user.get_role() >= Role.ADMINISTRATOR:
            return True

        allowed_users = Settings.get('allowed_to_acknowledge')
        return user.get_username() in allowed_users

    @RESTResource.ensure_role(Role.USER)
    def get(self, invalidation_id):
        """
        Acknowledge the invalidation and change it's status
        Legacy API, new API is POST
        """
        if not self.allowed_to_acknowledge():
            return {'results': False,
                    'prepid': invalidation_id,
                    'message': 'User not allowed to acknowledge'}

        invalidation = Invalidation.fetch(invalidation_id)
        if not invalidation:
            return {'results': False,
                    'prepid': invalidation_id,
                    'message': '%s could not be found' % (invalidation_id)}

        invalidation.set_acknowledged()
        if not invalidation.save():
            return {'results': False,
                    'prepid': invalidation_id,
                    'message': 'Could not save %s to database' % (invalidation_id)}

        return {'results': False,
                'prepid': invalidation_id}

    @RESTResource.ensure_role(Role.USER)
    @RESTResource.request_with_json
    def post(self, data):
        def acknowledge(invalidation):
            if not self.allowed_to_acknowledge():
                raise Exception('User not allowed to acknowledge')

            if invalidation.get('status') != 'announced':
                raise Exception('Only announced invalidations can be acknowledged')

            invalidation.set_acknowledged()

        return self.do_multiple_items(data['prepid'], Invalidation, acknowledge)


class HoldInvalidation(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        def hold(invalidation):
            if invalidation.get('status') != 'new':
                raise Exception('Only new invalidations can be put on hold')

            invalidation.set_hold()

        return self.do_multiple_items(data['prepid'], Invalidation, hold)


class ResetInvalidation(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        def reset(invalidation):
            if invalidation.get('status') not in ('hold', 'announced'):
                raise Exception('Only announced or invalidations on hold can be reset')

            invalidation.set_new()

        return self.do_multiple_items(data['prepid'], Invalidation, reset)
