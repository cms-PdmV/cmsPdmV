from rest_api.api_base import GetRESTResource, RESTResource, DeleteRESTResource
from json_layer.batch import Batch
from json_layer.user import Role


class GetBatch(GetRESTResource):
    """
    Endpoing for retrieving a batch
    """
    object_class = Batch


class DeleteBatch(DeleteRESTResource):
    """
    Endpoint for deleting a batch
    """

    @RESTResource.ensure_role(Role.ADMINISTRATOR)
    def delete(self, prepid):
        """
        Delete a batch
        """
        return self.delete_object(prepid, Batch)


class AnnounceBatch(RESTResource):
    """
    Endpoint for announcing batches
    """

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Annouce a given batch or batches
        """
        def announce(batch):
            batch.announce()

        return self.do_multiple_items(data['prepid'], Batch, announce)
