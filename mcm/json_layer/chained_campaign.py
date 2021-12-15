# from chained_request import chained_request as ChainedRequest
from json_layer.json_base import json_base
from couchdb_layer.mcm_database import database as Database
# from rest_api.ChainedRequestPrepId import ChainedRequestPrepId


class chained_campaign(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'alias': '',
        'campaigns': [],  # list of lists [camp_id, flow]
        'notes': '',
        'action_parameters': {
            'threshold': 0,
            'flag': True
        },
        'history': [],
        'do_not_check_cmssw_versions': False
    }

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}

        # update self according to json_input
        self.update(json_input)
        self.validate()

    def generate_request(self, root_request):
        """
        Create a new chained request using this chained campaign and given
        root request
        """
        prepid = self.get_attribute('prepid')
        root_request_id = root_request.get_attribute('prepid')
        self.logger.info('Building a new chained request using %s and %s as root',
                         prepid,
                         root_request_id)

        # parse request id
        pwg = root_request.get_attribute('pwg')
        # generate new chain id
        chained_request_id = ChainedRequestPrepId().next_prepid(pwg, prepid)
        if not chained_request_id:
            raise ValueError('Prepid returned was None')

        chained_request_db = Database('chained_requests')
        chained_request = ChainedRequest(chained_request_db.get(chained_request_id))

        # set values
        chained_request.set_attribute('pwg', pwg)
        chained_request.set_attribute('member_of_campaign', self.get_attribute('prepid'))
        chained_request.set_attribute('action_parameters', self.get_attribute('action_parameters'))
        # By default flag should be true
        chained_request.get_attribute('action_parameters')['flag'] = True

        # set the default values that will be carried over to the next step in the chain
        chained_request.set_attribute("dataset_name", root_request.get_attribute("dataset_name"))
        chained_request.set_attribute("pwg", pwg)

        # Last status of chain
        request_status = root_request.get_attribute('status')
        chained_request.set_attribute('last_status', request_status)
        if request_status in {'submitted', 'done'}:
            chained_request.set_attribute('status', 'processing')

        # add root request to chain
        chained_request.set_attribute('chain', [root_request_id])

        # update history
        chained_request.update_history({'action': 'created'})
        return chained_request
