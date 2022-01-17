from copy import deepcopy
from couchdb_layer.mcm_database import database as Database
from rest_api.RestAPIMethod import RESTResource
from json_layer.campaign import Campaign
from json_layer.flow import Flow
from json_layer.user import Role


class FlowRESTResource(RESTResource):

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
                campaign = Campaign(campaign_db.get(old_allowed_id))
                next_campaigns = campaign.get_attribute('next')
                if old_next_id in next_campaigns:
                    next_campaigns.remove(old_next_id)
                    campaign.set_attribute('next', next_campaigns)
                    campaign.save()

        # Add
        if new_next_id:
            for new_allowed_id in add_to:
                campaign = Campaign(campaign_db.get(new_allowed_id))
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
        sequence_name = parameters.get('sequences_name', 'default')
        campaign_sequences = next_campaign['sequences']
        if sequence_name not in campaign_sequences:
            return {'results': False,
                    'message': '%s is not defined in %s' % (sequence_name, next_campaign_id)}

        campaign_sequences = campaign_sequences[sequence_name]
        if len(parameters['sequences']) > len(campaign_sequences):
            return {'results': False,
                    'message': 'Flow has more sequences than "%s" campaign' % (next_campaign_id)}

        while len(parameters['sequences']) < len(campaign_sequences):
            parameters['sequences'].append({})

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

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def put(self, data):
        """
        Create a flow with the provided json content
        """
        flow = Flow(data)
        prepid = flow.get_attribute('prepid')
        if not prepid:
            self.logger.error('Invalid prepid "%s"', prepid)
            return {'results': False,
                    'message': 'Invalid prepid "%s"' % (prepid)}

        if not self.fullmatch(Flow._prepid_pattern, prepid):
            self.logger.error('Invalid flow name %s', prepid)
            return {'results': False,
                    'message': 'Invalid flow name "%s"' % (prepid)}

        if Flow.fetch(prepid):
            self.logger.error('Flow "%s" already exists', prepid)
            return {'results': False,
                    'message': 'Flow "%s" already exists' % (prepid)}

        # Validate
        flow.validate()
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
        if not flow.save():
            return {'results': False,
                    'message': 'Could not save flow %s to database' % (prepid)}

        # Update relevant campaigns' "Next" parameter
        self.update_derived_objects(None, flow)

        return {'results': True}


class UpdateFlow(FlowRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Update a flow with the provided json content
        """
        prepid = data.get('prepid', data.get('_id'))
        if not prepid:
            return {'results': False,
                    'message': 'Missing prepid in submitted data'}

        old_flow = Flow.fetch(prepid)
        if not old_flow:
            return {"results": False,
                    'message': 'Object "%s" does not exist' % (prepid)}

        new_flow = Flow(data)
        if new_flow.get('_rev') != old_flow.get('_rev'):
            return {'results': False,
                    'message': 'Provided revision does not match revision in database'}

        # Validate
        new_flow.validate()

        # Check if there are submitted requests when changing processing string
        old_ps = old_flow.get_attribute('request_parameters').get('process_string', None)
        new_ps = new_flow.get_attribute('request_parameters').get('process_string', None)
        if old_ps != new_ps:
            request_db = Database('requests')
            requests = request_db.search({'status': 'submitted', 'flown_with': prepid},
                                         limit=1,
                                         include_fields='prepid')
            if requests:
                return {'results': False,
                        'message': ('Cannot change process string because there are requests in '
                                    'status "submitted" that are flown with "%s"' % (prepid))}

        # Check if allowed and next campaigns exist
        campaign_check = self.check_campaigns(new_flow)
        if campaign_check is not True:
            return campaign_check

        # Adjust the request parameters based on next campaign
        parameter_check = self.set_default_request_parameters(new_flow)
        if parameter_check is not True:
            return parameter_check

        old_allowed_campaigns = old_flow.get('allowed_campaigns')
        new_allowed_campaigns = new_flow.get('allowed_campaigns')
        removed_campaigns = set(old_allowed_campaigns) - set(new_allowed_campaigns)
        if removed_campaigns:
            chained_campaign_db = Database('chained_campaigns')
            # Check if there are chained campaigns that are made with this flow
            # and was using the removed campaigns
            for removed_campaign in removed_campaigns:
                # Contains this flow AND removed campaign
                chained_campaign_query = {'contains': prepid,
                                          'contains_': removed_campaign}
                chained_campaigns = chained_campaign_db.search(chained_campaign_query,
                                                               limit=1,
                                                               include_fields='prepid')
                if chained_campaigns:
                    return {'results': False,
                            'message': ('Campaign "%s" cannot be removed because there are chained '
                                        'campaigns using "%s" and "%s" ' % (removed_campaign,
                                                                            prepid,
                                                                            removed_campaign))}

        new_next_campaign = new_flow.get('next_campaign')
        old_next_campaign = old_flow.get('next_campaign')
        if old_next_campaign and old_next_campaign != new_next_campaign:
            chained_campaign_db = Database('chained_campaigns')
            # Check if there are chained campaigns that are made with this flow
            # and was using the changed next campaign
            # Contains this flow AND that next campaign
            chained_campaign_query = {'contains': prepid,
                                      'contains_': old_next_campaign}
            chained_campaigns = chained_campaign_db.search(chained_campaign_query,
                                                           limit=1,
                                                           include_fields='prepid')
            if chained_campaigns:
                return {'results': False,
                        'message': ('Campaign "%s" cannot be removed because there are chained '
                                    'campaigns using "%s" and "%s" ' % (old_next_campaign,
                                                                        prepid,
                                                                        old_next_campaign))}

        difference = self.get_obj_diff(old_flow.json(),
                                       new_flow.json(),
                                       ('history', '_rev'))
        if not difference:
            return {'results': True}

        difference = ', '.join(difference)
        new_flow.set('history', old_flow.get('history'))
        new_flow.update_history({'action': 'update', 'step': difference})

        # Save to DB
        if not new_flow.save():
            return {'results': False,
                    'message': 'Could not save flow %s to database' % (prepid)}

        # Update relevant campaigns' "Next" parameter
        self.update_derived_objects(old_flow, new_flow)

        return {'results': True}


class DeleteFlow(FlowRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
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
        chained_campaigns = chained_campaign_db.query_view('contains', flow_id, limit=3)
        if chained_campaigns:
            chained_campaign_ids = ', '.join(x['_id'] for x in chained_campaigns)
            message = 'Chained campaign(s) %s have %s, delete them first' % (chained_campaign_ids,
                                                                             flow_id)
            self.logger.error(message)
            return {'results': False,
                    'message': message}

        # Check requests...
        request_db = Database('requests')
        requests = request_db.query_view('flown_with', flow_id, limit=3)
        if requests:
            request_ids = ', '.join(x['_id'] for x in requests)
            message = 'Request(s) %s are flown with %s, delete them first' % (request_ids,
                                                                              flow_id)
            self.logger.error(message)
            return {'results': False,
                    'message': message}

        # Delete to DB
        flow = Flow(flow_db.get(flow_id))
        if not flow_db.delete(flow_id):
            self.logger.error('Could not delete flow %s from database', flow_id)
            return {'results': False,
                    'message': 'Could not delete flow %s from database' % (flow_id)}

        # Update relevant campaigns' "Next" parameter
        self.update_derived_objects(flow, None)

        return {'results': True}


class GetFlow(RESTResource):

    def get(self, flow_id):
        """
        Retrieve the flow for given id
        """
        flow_db = Database('flows')
        return {'results': flow_db.get(prepid=flow_id)}


class ApproveFlow(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def post(self, flow_id):
        """
        Move the given flow(s) id to the next approval
        """
        flow = Flow.fetch(flow_id)
        if not flow:
            return {'prepid': flow_id,
                    'results': False,
                    'message': 'The flow "%s" does not exist' % (flow_id)}

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

    @RESTResource.ensure_role(Role.MC_CONTACT)
    @RESTResource.request_with_json
    def put(self, data):
        """
        Make a clone of flow
        """
        flow_id = data['prepid']
        new_flow_id = data['new_prepid']
        old_flow = Flow.fetch(flow_id)
        if not old_flow:
            return {'results': False,
                    'message': 'Flow "%s" does not exist' % (flow_id)}

        if Flow.fetch(new_flow_id):
            return {'results': False,
                    'message': 'Flow "%s" already exist' % (new_flow_id)}

        new_json = deepcopy(old_flow.json())
        new_json['prepid'] = new_flow_id
        new_json['_id'] = new_flow_id
        for attr in ('history', '_rev'):
            new_json.pop(attr, None)

        new_flow = Flow(new_json)
        new_flow.validate()
        new_flow.update_history({'action': 'clone', 'step': flow_id})
        if not new_flow.save():
            return {'results': False,
                    'message': 'Error saving new flow'}

        return {'results': True,
                'message': 'Created %s' % (new_flow_id),
                'prepid': new_flow_id}
