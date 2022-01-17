from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database as Database
from json_layer.chained_campaign import ChainedCampaign
from json_layer.user import Role


class CreateChainedCampaign(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def put(self, data):
        """
        Create chained campaign with the provided json content
        """
        chained_campaign_db = Database('chained_campaigns')
        chained_campaign = ChainedCampaign(data)
        campaigns = chained_campaign.get_attribute('campaigns')
        if not campaigns:
            return {'results': False,
                    'message': 'Chained campaign must have at least one campaign'}

        prepid = 'chain'
        for i, (campaign, flow) in enumerate(campaigns):
            if i == 0:
                prepid += '_%s' % (campaign)
            else:
                prepid += '_%s' % (flow)

        self.logger.info('Creating new chained campaign %s' % (prepid))
        if chained_campaign_db.document_exists(prepid):
            self.logger.error('Chained campaign "%s" already exists', prepid)
            return {"results": False,
                    "message": 'Chained campaign "%s" already exists' % (prepid)}

        chained_campaign.set_attribute('prepid', prepid)
        chained_campaign.set_attribute("_id", prepid)
        # update history
        chained_campaign.update_history('created')
        if not chained_campaign_db.save(chained_campaign.json()):
            self.logger.error('Could not save chained campaign "%s" to database', prepid)
            return {'results': False,
                    'message': 'Could not save chained campaign "%s" to database' % (prepid)}

        return {'results': True,
                'prepid': prepid}


class UpdateChainedCampaign(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Update a chained campaign with the provided json content
        """
        if '_rev' not in data:
            return {'results': False,
                    'message': 'No revision provided'}

        chained_campaign_db = Database('chained_campaigns')
        chained_campaign = ChainedCampaign(data)
        prepid = chained_campaign.get_attribute('prepid')
        if not prepid:
            self.logger.error('Invalid prepid "%s"', prepid)
            return {'results': False,
                    'message': 'Invalid prepid "%s"' % (prepid)}

        if not chained_campaign_db.document_exists(prepid):
            self.logger.error('Cannot update, %s does not exist', prepid)
            return {'results': False,
                    'message': 'Cannot update, "%s" does not exist' % (prepid)}

        previous_version = ChainedCampaign.fetch(prepid)
        difference = self.get_obj_diff(previous_version.json(),
                                       chained_campaign.json(),
                                       ('history', '_rev'))
        if not difference:
            return {'results': True}

        difference = ', '.join(difference)
        chained_campaign.update_history('update', difference)

        # Save to DB
        if not chained_campaign_db.update(chained_campaign.json()):
            self.logger.error('Could not save campaign %s to database', prepid)
            return {'results': False,
                    'message': 'Could not save campaign %s to database' % (prepid)}

        return {'results': True}


class DeleteChainedCampaign(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def delete(self, chained_campaign_id):
        """
        Delete a chained campaign
        """
        prepid = chained_campaign_id # For shorter lines....
        ch_campaign_db = Database('chained_campaigns')
        if not ch_campaign_db.document_exists(prepid):
            self.logger.error('Cannot delete, %s does not exist', prepid)
            return {'results': False,
                    'message': 'Cannot delete, %s does not exist' % (prepid)}

        # Check chained requests...
        ch_request_db = Database('chained_requests')
        ch_requests = ch_request_db.query_view('member_of_campaign', prepid, limit=3)
        if ch_requests:
            ch_request_ids = ', '.join(x['_id'] for x in ch_requests)
            message = 'Chained request(s) %s are member of %s, delete them first' % (ch_request_ids,
                                                                                     prepid)
            self.logger.error(message)
            return {'results': False,
                    'message': message}

        # Delete to DB
        if not ch_campaign_db.delete(prepid):
            self.logger.error('Could not delete chained campaign %s from database', prepid)
            return {'results': False,
                    'message': 'Could not delete chained campaign %s from database' % (prepid)}

        return {'results': True}


class GetChainedCampaign(RESTResource):

    def get(self, chained_campaign_id):
        """
        Retrieve the chained campaign for given id
        """
        chained_campaign_db = Database('chained_campaigns')
        return {'results': chained_campaign_db.get(prepid=chained_campaign_id)}
