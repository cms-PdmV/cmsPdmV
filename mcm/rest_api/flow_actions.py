from couchdb_layer.mcm_database import Database
from rest_api.api_base import CloneRESTResource, CreateRESTResource, DeleteRESTResource, GetEditableRESTResource, GetRESTResource, GetUniqueValuesRESTResource, RESTResource, UpdateRESTResource
from model.campaign import Campaign
from model.flow import Flow
from model.user import Role
from tools.exceptions import BadAttributeException


class FlowRESTResource(RESTResource):

    def update_derived_objects(self, old_flow, new_flow):
        """
        Update campaigns' "Next" attribute
        """
        old_allowed_ids = set(old_flow.get('allowed_campaigns') if old_flow else [])
        old_next_id = old_flow.get('next_campaign') if old_flow else None
        new_allowed_ids = set(new_flow.get('allowed_campaigns') if new_flow else [])
        new_next_id = new_flow.get('next_campaign') if new_flow else None

        if old_next_id == new_next_id and old_allowed_ids == new_allowed_ids:
            # Nothing changed
            return

        # If next campaign is different, remove from all old allowed, add to all
        # new allowed campaigns
        # If next campaign is the same, remove from removed allowed and add to
        # added allowed
        next_changed = old_next_id != new_next_id
        remove_from = old_allowed_ids - (set() if next_changed else new_allowed_ids)
        add_to = new_allowed_ids - (set() if next_changed else old_allowed_ids)
        # Remove
        if old_next_id:
            for old_allowed_id in remove_from:
                campaign = Campaign.fetch(old_allowed_id)
                next_campaigns = campaign.get('next')
                if old_next_id in next_campaigns:
                    next_campaigns.remove(old_next_id)
                    campaign.set('next', next_campaigns)
                    campaign.save()

        # Add
        if new_next_id:
            for new_allowed_id in add_to:
                campaign = Campaign.fetch(new_allowed_id)
                next_campaigns = campaign.get('next')
                if new_next_id not in next_campaigns:
                    next_campaigns.append(new_next_id)
                    next_campaigns.sort()
                    campaign.set('next', next_campaigns)
                    campaign.save()

    def set_default_request_parameters(self, flow):
        """
        Add a skeleton of the sequences of the next campaign
        """
        next_campaign_id = flow.get('next_campaign')
        if not next_campaign_id:
            return True

        parameters = flow.get('request_parameters')
        if 'sequences' not in parameters:
            parameters['sequences'] = []

        campaign_db = Database('campaigns')
        next_campaign = campaign_db.get(next_campaign_id)
        sequence_name = parameters.get('sequences_name', 'default')
        campaign_sequences = next_campaign['sequences']
        if sequence_name not in campaign_sequences:
            raise BadAttributeException(f'{sequence_name} is not defined in "{next_campaign_id}"')

        campaign_sequences = campaign_sequences[sequence_name]
        if len(parameters['sequences']) > len(campaign_sequences):
            raise BadAttributeException(f'Flow has more sequences than "{next_campaign_id}"')

        while len(parameters['sequences']) < len(campaign_sequences):
            parameters['sequences'].append({})

        flow.set('request_parameters', parameters)

    def check_campaigns(self, flow):
        """
        Check if flow's allowed and next campaigns exist
        Check if next is not in allowed campaigns
        Check if energy is the same among allowed and next campaigns
        """
        allowed_campaign_ids = flow.get('allowed_campaigns')
        next_campaign_id = flow.get('next_campaign')
        if next_campaign_id in allowed_campaign_ids:
            raise BadAttributeException('Next campaign cannot be among allowed campaigns')

        campaign_db = Database('campaigns')
        if next_campaign_id:
            next_campaign = campaign_db.get(next_campaign_id)
            if not next_campaign:
                raise BadAttributeException(f'Next campaign "{next_campaign_id}" does not exist')

        for allowed_campaign_id in allowed_campaign_ids:
            allowed_campaign = campaign_db.get(allowed_campaign_id)
            if not allowed_campaign:
                raise BadAttributeException(f'Allowed campaign "{allowed_campaign}" does not exist')

            if allowed_campaign['energy'] != next_campaign['energy']:
                raise BadAttributeException(f'"{allowed_campaign_id}" energy is not '
                                            f'equal to "{next_campaign_id}" energy')


class CreateFlow(CreateRESTResource, FlowRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def put(self, data):
        """
        Create a flow with the provided json content
        """
        return self.create_object(data, Flow)

    def before_create(self, obj):
        # Check if allowed and next campaigns exist
        self.check_campaigns(obj)
        # Adjust the request parameters based on next campaign
        self.set_default_request_parameters(obj)

    def after_create(self, obj):
        # Update relevant campaigns' "Next" parameter
        self.update_derived_objects(None, obj)


class UpdateFlow(UpdateRESTResource, FlowRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Update a flow with the provided json content
        Required attributes - prepid and revision
        """
        return self.update_object(data, Flow)

    def before_update(self, old_obj, new_obj):
        prepid = new_obj.get('prepid')
        # Check if there are submitted requests when changing processing string
        old_ps = old_obj.get_attribute('request_parameters').get('process_string', None)
        new_ps = new_obj.get_attribute('request_parameters').get('process_string', None)
        if old_ps != new_ps:
            request_db = Database('requests')
            requests = request_db.search({'status': 'submitted', 'flown_with': prepid}, limit=1)
            if requests:
                raise BadAttributeException('Cannot change process string because there are '
                                            f'"submitted" requests that are flown with "{prepid}"')

        # Check if allowed and next campaigns exist
        self.check_campaigns(new_obj)
        # Adjust the request parameters based on next campaign
        self.set_default_request_parameters(new_obj)

        # Check if allowed campaign change is allowed
        old_allowed_campaigns = old_obj.get('allowed_campaigns')
        new_allowed_campaigns = new_obj.get('allowed_campaigns')
        removed_campaigns = set(old_allowed_campaigns) - set(new_allowed_campaigns)
        if removed_campaigns:
            chained_campaign_db = Database('chained_campaigns')
            # Check if there are chained campaigns that are made with this flow
            # and was using the removed campaigns
            # Contains this flow AND any removed campaign
            chained_campaign_query = {'contains': prepid,
                                      'contains_': list(removed_campaigns)}
            chained_campaigns = chained_campaign_db.search(chained_campaign_query, limit=1)
            if chained_campaigns:
                raise BadAttributeException(f'Campaign "{removed_campaigns[0]}" cannot be removed '
                                            'because there are chained campaigns using it')

        new_next_campaign = new_obj.get('next_campaign')
        old_next_campaign = old_obj.get('next_campaign')
        if old_next_campaign and old_next_campaign != new_next_campaign:
            chained_campaign_db = Database('chained_campaigns')
            # Check if there are chained campaigns that are made with this flow
            # and was using the changed next campaign
            # Contains this flow AND that next campaign
            chained_campaign_query = {'contains': prepid,
                                      'contains_': old_next_campaign}
            chained_campaigns = chained_campaign_db.search(chained_campaign_query, limit=1)
            if chained_campaigns:
                raise BadAttributeException(f'Campaign "{old_next_campaign}" cannot be removed '
                                            'because there are chained campaigns using it')

    def after_update(self, old_obj, new_obj, changes):
        # Update relevant campaigns' "Next" parameter
        self.update_derived_objects(old_obj, new_obj)


class DeleteFlow(FlowRESTResource, DeleteRESTResource):

    def delete_check(self, obj):
        flow_id = obj.get('prepid')
        # Check chained campaigns...
        chained_campaign_db = Database('chained_campaigns')
        chained_campaigns = chained_campaign_db.query_view('contains', flow_id, limit=3)
        if chained_campaigns:
            chained_campaign_ids = ', '.join(x['_id'] for x in chained_campaigns)
            raise Exception('Chained campaign(s) %s have %s, delete them first' % (chained_campaign_ids,
                                                                                   flow_id))

        # Check requests...
        request_db = Database('requests')
        requests = request_db.query_view('flown_with', flow_id, limit=3)
        if requests:
            request_ids = ', '.join(x['_id'] for x in requests)
            raise Exception('Request(s) %s are flown with %s, delete them first' % (request_ids,
                                                                                    flow_id))
        self.flow = obj

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def delete(self, prepid):
        """
        Delete a flow
        """
        self.flow = None
        results = self.delete_object(prepid, Flow)
        if results.get('results'):
            # Update relevant campaigns' "Next" parameter
            self.update_derived_objects(self.flow, None)

        return results


class GetFlow(GetRESTResource):
    """
    Endpoing for retrieving a flow
    """
    object_class = Flow


class GetEditableFlow(GetEditableRESTResource):
    """
    Endpoing for retrieving a flow and it's editing info
    """
    object_class = Flow


class GetUniqueFlowValues(GetUniqueValuesRESTResource):
    """
    Endpoint for getting unique values of flow attributes
    """
    object_class = Flow


class CloneFlow(CloneRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def put(self, data):
        """
        Make a clone of a flow
        """
        return self.clone_object(data, Flow)


class ToggleFlowType(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Move the given flow(s) id to the next type
        """
        def toggle(flow):
            flow.toggle_type()

        return self.do_multiple_items(data['prepid'], Flow, toggle)
