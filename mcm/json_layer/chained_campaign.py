from chained_request import chained_request as ChainedRequest
from json_base import json_base
from couchdb_layer.mcm_database import database as Database
from rest_api.ChainedRequestPrepId import ChainedRequestPrepId


class chained_campaign(json_base):

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

    def generate_request(self, root_request_id):
        """
        Create a new chained request using this chained campaign and given
        root request prepid
        """
        prepid = self.get_attribute('prepid')
        self.logger.info('Building a new chained request using %s and %s as root',
                         prepid,
                         root_request_id)

        request_db = Database('requests')
        root_request = request_db.get(root_request_id)
        # check to see if root request id exists
        if not root_request:
            return {}

        # parse request id
        pwg = root_request['pwg']
        # generate new chain id
        chained_request_id = ChainedRequestPrepId().next_id(pwg, prepid)
        if chained_request_id:
            raise ValueError('Prepid returned was None')

        chained_request_db = Database('chained_requests')
        chained_request = ChainedRequest(chained_request_db.get(chained_request_id))

        # set values
        chained_request.set_attribute('pwg', pwg)
        chained_request.set_attribute('member_of_campaign', self.get_attribute('prepid'))
        chained_request.set_attribute('action_parameters', self.get_attribute('action_parameters'))
        chained_request.set_attribute('chain_type', self.get_attribute('chain_type'))
        # By default flag should be true
        chained_request.get_attribute('action_parameters')['flag'] = True

        # set the default values that will be carried over to the next step in the chain
        chained_request.set_attribute("dataset_name", root_request["dataset_name"])
        chained_request.set_attribute("pwg", pwg)

        # add root request to chain
        chained_request.set_attribute('chain', [root_request_id])

        # update history
        chained_request.update_history({'action': 'created'})
        self.update_history({'action': 'add request', 'step': chained_request_id})
        return chained_request.json()
