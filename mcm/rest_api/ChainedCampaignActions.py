#!/usr/bin/env python

import flask
import time

from json import dumps, loads
from random import shuffle

from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from json_layer.chained_request import chained_request
from json_layer.chained_campaign import chained_campaign
from tools.user_management import access_rights
import tools.settings as settings


class CreateChainedCampaign(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Create a chained campaign from the provide json content
        """
        return self.create_campaign(flask.request.data)

    def create_campaign(self, data):
        db = database('chained_campaigns')
        if '_rev' in data:
            return {"results": " cannot create from a json with _rev"}

        try:
            ccamp = chained_campaign(json_input=loads(data))
        except chained_campaign('').IllegalAttributeName as ex:
            return {"results": False, "message": str(ex)}

        if not ccamp.get_attribute('prepid'):
            generated_prepid = 'chain'
            for i, c in enumerate(ccamp.get_attribute('campaigns')):
                generated_prepid += '_'
                if i == 0:
                    generated_prepid += c[0]
                else:
                    generated_prepid += c[1]

            ccamp.set_attribute('prepid', generated_prepid)

        self.logger.info('Creating new chained_campaign %s...' % (ccamp.get_attribute('prepid')))
        ccamp.set_attribute("_id", ccamp.get_attribute("prepid"))
        chained_campaign_id = ccamp.get_attribute('_id')
        if db.document_exists(chained_campaign_id):  # or self.db.document_exists(ccamp.get_attribute("_id")):
            self.logger.error('Campaign %s already exists. Cannot re-create it.' % (chained_campaign_id))
            return {"results": False, "message": 'Campaign %s already exists' % (chained_campaign_id)}

        # update history
        ccamp.update_history({'action' :'created'})
        saved = db.save(ccamp.json())
        # update campaigns db
        self.update_campaigns(ccamp)

        if saved:
            return {"results": True, "prepid": ccamp.get_attribute("prepid")}
        else:
            return {"results": False, "message": "could not save to DB"}

    def update_campaigns(self, ccamp):
        cdb = database('campaigns')
        next = None
        self.logger.info('Looking at campaigns %s' % (ccamp.get_attribute('campaigns')))
        for (c, f) in reversed(ccamp.get_attribute('campaigns')):
            mcm_c = cdb.get(c)
            if next:
                if next not in mcm_c['next']:
                    mcm_c['next'].append(next)
                    mcm_c['next'].sort()
                    cdb.update(mcm_c)
            next = c


class UpdateChainedCampaign(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Update the content of a chained campaign with the provided json content
        """
        return self.update_campaign(loads(flask.request.data))

    def update_campaign(self, data):
        if '_rev' not in data:
            return {"results": False, 'message': 'There is no previous revision provided'}
        try:
            ccamp = chained_campaign(json_input=data)
        except chained_campaign.IllegalAttributeName:
            return {"results": False}

        prepid = ccamp.get_attribute('prepid')
        if not prepid and not ccamp.get_attribute('_id'):
            raise ValueError('Prepid returned was None')

        db = database('chained_campaigns')
        previous_version = chained_campaign(json_input=db.get(prepid))
        self.logger.info('Updating chained campaign %s', prepid)
        # update history
        difference = self.get_obj_diff(previous_version.json(),
                                       ccamp.json(),
                                       ('history', '_rev'))
        difference = ', '.join(difference)
        ccamp.update_history({'action': 'update', 'step': difference})
        return {"results": db.update(ccamp.json())}


class DeleteChainedCampaign(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.db_name = 'chained_campaigns'
        self.before_request()
        self.count_call()

    def delete(self, chained_campaign_id, force=False):
        """
        Delete a chained campaign and all related
        """
        force = True if force == 'force' else False
        return self.delete_request(chained_campaign_id, force)

    def delete_request(self, ccid, force=False):
        if not self.delete_all_requests(ccid, force):
            return {"results": False}

        db = database(self.db_name)
        return {"results": db.delete(ccid)}

    def delete_all_requests(self, cid, force=False):
        rdb = database('chained_requests')
        res = rdb.query('member_of_campaign==' + cid, page_num=-1)
        if len(res) and not force:
            return False
        try:
            for req in res:
                rdb.delete(req['prepid'])
            return True
        except Exception as ex:
            self.logger.error("Failed to delete all requests. exception:%s" % (str(ex)))
            return False


class GetChainedCampaign(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()
        self.db = database('chained_campaigns')

    def get(self, chained_campaign_id):
        """
        Retrieve the content of a given chained campaign id
        """
        return self.get_request(chained_campaign_id)

    def get_request(self, id):
        return {"results": self.db.get(id)}


class InspectChainedCampaignsRest(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def listAll(self):
        ccdb = database('chained_campaigns')
        all_cc = ccdb.raw_query("prepid")
        prepids_list = map(lambda x: x['id'], all_cc)
        return prepids_list

    def multiple_inspect(self, ccids):

        settings.set_value('inspect_chained_campaigns_running', True)
        crdb = database('chained_requests')
        try:
            ccids = ccids.split(',')
            index = 0
            while len(ccids) > index:
                query = crdb.construct_lucene_complex_query([
                    ('member_of_campaign', {'value': ccids[index: index + 20]}),
                    ('last_status', {'value': 'done'}),
                    ('status', {'value': 'processing'})
                ])
                crlist = crdb.full_text_search('search', query, page=-1)
                # we yield len of cr_list so we would know how much data later on we processed
                yield dumps({'prepids': ccids[index: index + 20], 'cr_len': len(crlist)}, indent=2)
                index += 20
                for cr in crlist:
                    time.sleep(0.5)
                    mcm_cr = chained_request(cr)
                    if mcm_cr:
                        __inspect_ret = mcm_cr.inspect()
                    else:
                        __inspect_ret = {"prepid": cr, "results": False,
                                'message': '%s does not exist' % cr['prepid']}

                    self.logger.info("Inspection for: %s returned: %s" % (cr['prepid'],
                            __inspect_ret))

                    yield dumps(__inspect_ret, indent=4)

                # force slowing-down of inspect to not abuse the DB
                time.sleep(1)
            self.logger.info("ChainedCampaigns inspection finished")

        except Exception as ex:
            self.logger.error("ChainedCampaigns inspection crashed. reason: %s" % str(ex))
            yield dumps({'message': 'crlist crashed: %s' % (str(ex)),
                    'last_used_query': query})
        finally:
            settings.set_value('inspect_chained_campaigns_running', False)


class InspectChainedRequests(InspectChainedCampaignsRest):
    def __init__(self):
        InspectChainedCampaignsRest.__init__(self)

    def get(self, chained_campaign_ids):
        """
        Inspect the chained requests of a provided chained campaign id
        """
        return flask.Response(flask.stream_with_context(self.multiple_inspect(chained_campaign_ids)))


class InspectChainedCampaigns(InspectChainedCampaignsRest):
    def __init__(self):
        InspectChainedCampaignsRest.__init__(self)

    def get(self, action):
        """
        Inspect the chained requests of all chained campaigns, requires /all
        """
        if action != 'all':
            return {"results": 'Error: Incorrect argument provided'}
        is_running = settings.get_value('inspect_chained_campaigns_running')
        self.logger.info('InspectChainedRequests is running: %s' % (is_running))
        # if is_running:
        #     return {"results": 'Already running inspection'}

        # force pretify output in browser for multiple lines
        self.representations = {'text/plain': self.output_text}
        ccid_list = self.listAll()
        shuffle(ccid_list)
        return flask.Response(flask.stream_with_context(self.multiple_inspect(','.join(ccid_list))))


class ChainedCampaignsPriorityChange(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.chained_campaigns_db = database("chained_campaigns")
        self.before_request()
        self.count_call()

    def post(self):
        fails = []
        for chain in loads(flask.request.data):
            chain_prepid = chain['prepid']
            mcm_chained_campaign = chained_campaign(self.chained_campaigns_db.get(chain_prepid))
            mcm_chained_campaign.set_attribute('action_parameters', chain['action_parameters'])
            if not mcm_chained_campaign.save():
                message = 'Unable to save chained campaign %s' % chain_prepid
                fails.append(message)
                self.logger.error(message)
        return {
            'results': True if len(fails) == 0 else False,
            'message': fails
        }
