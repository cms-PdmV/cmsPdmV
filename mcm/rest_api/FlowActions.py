import flask
import json

from couchdb_layer.mcm_database import database as Database
from RestAPIMethod import RESTResource
from json_layer.campaign import campaign as Campaign
from json_layer.flow import flow as Flow
from tools.user_management import access_rights


class FlowRESTResource(RESTResource):

    access_limit = access_rights.production_manager

    def update_derived_objects(self, old_flow, new_flow):
        """
        Update campaigns' "Next" attribute
        """
        old_allowed_ids = set(old_flow.get_attribute('allowed_campaigns') if old_flow else [])
        old_next_id = old_flow.get_attribute('next_campaign') if old_flow else None
        new_allowed_ids = set(new_flow.get_attribute('allowed_campaigns') if new_flow else [])
        new_next_id = new_flow.get_attribute('next_campaign') if new_flow else None

        if old_next_id == new_next_id and old_allowed_ids == new_allowed_ids:
            # Nothing changed
            return

        # Something changed
        campaign_db = Database('campaigns')
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
                campaign = Campaign(json_input=campaign_db.get(old_allowed_id))
                next_campaigns = campaign.get_attribute('next')
                if old_next_id in next_campaigns:
                    next_campaigns.remove(old_next_id)
                    campaign.set_attribute('next', next_campaigns)
                    campaign.save()

        # Add
        if new_next_id:
            for new_allowed_id in add_to:
                campaign = Campaign(json_input=campaign_db.get(new_allowed_id))
                next_campaigns = campaign.get_attribute('next')
                if new_next_id not in next_campaigns:
                    next_campaigns.append(new_next_id)
                    next_campaigns.sort()
                    campaign.set_attribute('next', next_campaigns)
                    campaign.save()

    def set_default_request_parameters(self, flow):
        """
        Add a skeleton of the sequences of the next campaign
        """
        next_campaign_id = flow.get_attribute('next_campaign')
        if not next_campaign_id:
            return True

        parameters = flow.get_attribute('request_parameters')
        if 'sequences' not in parameters:
            parameters['sequences'] = []

        campaign_db = Database('campaigns')
        next_campaign = campaign_db.get(next_campaign_id)
        if len(parameters['sequences']) > len(next_campaign['sequences']):
            return {'results': False,
                    'message': 'Flow has more sequences than "%s" campaign' % (next_campaign_id)}

        while len(parameters['sequences']) < len(next_campaign['sequences']):
            parameters['sequences'].append({'default': {}})

        flow.set_attribute('request_parameters', parameters)
        return True

    def check_campaigns(self, flow):
        """
        Check if flow's allowed and next campaigns exist
        Check if next is not in allowed campaigns
        Check if energy is the same among allowed and next campaigns
        """
        allowed_campaign_ids = flow.get_attribute('allowed_campaigns')
        next_campaign_id = flow.get_attribute('next_campaign')
        if next_campaign_id in allowed_campaign_ids:
            return {'results': False,
                    'message': 'Next campaign cannot be among allowed campaigns'}

        campaign_db = Database('campaigns')
        next_campaign = campaign_db.get(next_campaign_id)
        if not next_campaign:
            return {'results': False,
                    'message': 'Next campaign "%s" does not exist' % (next_campaign_id)}

        for allowed_campaign_id in allowed_campaign_ids:
            allowed_campaign = campaign_db.get(allowed_campaign_id)
            if not allowed_campaign:
                return {'results': False,
                        'message': 'Allowed campaign "%s" does not exist' % allowed_campaign}

            if allowed_campaign['energy'] != next_campaign['energy']:
                return {'results': False,
                        'message': '"%s" energy %sTeV is not equal to "%s" energy %sTeV' % (
                            allowed_campaign_id,
                            allowed_campaign['energy'],
                            next_campaign_id,
                            next_campaign['energy'],
                        )}

        return True


class CreateFlow(FlowRESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Create a flow with the provided json content
        """
        data = json.loads(flask.request.data)
        flow_db = Database('flows')
        flow = Flow(json_input=data)
        prepid = flow.get_attribute('prepid')
        if not prepid:
            self.logger.error('Invalid prepid "%s"', prepid)
            return {'results': False,
                    'message': 'Invalid prepid "%s"' % (prepid)}

        if not self.fullmatch(Flow._prepid_pattern, prepid):
            self.logger.error('Invalid flow name %s', prepid)
            return {'results': False,
                    'message': 'Invalid flow name "%s"' % (prepid)}

        if flow_db.document_exists(prepid):
            self.logger.error('Flow "%s" already exists', prepid)
            return {'results': False,
                    'message': 'Flow "%s" already exists' % (prepid)}

        # Make allowed campaigns unique
        allowed_campaigns = sorted(list(set(flow.get_attribute('allowed_campaigns'))))
        flow.set_attribute('allowed_campaigns', allowed_campaigns)
        # Check if allowed and next campaigns exist
        campaign_check = self.check_campaigns(flow)
        if campaign_check is not True:
            return campaign_check

        # Adjust the request parameters based on next campaign
        parameter_check = self.set_default_request_parameters(flow)
        if parameter_check is not True:
            return parameter_check

        flow.set_attribute('_id', prepid)
        flow.update_history({'action': 'created'})
        # Save to DB
        if not flow_db.save(flow.json()):
            self.logger.error('Could not save flow %s to database', prepid)
            return {'results': False,
                    'message': 'Could not save flow %s to database' % (prepid)}

        # Update relevant campaigns' "Next" parameter
        self.update_derived_objects(None, flow)

        return {'results': True}


class UpdateFlow(FlowRESTResource):

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

        flow_db = Database('flows')
        flow = Flow(json_input=data)
        prepid = flow.get_attribute('prepid')
        if not prepid:
            self.logger.error('Invalid prepid "%s"', prepid)
            return {'results': False,
                    'message': 'Invalid prepid "%s"' % (prepid)}

        if not flow_db.document_exists(prepid):
            self.logger.error('Cannot update, %s does not exist', prepid)
            return {'results': False,
                    'message': 'Cannot update, "%s" does not exist' % (prepid)}

        # find out what is the change
        previous_version = Flow(json_input=flow_db.get(prepid))

        old_ps = previous_version.get_attribute('request_parameters').get('process_string', None)
        new_ps = flow.get_attribute('request_parameters').get('process_string', None)
        if old_ps != new_ps:
            request_db = Database('requests')
            request_query = request_db.make_query({'status': 'submitted', 'flown_with': prepid})
            requests = request_db.full_text_search('search',
                                                   request_query,
                                                   limit=1,
                                                   include_fields='prepid')
            if requests:
                return {'results': False,
                        'message': ('Cannot change process string because there are requests in '
                                    'status "submitted" that are flown with "%s"' % (prepid))}

        # Make allowed campaigns unique
        allowed_campaigns = sorted(list(set(flow.get_attribute('allowed_campaigns'))))
        flow.set_attribute('allowed_campaigns', allowed_campaigns)
        # Check if allowed and next campaigns exist
        campaign_check = self.check_campaigns(flow)
        if campaign_check is not True:
            return campaign_check

        # Adjust the request parameters based on next campaign
        parameter_check = self.set_default_request_parameters(flow)
        if parameter_check is not True:
            return parameter_check

        previous_allowed_campaigns = previous_version.get_attribute('allowed_campaigns')
        removed_campaigns = set(previous_allowed_campaigns) - set(allowed_campaigns)
        if removed_campaigns:
            chained_campaign_db = Database('chained_campaigns')
            # Check if there are chained campaigns that are made with this flow
            # and was using the removed campaigns
            for removed_campaign in removed_campaigns:
                contains = {'contains': [prepid, removed_campaign]}
                chained_campaign_query = chained_campaign_db.make_query(contains)
                chained_campaigns = chained_campaign_db.full_text_search('search',
                                                                         chained_campaign_query,
                                                                         limit=1,
                                                                         include_fields='prepid')
                if chained_campaigns:
                    return {'results': False,
                            'message': ('Campaign "%s" cannot be removed because there are chained '
                                        'campaigns using "%s" and "%s" ' % (removed_campaign,
                                                                            prepid,
                                                                            removed_campaign))}

        next_campaign = flow.get_attribute('next_campaign')
        previous_next_campaign = previous_version.get_attribute('next_campaign')
        if previous_next_campaign and previous_next_campaign != next_campaign:
            chained_campaign_db = Database('chained_campaigns')
            # Check if there are chained campaigns that are made with this flow
            # and was using the changed next campaign
            contains = {'contains': [prepid, previous_next_campaign]}
            chained_campaign_query = chained_campaign_db.make_query(contains)
            chained_campaigns = chained_campaign_db.full_text_search('search',
                                                                     chained_campaign_query,
                                                                     limit=1,
                                                                     include_fields='prepid')
            if chained_campaigns:
                return {'results': False,
                        'message': ('Campaign "%s" cannot be removed because there are chained '
                                    'campaigns using "%s" and "%s" ' % (previous_next_campaign,
                                                                        prepid,
                                                                        previous_next_campaign))}

        difference = self.get_obj_diff(previous_version.json(),
                                       flow.json(),
                                       ('history', '_rev'))
        difference = ', '.join(difference)
        flow.update_history({'action': 'update', 'step': difference})

        # Save to DB
        if not flow_db.update(flow.json()):
            self.logger.error('Could not save flow %s to database', prepid)
            return {'results': False,
                    'message': 'Could not save flow %s to database' % (prepid)}

        # Update relevant campaigns' "Next" parameter
        self.update_derived_objects(previous_version, flow)

        return {'results': True}


class DeleteFlow(FlowRESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def delete(self, flow_id):
        """
        Delete a flow
        """
        flow_db = Database('flows')
        if not flow_db.document_exists(flow_id):
            self.logger.error('Cannot delete, %s does not exist', flow_id)
            return {'results': False,
                    'message': 'Cannot delete, %s does not exist' % (flow_id)}

        # Check chained campaigns...
        chained_campaign_db = Database('chained_campaigns')
        chained_campaigns = chained_campaign_db.query('contains==%s' % (flow_id), limit=3)
        if chained_campaigns:
            chained_campaign_ids = ', '.join(x['_id'] for x in chained_campaigns)
            message = 'Chained campaign(s) %s have %s, delete them first' % (chained_campaign_ids,
                                                                             flow_id)
            self.logger.error(message)
            return {'results': False,
                    'message': message}

        # Check requests...
        request_db = Database('requests')
        requests = request_db.query('flown_with==%s' % (flow_id), limit=3)
        if requests:
            request_ids = ', '.join(x['_id'] for x in requests)
            message = 'Request(s) %s are flown with %s, delete them first' % (request_ids,
                                                                              flow_id)
            self.logger.error(message)
            return {'results': False,
                    'message': message}

        # Delete to DB
        flow = Flow(json_input=flow_db.get(flow_id))
        if not flow_db.delete(flow_id):
            self.logger.error('Could not delete flow %s from database', flow_id)
            return {'results': False,
                    'message': 'Could not delete flow %s from database' % (flow_id)}

        # Update relevant campaigns' "Next" parameter
        self.update_derived_objects(flow, None)

        return {'results': True}


class GetFlow(RESTResource):

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, flow_id):
        """
        Retrieve the flow for given id
        """
        flow_db = Database('flows')
        return {'results': flow_db.get(prepid=flow_id)}


class ApproveFlow(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, flow_id):
        """
        Move the given flow(s) id to the next approval
        """
        flow_db = Database('flows')
        if not flow_db.document_exists(flow_id):
            return {'prepid': flow_id,
                    'results': False,
                    'message': 'The flow "%s" does not exist' % (flow_id)}

        flow = Flow(json_input=flow_db.get(flow_id))
        try:
            flow.toggle_approval()
            saved = flow.save()
            return {'prepid': flow_id,
                    'results': saved}
        except Exception as ex:
            self.logger.error('Error approving flow "%s": %s', flow_id, ex)
            return {'prepid': flow_id,
                    'results': False}


class CloneFlow(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Make a clone of flow
        """
        data = json.loads(flask.request.data)
        flow_id = data['prepid']
        new_flow_id = data['new_prepid']
        if not flow_id or not new_flow_id:
            self.logger.error('Invalid prepid "%s" or "%s"', flow_id, new_flow_id)
            return {'results': False,
                    'message': 'Invalid prepid "%s" or "%s"' % (flow_id, new_flow_id)}

        if not self.fullmatch(Flow._prepid_pattern, new_flow_id):
            self.logger.error('Invalid new flow name %s', new_flow_id)
            return {'results': False,
                    'message': 'Invalid new flow name "%s"' % (new_flow_id)}

        flow_db = Database('flows')
        if not flow_db.document_exists(flow_id):
            return {'results': False,
                    'message': 'Flow "%s" does not exist' % (flow_id)}

        if flow_db.document_exists(new_flow_id):
            return {'results': False,
                    'message': 'Flow "%s" already exist' % (new_flow_id)}

        new_json = flow_db.get(flow_id)
        new_json['prepid'] = new_flow_id
        new_json['_id'] = new_flow_id
        for attr in ('history', '_rev'):
            new_json.pop(attr, None)

        new_flow = Flow()
        new_flow.update(new_json)
        new_flow.update_history({'action': 'clone', 'step': flow_id})
        if new_flow.save():
            return {'results': True,
                    'message': 'Created %s' % (new_flow_id),
                    'prepid': new_flow_id}

        return {'results': False,
                'message': 'Error saving new flow'}
