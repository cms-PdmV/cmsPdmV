from json_layer.json_base import json_base


class flow(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'next_campaign': '',
        'allowed_campaigns': [],
        'request_parameters': {},
        'notes': '',
        'history': [],
        'approval': ''
    }

    _json_base__approvalsteps = ['none', 'flow', 'submit', 'tasksubmit']

    _prepid_pattern = 'flow[a-zA-Z0-9]{2,60}'

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}

        self._json_base__schema['approval'] = self.get_approval_steps()[0]

        # update self according to json_input
        self.update(json_input)
        self.validate()

    def toggle_approval(self):
        approval_steps = self.get_approval_steps()
        approval = self.get_attribute('approval')
        index = approval_steps.index(approval)
        self.approve(to_approval=approval_steps[(index + 1) % (len(approval_steps))])
