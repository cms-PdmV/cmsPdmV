import time
import traceback
import flask
from couchdb_layer.mcm_database import Database
from rest_api.RestAPIMethod import (CloneRESTResource, CreateRESTResource,
                                    GetRESTResource,
                                    UpdateRESTResource,
                                    DeleteRESTResource,
                                    GetEditableRESTResource,
                                    GetUniqueValuesRESTResource,
                                    RESTResource)
from json_layer.campaign import Campaign
from json_layer.request import Request
from json_layer.sequence import Sequence
from json_layer.chained_campaign import ChainedCampaign
from json_layer.user import Role
from tools.exceptions import InvalidActionException, NotFoundException


class CreateCampaign(CreateRESTResource):
    """
    Endpoint for creating new campaign
    """

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def put(self, data):
        """
        Create a campaign with the provided content
        Required attribute - a unique prepid
        """
        return self.create_object(data, Campaign)

    def before_create(self, obj):
        # Ensure schema of sequences
        sequences = obj.get('sequences')
        sequences = {name: [Sequence(s).json() for s in seqs] for name, seqs in sequences.items()}
        obj.set_attribute('sequences', sequences)
        obj.set_attribute('next', [])

    def after_create(self, obj):
        prepid = obj.get('prepid')
        root = obj.get_attribute('root')
        # If campaign is maybe root (-1) or root (0), create chained campaign
        if root in (-1, 0):
            self.logger.info('Creating a new chained campaign for "%s" campaign', prepid)
            chained_campaign = ChainedCampaign({'prepid': f'chain_{prepid}',
                                                '_id': f'chain_{prepid}',
                                                'campaigns': [[prepid, None]]})
            chained_campaign.save()


class UpdateCampaign(UpdateRESTResource):
    """
    Endpoint for updating a campaign
    """

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Update a campaign with the provided content
        Required attributes - prepid and revision
        """
        return self.update_object(data, Campaign)

    def before_update(self, old_obj, new_obj):
        # Ensure schema of sequences
        sequences = new_obj.get('sequences')
        sequences = {name: [Sequence(s).json() for s in seqs] for name, seqs in sequences.items()}
        new_obj.set_attribute('sequences', sequences)

    def after_update(self, old_obj, new_obj, changes):
        prepid = new_obj.get('prepid')
        root = new_obj.get_attribute('root')
        # If campaign is maybe root (-1) or root (0), create chained campaign
        if root in (-1, 0):
            chained_campaign_db = ChainedCampaign.get_database()
            chained_campaign_id = f'chain_{prepid}'
            if not chained_campaign_db.document_exists(chained_campaign_id):
                self.logger.info('Creating a new chained campaign for "%s" campaign', prepid)
                chained_campaign = ChainedCampaign({'prepid': chained_campaign_id,
                                                    '_id': chained_campaign_id,
                                                    'campaigns': [[prepid, None]]})
                chained_campaign.save()


class DeleteCampaign(DeleteRESTResource):
    """
    Endpoint for deleting a campaign
    """

    @RESTResource.ensure_role(Role.PRODUCTION_EXPERT)
    def delete(self, prepid):
        """
        Delete a campaign
        """
        return self.delete_object(prepid, Campaign)

    def delete_check(self, obj):
        prepid = obj.get('prepid')
        # Check flows...
        flow_db = Database('flows')
        flow_allowed_campaigns = flow_db.query_view('allowed_campaigns', prepid, limit=1)
        if flow_allowed_campaigns:
            flow_id = flow_allowed_campaigns[0].get('_id')
            raise InvalidActionException(f'Flow {flow_id} has {prepid} as allowed campaign')

        flow_next_campaign = flow_db.query_view('next_campaign', prepid, limit=1)
        if flow_next_campaign:
            flow_id = flow_next_campaign[0].get('_id')
            raise InvalidActionException(f'Flow {flow_id} has {prepid} as next campaign')

        # Check chained campaigns...
        chained_campaign_db = Database('chained_campaigns')
        chained_campaigns = chained_campaign_db.query_view('campaign', prepid, limit=1)
        if chained_campaigns:
            chained_campaign_id = chained_campaigns[0].get('_id')
            raise InvalidActionException(f'Chained campaign {chained_campaign_id} has {prepid}')

        # Check requests...
        request_db = Database('requests')
        requests = request_db.query_view('member_of_campaign', prepid, limit=3)
        if requests:
            request_id = requests[0].get('_id')
            raise InvalidActionException(f'Request {request_id} is member of {prepid}')

    def after_delete(self, obj):
        # Get all campaigns that contain this campaign as "next"
        prepid = obj.get('prepid')
        campaign_db = Campaign.get_database()
        campaigns_with_next = campaign_db.query_view('next', prepid, page_num=-1)
        for campaign_next in campaigns_with_next:
            if prepid in campaign_next['next']:
                campaign_next['next'].remove(prepid)
                campaign_db.update(campaign_next)

        return super().delete_check(obj)


class GetCampaign(GetRESTResource):
    """
    Endpoing for retrieving a campaign
    """
    object_class = Campaign


class GetEditableCampaign(GetEditableRESTResource):
    """
    Endpoing for retrieving a campaign and it's editing info
    """
    object_class = Campaign


class GetUniqueCampaignValues(GetUniqueValuesRESTResource):
    """
    Endpoint for getting unique values of campaign attributes
    """
    object_class = Campaign


class CloneCampaign(CloneRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def put(self, data):
        """
        Make a clone of a campaign
        """
        return self.clone_object(data, Campaign)


class ToggleCampaignStatus(RESTResource):
    """
    Endpoint for toggling campaign status between started and stopped
    """

    @RESTResource.ensure_role(Role.PRODUCTION_EXPERT)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Toggle campaign status
        """
        def toggle(campaign):
            campaign.toggle_status()

        return self.do_multiple_items(data['prepid'], Campaign, toggle)


class GetCmsDriverForCampaign(RESTResource):
    """
    Endpoing for getting cmsDriver commands of a campaign
    """

    def get(self, prepid):
        """
        Retrieve the dictionary of cmsDriver commands of a campaign
        """
        campaign = Campaign.fetch(prepid)
        if not campaign:
            raise NotFoundException(prepid)

        return {'results': campaign.get_cmsdrivers()}


class GetDefaultCampaignSequence(RESTResource):
    """
    Endpoint for getting an empty campaign sequence
    """

    def get(self):
        """
        Get an empty campaign sequence
        """
        return {'results': Sequence.schema()}


class InspectCampaign(RESTResource):
    """
    Endpoing for inspecting all requests in the campaign
    """

    @RESTResource.ensure_role(Role.PRODUCTION_EXPERT)
    def get(self, prepid):
        """
        Inspect all requests in given campaign(s)
        """
        # Make a list of IDs, although usually a single ID is expected
        return flask.Response(flask.stream_with_context(self.inspect(prepid)))

    def inspect(self, campaign_id):
        request_db = Database('requests')
        try:
            self.logger.info('Starting campaign inspect of %s', campaign_id)
            yield f'Starting campaign inspect of {campaign_id}\n'
            query = {'member_of_campaign': campaign_id,
                     'status': ['submitted', 'approved']}
            # Do another loop over the requests themselves
            page = 0
            requests = [{}]
            while len(requests) > 0:
                requests = request_db.search(query, page=page, limit=200)
                self.logger.info('Inspecting %s requests on page %s', len(requests), page)
                yield f'Inspecting {len(requests)} requests on page {page}\n'
                for request_json in requests:
                    prepid = request_json['prepid']
                    self.logger.info('Inspecting request %s', prepid)
                    yield f'Inspecting request {prepid}\n'
                    request = Request(request_json)
                    inspect_result = request.inspect()
                    if not inspect_result.get('results'):
                        message = inspect_result.get('message', '?')
                        self.logger.info('Failure: %s', message)
                        yield f'Failure: {message}\n'
                    else:
                        self.logger.info('Success!')
                        yield 'Success!\n'

                page += 1
                time.sleep(0.1)

            time.sleep(0.2)
        except Exception as ex:
            self.logger.error('Exception while inspecting %s campaign: %s\n%s',
                                campaign_id,
                                ex,
                                traceback.format_exc())

        self.logger.info('Campaign %s inspection finished', campaign_id)
