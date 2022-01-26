import time
import traceback

from couchdb_layer.mcm_database import database as Database
from rest_api.RestAPIMethod import DeleteRESTResource, RESTResource
from json_layer.campaign import Campaign
from json_layer.request import Request
from json_layer.sequence import Sequence
from json_layer.chained_campaign import ChainedCampaign
from json_layer.user import Role


class CreateCampaign(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def put(self, data):
        """
        Create a campaign with the provided json content
        """
        campaign = Campaign(data)
        prepid = campaign.get_attribute('prepid')
        if Campaign.fetch(prepid):
            self.logger.error('Campaign "%s" already exists', prepid)
            return {'results': False,
                    'message': 'Campaign "%s" already exists' % (prepid)}

        # Validate
        campaign.validate()
        # Ensure schema of sequences
        sequences = campaign.get('sequences')
        sequences = {name: [Sequence(s).json() for s in seqs] for name, seqs in sequences.items()}
        campaign.set_attribute('sequences', sequences)
        campaign.set_attribute('_id', prepid)
        campaign.update_history({'action': 'created'})

        # Save to DB
        if not campaign.save():
            return {'results': False,
                    'message': 'Could not save %s to the database' % (prepid)}

        root = campaign.get_attribute('root')
        # If campaign is maybe root or root, create dedicated chained campaign
        if root in (-1, 0):
            chained_campaign_db = Database('chained_campaigns')
            chained_campaign = ChainedCampaign({'prepid': 'chain_%s' % (prepid),
                                                '_id': 'chain_%s' % (prepid),
                                                'campaigns': [[prepid, None]]})
            chained_campaign_db.save(chained_campaign.json())

        return {'results': True, 'prepid': prepid}


class UpdateCampaign(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Update a campaign with the provided json content
        """
        prepid = data.get('prepid', data.get('_id'))
        if not prepid:
            return {'results': False,
                    'message': 'Missing prepid in submitted data'}

        old_campaign = Campaign.fetch(prepid)
        if not old_campaign:
            return {"results": False,
                    'message': 'Object "%s" does not exist' % (prepid)}

        new_campaign = Campaign(data)
        if new_campaign.get('_rev') != old_campaign.get('_rev'):
            return {'results': False,
                    'message': 'Provided revision does not match revision in database'}

        # Validate
        new_campaign.validate()
        # Ensure schema of sequences
        sequences = new_campaign.get('sequences')
        sequences = {name: [Sequence(s).json() for s in seqs] for name, seqs in sequences.items()}
        new_campaign.set_attribute('sequences', sequences)
        # Difference
        difference = self.get_obj_diff(old_campaign.json(),
                                       new_campaign.json(),
                                       ('history', '_rev'))
        if not difference:
            return {'results': True}

        difference = ', '.join(difference)
        new_campaign.set('history', old_campaign.get('history'))
        new_campaign.update_history('update', difference)

        # Save to DB
        if not new_campaign.save():
            return {'results': False,
                    'message': 'Could not save %s to the database' % (prepid)}

        root = new_campaign.get_attribute('root')
        # If campaign is maybe root (-1) or root (0), create dedicated chained campaign
        if root in (-1, 0):
            chained_campaign_db = Database('chained_campaigns')
            chained_campaign_id = 'chain_%s' % (prepid)
            if not chained_campaign_db.document_exists(chained_campaign_id):
                chained_campaign = ChainedCampaign({'prepid': chained_campaign_id,
                                                    '_id': chained_campaign_id,
                                                    'campaigns': [[prepid, None]]})
                chained_campaign_db.save(chained_campaign.json())

        return {'results': True, 'prepid': prepid}


class DeleteCampaign(DeleteRESTResource):

    def delete_check(self, obj):
        campaign_id = obj.get('prepid')
        # Check flows...
        flow_db = Database('flows')
        flow_allowed_campaigns = flow_db.query_view('allowed_campaigns', campaign_id, limit=3)
        if flow_allowed_campaigns:
            flow_ids = ', '.join(x['_id'] for x in flow_allowed_campaigns)
            raise Exception('Flow(s) %s have %s as allowed campaign, edit them first' % (flow_ids,
                                                                                         campaign_id))

        flow_next_campaign = flow_db.query_view('next_campaign', campaign_id, limit=3)
        if flow_next_campaign:
            flow_ids = ', '.join(x['_id'] for x in flow_next_campaign)
            raise Exception('Flow(s) %s have %s as next campaign, edit them first' % (flow_ids,
                                                                                      campaign_id))

        # Check chained campaigns...
        chained_campaign_db = Database('chained_campaigns')
        chained_campaigns = chained_campaign_db.query_view('campaign', campaign_id, limit=3)
        if chained_campaigns:
            chained_campaign_ids = ', '.join(x['_id'] for x in chained_campaigns)
            raise Exception('Chained campaign(s) %s have %s, delete them first' % (chained_campaign_ids,
                                                                                   campaign_id))

        # Check requests...
        request_db = Database('requests')
        requests = request_db.query_view('member_of_campaign', campaign_id, limit=3)
        if requests:
            request_ids = ', '.join(x['_id'] for x in requests)
            raise Exception('Request(s) %s are member of %s, delete them first' % (request_ids,
                                                                                   campaign_id))

        # Get all campaigns that contain this campaign as "next"
        campaign_db = Campaign.get_database()
        campaigns_with_next = campaign_db.query_view('next', campaign_id,  page_num=-1)
        for campaign_next in campaigns_with_next:
            if campaign_id in campaign_next['next']:
                campaign_next['next'].remove(campaign_id)
                campaign_db.update(campaign_next)

        return super().delete_check(obj)

    @RESTResource.ensure_role(Role.PRODUCTION_EXPERT)
    def delete(self, prepid):
        """
        Delete a campaign
        """
        return self.delete_object(prepid, Campaign)


class GetCampaign(RESTResource):

    def get(self, prepid):
        """
        Retrieve the campaign for given id
        """
        return {'results': Campaign.get_database().get(prepid)}


class ToggleCampaignStatus(RESTResource):

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

    def get(self, campaign_id):
        """
        Retrieve the list of cmsDriver commands for a given campaign id
        """
        campaign_db = Database('campaigns')
        if not campaign_db.document_exists(campaign_id):
            self.logger.error('Campaign %s does not exist', campaign_id)
            return {'results': False,
                    'message': 'Campaign "%s" does not exist' % (campaign_id)}

        campaign = Campaign(campaign_db.get(campaign_id))
        return {'results': campaign.get_cmsdrivers()}


class InspectCampaigns(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_EXPERT)
    def get(self, campaign_id):
        """
        Inspect all requests in given campaign(s)
        """
        # force pretty output in browser for multiple lines
        self.representations = {'text/plain': self.output_text}
        # Make a list of IDs, although usually a single ID is expected
        campaign_ids = list(set(campaign_id.split(',')))
        from random import shuffle
        shuffle(campaign_ids)
        import flask
        return flask.Response(flask.stream_with_context(self.inspect(campaign_ids)))

    def inspect(self, campaign_ids):
        request_db = Database('requests')
        for campaign_id in campaign_ids:
            try:
                self.logger.info('Starting campaign inspect of %s', campaign_id)
                yield 'Starting campaign inspect of %s\n' % (campaign_id)
                query = {'member_of_campaign': campaign_id,
                         'status': ['submitted', 'approved']}
                # Do another loop over the requests themselves
                page = 0
                requests = [{}]
                while len(requests) > 0:
                    requests = request_db.search(query, page=page, limit=200)
                    self.logger.info('Inspecting %s requests on page %s', len(requests), page)
                    yield 'Inspecting %s requests on page %s\n' % (len(requests), page)
                    for request_json in requests:
                        prepid = request_json['prepid']
                        self.logger.info('Inspecting request %s', prepid)
                        yield 'Inspecting request %s\n' % (prepid)
                        request = Request(request_json)
                        inspect_result = request.inspect()
                        if not inspect_result.get('results'):
                            message = inspect_result.get('message', '?')
                            self.logger.info('Failure: %s', message)
                            yield 'Failure: %s\n' % (message)
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
