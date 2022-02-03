from rest_api.RestAPIMethod import DeleteRESTResource, RESTResource
from couchdb_layer.mcm_database import database as Database
from json_layer.chained_campaign import ChainedCampaign
from json_layer.user import Role
from tools.exceptions import NotFoundException


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


class DeleteChainedCampaign(DeleteRESTResource):

    def delete_check(self, obj):
        prepid = obj.get('prepid')
        # Check chained requests...
        ch_request_db = Database('chained_requests')
        ch_requests = ch_request_db.query_view('member_of_campaign', prepid, limit=3)
        if ch_requests:
            ch_request_ids = ', '.join(x['_id'] for x in ch_requests)
            raise Exception('Chained request(s) %s are member of %s, delete them first' % (ch_request_ids,
                                                                                           prepid))

        return super().delete_check(obj)

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def delete(self, prepid):
        """
        Delete a chained campaign
        """
        return self.delete_object(prepid, ChainedCampaign)


class GetChainedCampaign(RESTResource):
    """
    Endpoing for retrieving a chained campaign
    """

    def get(self, prepid):
        """
        Retrieve the chained campaign for given id
        """
        chained_campaign = ChainedCampaign.fetch(prepid)
        if not chained_campaign:
            raise NotFoundException(prepid)

        return {'results': chained_campaign.json()}


class GetEditableChainedCampaign(RESTResource):
    """
    Endpoing for retrieving a chained campaign and it's editing info
    """

    def get(self, prepid):
        """
        Retrieve the chained campaign and it's editing info for given id
        """
        chained_campaign = ChainedCampaign.fetch(prepid)
        if not chained_campaign:
            raise NotFoundException(prepid)

        return {'results': {'object': chained_campaign.json(),
                            'editing_info': chained_campaign.get_editing_info()}}
