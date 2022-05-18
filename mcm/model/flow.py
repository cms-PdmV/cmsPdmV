from model.model_base import ModelBase


class Flow(ModelBase):

    _ModelBase__schema = {
        '_id': '',
        'prepid': '',
        'next_campaign': '',
        'allowed_campaigns': [],
        'request_parameters': {},
        'notes': '',
        'history': [],
        'approval': 'none'
    }
    database_name = 'flows'

    def validate(self):
        prepid = self.get('prepid')
        if not self.flow_prepid_regex(prepid):
            raise Exception('Invalid flow prepid')

        # Make allowed campaigns unique
        allowed_campaigns = sorted(list(set(self.get('allowed_campaigns'))))
        self.set('allowed_campaigns', allowed_campaigns)

        request_parameters = self.get('request_parameters')
        allowed_parameters = {'time_event', 'size_event', 'process_string', 'keep_output',
                              'pileup_dataset_name', 'sequences', 'sequences_name'}
        invalid_parameters = set(list(request_parameters.keys())) - allowed_parameters
        if invalid_parameters:
            raise Exception('Not allowed parameters: %s' % (', '.join(list(invalid_parameters))))

        return super().validate()

    def toggle_type(self):
        approval_steps = ('none', 'together', 'together_unique', 'after_done')
        approval = self.get_attribute('approval')
        index = approval_steps.index(approval) if approval in approval_steps else 0
        new_approval = approval_steps[(index + 1) % (len(approval_steps))]
        self.set_attribute('approval', new_approval)
        self.update_history('approve', new_approval)

    def get_editing_info(self):
        info = super().get_editing_info()
        info['allowed_campaigns'] = True
        info['next_campaign'] = True
        info['notes'] = True
        info['prepid'] = not bool(self.get('prepid'))
        info['request_parameters'] = True
        return info

    def build_sequences(self, campaign):
        """
        Build sequences from the given campaign and this flow
        """
        campaign_sequences = campaign.get('sequences')[sequences_name]
        request_parameters = self.get('request_parameters')
        sequences_name = request_parameters.get('sequences_name', 'default')
        flow_sequences = request_parameters.get('sequences', [])
        # Add empty sequences to flow, if needed
        flow_sequences += (len(campaign_sequences) - len(flow_sequences)) * [{}]
        if len(campaign_sequences) != len(flow_sequences):
            flow_name = self.get('prepid')
            campaign_name = campaign.get('prepid')
            raise Exception(f'Cannot build sequences for {campaign_name} + {flow_name}')

        sequences = []
        # Iterate through campaign and flow sequences
        # Apply flow changes over campaign's sequence and add to list
        for flow_seq, campaign_seq in zip(flow_sequences, campaign_sequences):
            # Allow all attributes?
            campaign_seq.update(flow_seq)
            sequences.append(campaign_seq)

        return sequences
