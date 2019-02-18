#!/usr/bin/env python

from chained_request import chained_request
from json_base import json_base
from couchdb_layer.mcm_database import database
from rest_api.ChainedRequestPrepId import ChainedRequestPrepId


class chained_campaign(json_base):
    class CampaignDoesNotExistException(Exception):
        def __init__(self, campid):
            self.c = str(campid)
            chained_campaign.logger.error('Campaign %s does not exist' % (self.c))

        def __str__(self):
            return 'Error: Campaign ' + self.c + ' does not exist.'

    class FlowDoesNotExistException(Exception):
        def __init__(self, flowid):
            self.f = str(flowid)
            chained_campaign.logger.error('Flow %s does not exist' % (self.f))

        def __str__(self):
            return 'Error: Flow ' + self.f + ' does not exist.'

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'alias': '',
        'campaigns': [],  # list of lists [camp_id, flow]
        'notes': '',
        'action_parameters': {
            'block_number': 0,
            'staged': 0,
            'threshold': 0,
            'flag': True
        },
        'history': [],
        'valid': True,
        'chain_type': 'TaskChain',
        'do_not_check_cmssw_versions': False
    }

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}

        # update self according to json_input
        self.update(json_input)
        self.validate()

    # start() makes the chained campaign visible to the actions page
    def start(self):
        if self._json_base__json['valid']:
            return
        self.update_history({'action': 'start'})
        self._json_base__json['valid'] = True

    # stop() makes the chained campaign invisible to the actions page
    def stop(self):
        if not self._json_base__json['valid']:
            return
        self.update_history({'action': 'stop'})
        self._json_base__json['valid'] = False

    def add_campaign(self, campaign_id, flow_name=None):
        self.logger.info('Adding a new campaign %s to chained campaign %s' % (campaign_id, self.get_attribute('_id')))
        camp_db = database('campaigns')
        flow_db = database('flows')
        if not camp_db.document_exists(campaign_id):
            raise self.CampaignDoesNotExistException(campaign_id)

        # check to see if flow_name is none (campaign_id = root)
        if flow_name is not None:
            if not flow_db.document_exists(flow_name):
                raise self.FlowDoesNotExistException(flow_name)

        camps = self.get_attribute('campaigns')
        if not camps or camps is None:
            camps = []
        camps.append([campaign_id, flow_name])
        self.set_attribute('campaigns', camps)

        return True

    def remove_campaign(self, cid):
        self.logger.info('Removing campaign %s from chained_campaign %s' % (cid, self.get_attribute('_id')))
        camps = self.get_attribute('campaigns')
        new_camps = []
        if not camps or camps is None:
            camps = []
        else:
            for c, f in camps:
                if cid in c:
                    continue
                new_camps.append((c, f))

        self.set_attribute('campaigns', new_camps)

    # create a chained request spawning from root_request_id
    def generate_request(self, root_request_id):
        self.logger.info('Building a new chained_request for chained_campaign %s. Root request: %s' % (self.get_attribute('_id'), root_request_id))
        try:
            rdb = database('requests')
            crdb = database('chained_requests')
        except database.DatabaseAccessError:
            return {}

        # check to see if root request id exists
        if not rdb.document_exists(root_request_id):
            return {}

        # init new creq

        # parse request id
        tok = root_request_id.split('-')
        pwg = tok[0]
        # generate new chain id
        cid = ChainedRequestPrepId().next_id(pwg, self.get_attribute('prepid'))

        creq = chained_request(crdb.get(cid))

        # set values
        creq.set_attribute('pwg', pwg)
        creq.set_attribute('member_of_campaign', self.get_attribute('prepid'))
        creq.set_attribute('action_parameters', self.get_attribute('action_parameters'))
        creq.set_attribute('chain_type', self.get_attribute('chain_type'))
        # By default flag should be true
        creq.get_attribute('action_parameters')['flag'] = True
        if not creq.get_attribute('prepid'):
            raise ValueError('Prepid returned was None')

        # set the default values that will be carried over to the next step in the chain
        req = rdb.get(root_request_id)

        creq.set_attribute("dataset_name", req["dataset_name"])
        creq.set_attribute("pwg", req["pwg"])

        # add root request to chain
        creq.set_attribute('chain', [root_request_id])

        # update history
        creq.update_history({'action': 'created'})
        self.update_history({'action': 'add request', 'step': creq.get_attribute('_id')})

        # save to database
        return creq.json()

    def __remove_request_parameters(self, rootid=None):
        ob = self.get_attribute('action_parameters')
        res = {}
        for key in ob:
            if key == rootid:
                continue
            res[key] = ob[key]
        self.set_attribute('action_parameters', res)
