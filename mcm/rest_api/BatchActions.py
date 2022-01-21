from rest_api.RestAPIMethod import RESTResource, DeleteRESTResource
from json_layer.batch import Batch
from json_layer.user import Role


class GetBatch(RESTResource):

    def get(self, prepid):
        """
        Retrieve the batch for given id
        """
        return {'results': Batch.get_database().get(prepid)}


class DeleteBatch(DeleteRESTResource):

    @RESTResource.ensure_role(Role.ADMINISTRATOR)
    def delete(self, prepid):
        """
        Delete a batch
        """
        return self.delete_object(prepid, Batch)


class AnnounceBatch(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Annouce a given batches
        """
        def announce(batch):
            batch.announce()

        return self.do_multiple_items(data['prepid'], Batch, announce)
