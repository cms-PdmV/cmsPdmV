import flask
import time
import traceback
import json

from couchdb_layer.mcm_database import database as Database
from RestAPIMethod import RESTResource
from json_layer.campaign import campaign as Campaign
from json_layer.request import request as Request
from json_layer.sequence import sequence as Sequence
from json_layer.chained_campaign import chained_campaign as ChainedCampaign
from tools.user_management import access_rights
import tools.settings as settings


class CreateCampaign(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Create a campaign with the provided json content
        """
        data = json.loads(flask.request.data)
        campaign_db = Database('campaigns')
        campaign = Campaign(json_input=data)
        prepid = campaign.get_attribute('prepid')
        if not prepid:
            self.logger.error('Invalid prepid "%s"', prepid)
            return {'results': False,
                    'message': 'Invalid prepid "%s"' % (prepid)}

        if not self.fullmatch(Campaign._prepid_pattern, prepid):
            self.logger.error('Invalid campaign name %s', prepid)
            return {'results': False,
                    'message': 'Invalid campaign name "%s"' % (prepid)}

        if campaign_db.document_exists(prepid):
            self.logger.error('Campaign "%s" already exists', prepid)
            return {'results': False,
                    'message': 'Campaign "%s" already exists' % (prepid)}

        # Ensure schema of sequences
        sequences = campaign.get_attribute('sequences')
        for sequence in sequences:
            for label in sequence:
                sequence[label] = Sequence(sequence[label]).json()

        campaign.set_attribute('sequences', sequences)

        campaign.set_attribute('_id', prepid)
        campaign.update_history({'action': 'created'})
        # Save to DB
        if not campaign_db.save(campaign.json()):
            self.logger.error('Could not save campaign %s to database', prepid)
            return {'results': False,
                    'message': 'Could not save campaign %s to database' % (prepid)}

        root = campaign.get_attribute('root')
        # If campaign is maybe root or root, create dedicated chained campaign
        if root in (-1, 0):
            chained_campaign_db = Database('chained_campaigns')
            chained_campaign = ChainedCampaign({'prepid': 'chain_%s' % (prepid),
                                                '_id': 'chain_%s' % (prepid)})
            chained_campaign.add_campaign(prepid)
            chained_campaign_db.save(chained_campaign.json())

        return {'results': True}


class UpdateCampaign(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Update a campaign with the provided json content
        """
        data = json.loads(flask.request.data)
        if '_rev' not in data:
            return {'results': False,
                    'message': 'No revision provided'}

        campaign_db = Database('campaigns')
        campaign = Campaign(json_input=data)
        prepid = campaign.get_attribute('prepid')
        if not prepid:
            self.logger.error('Invalid prepid "%s"', prepid)
            return {'results': False,
                    'message': 'Invalid prepid "%s"' % (prepid)}

        if not campaign_db.document_exists(prepid):
            self.logger.error('Cannot update, %s does not exist', prepid)
            return {'results': False,
                    'message': 'Cannot update, "%s" does not exist' % (prepid)}

        # Ensure schema of sequences
        sequences = campaign.get_attribute('sequences')
        for sequence in sequences:
            for label in sequence:
                sequence[label] = Sequence(sequence[label]).json()

        campaign.set_attribute('sequences', sequences)

        previous_version = Campaign(json_input=campaign_db.get(prepid))
        difference = self.get_obj_diff(previous_version.json(),
                                       campaign.json(),
                                       ('history', '_rev'))
        if not difference:
            return {'results': True}

        difference = ', '.join(difference)
        campaign.update_history({'action': 'update', 'step': difference})

        # Save to DB
        if not campaign_db.update(campaign.json()):
            self.logger.error('Could not save campaign %s to database', prepid)
            return {'results': False,
                    'message': 'Could not save campaign %s to database' % (prepid)}

        root = campaign.get_attribute('root')
        # If campaign is maybe root (-1) or root (0), create dedicated chained campaign
        if root in (-1, 0):
            chained_campaign_db = Database('chained_campaigns')
            chained_campaign_id = 'chain_%s' % (prepid)
            if not chained_campaign_db.document_exists(chained_campaign_id):
                chained_campaign = ChainedCampaign({'prepid': chained_campaign_id,
                                                    '_id': chained_campaign_id})
                chained_campaign.add_campaign(prepid)
                chained_campaign_db.save(chained_campaign.json())

        return {'results': True}


class DeleteCampaign(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def delete(self, campaign_id):
        """
        Delete a campaign
        """
        campaign_db = Database('campaigns')
        if not campaign_db.document_exists(campaign_id):
            self.logger.error('Cannot delete, %s does not exist', campaign_id)
            return {'results': False,
                    'message': 'Cannot delete, %s does not exist' % (campaign_id)}

        # Check flows...
        flow_db = Database('flows')
        flow_allowed_campaigns = flow_db.query_view('allowed_campaigns', campaign_id, limit=3)
        if flow_allowed_campaigns:
            flow_ids = ', '.join(x['_id'] for x in flow_allowed_campaigns)
            message = 'Flow(s) %s have %s as allowed campaign, edit them first' % (flow_ids,
                                                                                   campaign_id)
            self.logger.error(message)
            return {'results': False,
                    'message': message}

        flow_next_campaign = flow_db.query_view('next_campaign', campaign_id, limit=3)
        if flow_next_campaign:
            flow_ids = ', '.join(x['_id'] for x in flow_next_campaign)
            message = 'Flow(s) %s have %s as next campaign, edit them first' % (flow_ids,
                                                                                campaign_id)
            self.logger.error(message)
            return {'results': False,
                    'message': message}

        # Check chained campaigns...
        chained_campaign_db = Database('chained_campaigns')
        chained_campaigns = chained_campaign_db.query_view('campaign', campaign_id, limit=3)
        if chained_campaigns:
            chained_campaign_ids = ', '.join(x['_id'] for x in chained_campaigns)
            message = 'Chained campaign(s) %s have %s, delete them first' % (chained_campaign_ids,
                                                                             campaign_id)
            self.logger.error(message)
            return {'results': False,
                    'message': message}

        # Check requests...
        request_db = Database('requests')
        requests = request_db.query_view('member_of_campaign', campaign_id, limit=3)
        if requests:
            request_ids = ', '.join(x['_id'] for x in requests)
            message = 'Request(s) %s are member of %s, delete them first' % (request_ids,
                                                                             campaign_id)
            self.logger.error(message)
            return {'results': False,
                    'message': message}

        # Get all campaigns that contain this campaign as "next"
        campaigns_with_next = campaign_db.query_view('next', campaign_id,  page_num=-1)
        for campaign_next in campaigns_with_next:
            if campaign_id in campaign_next['next']:
                campaign_next['next'].remove(campaign_id)
                campaign_db.update(campaign_next)

        # Delete to DB
        if not campaign_db.delete(campaign_id):
            self.logger.error('Could not delete campaign %s from database', campaign_id)
            return {'results': False,
                    'message': 'Could not delete campaign %s from database' % (campaign_id)}

        return {'results': True}


class GetCampaign(RESTResource):

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, campaign_id):
        """
        Retrieve the campaign for given id
        """
        campaign_db = Database('campaigns')
        return {'results': campaign_db.get(prepid=campaign_id)}


class ToggleCampaignStatus(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, campaign_id):
        """
        Toggle campaign status
        """
        campaign_db = Database('campaigns')
        if not campaign_db.document_exists(campaign_id):
            self.logger.error('Campaign %s does not exist', campaign_id)
            return {'results': False,
                    'message': 'Campaign "%s" does not exist' % (campaign_id)}

        campaign = Campaign(json_input=campaign_db.get(campaign_id))
        try:
            campaign.toggle_status()
        except Exception as ex:
            return {'results': False,
                    'message': str(ex)}

        if not campaign.save():
            self.logger.error('Could not save campaign "%s" to database', campaign_id)
            return {'results': False,
                    'message': 'Could not save campaign "%s" to database' % (campaign_id)}

        return {'results': True}


class GetCmsDriverForCampaign(RESTResource):

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, campaign_id):
        """
        Retrieve the list of cmsDriver commands for a given campaign id
        """
        campaign_db = Database('campaigns')
        if not campaign_db.document_exists(campaign_id):
            self.logger.error('Campaign %s does not exist', campaign_id)
            return {'results': False,
                    'message': 'Campaign "%s" does not exist' % (campaign_id)}

        campaign = Campaign(json_input=campaign_db.get(campaign_id))
        return {'results': campaign.build_cmsDrivers()}


class InspectCampaigns(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

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
