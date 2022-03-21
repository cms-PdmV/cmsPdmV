from rest_api.api_base import RESTResource, DeleteRESTResource
from json_layer.user import Role, User
from json_layer.invalidation import Invalidation
from tools.settings import Settings


class GetInvalidation(RESTResource):

    def get(self, prepid):
        """
        Retrieve the invalidation for given id
        """
        return {'results': Invalidation.get_database().get(prepid)}


class DeleteInvalidation(DeleteRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_EXPERT)
    def delete(self, prepid):
        """
        Delete an invalidation
        """
        return self.delete_object(prepid, Invalidation)


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
    def get(self, prepid):
        """
        Acknowledge the invalidation and change it's status
        Legacy API, new API is POST
        """
        if not self.allowed_to_acknowledge():
            return {'results': False,
                    'prepid': prepid,
                    'message': 'User not allowed to acknowledge'}

        invalidation = Invalidation.fetch(prepid)
        if not invalidation:
            return {'results': False,
                    'prepid': prepid,
                    'message': '%s could not be found' % (prepid)}

        invalidation.set_acknowledged()
        if not invalidation.save():
            return {'results': False,
                    'prepid': prepid,
                    'message': 'Could not save %s to database' % (prepid)}

        return {'results': True,
                'prepid': prepid}

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
