from rest_api.RestAPIMethod import (CreateRESTResource,
                                    DeleteRESTResource,
                                    GetEditableRESTResource,
                                    GetRESTResource,
                                    UpdateRESTResource,
                                    RESTResource)
from json_layer.chained_campaign import ChainedCampaign
from json_layer.user import Role
from tools.exceptions import BadAttributeException, InvalidActionException


class CreateChainedCampaign(CreateRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def put(self, data):
        """
        Create a chained campaign with the provided content
        Required attribute - a list of flows and campaigns as 'campaigns'
        """
        campaigns = data.get('campaigns')
        if not campaigns:
            return {'results': False,
                    'message': 'Chained campaign must have at least one campaign'}

        prepid = 'chain'
        for i, (campaign, flow) in enumerate(campaigns):
            if i == 0:
                prepid += '_%s' % (campaign)
            else:
                prepid += '_%s' % (flow)

        data['prepid'] = prepid
        return self.create_object(data, ChainedCampaign)


    def before_create(self, obj):
        # Check if all chains and campaigns exist
        from json_layer.campaign import Campaign
        from json_layer.flow import Flow
        campaigns = obj.get('campaigns')
        used_ids = set()
        for i, (campaign_id, flow_id) in enumerate(campaigns):
            if campaign_id in used_ids or flow_id in used_ids:
                raise BadAttributeException(f'Chain contain duplicate flows or campaigns')

            if i > 0:
                used_ids.add(flow_id)
                flow = Flow.fetch(flow_id)
                if not flow:
                    raise BadAttributeException(f'Flow {flow_id} could not be found')

                next_campaign = flow.get('next_campaign')
                if not next_campaign:
                    raise BadAttributeException(f'Flow {flow_id} does not have next campaign')

                if next_campaign != campaign_id:
                    raise BadAttributeException(f'{flow_id} next campaign is not "{campaign_id}"')

            used_ids.add(campaign_id)
            campaign = Campaign.fetch(campaign_id)
            if not campaign:
                raise BadAttributeException(f'Campaign {campaign_id} could not be found')


class UpdateChainedCampaign(UpdateRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Update a chained campaign with the provided json content
        Required attributes - prepid and revision
        """
        return self.update_object(data, ChainedCampaign)


class DeleteChainedCampaign(DeleteRESTResource):

    def delete_check(self, obj):
        prepid = obj.get('prepid')
        # Check chained requests created in chained campaign
        from json_layer.chained_request import ChainedRequest
        chained_request_db =ChainedRequest.get_database()
        chained_requests = chained_request_db.query_view('member_of_campaign', prepid, limit=1)
        if chained_requests:
            raise InvalidActionException(f'Chained campaign has chained requests')

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def delete(self, prepid):
        """
        Delete a chained campaign
        """
        return self.delete_object(prepid, ChainedCampaign)


class GetChainedCampaign(GetRESTResource):
    """
    Endpoing for retrieving a chained campaign
    """
    object_class = ChainedCampaign


class GetEditableChainedCampaign(GetEditableRESTResource):
    """
    Endpoing for retrieving a chained campaign and it's editing info
    """
    object_class = ChainedCampaign
