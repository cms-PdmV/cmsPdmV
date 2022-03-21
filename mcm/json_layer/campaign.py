from json_layer.model_base import ModelBase
from json_layer.sequence import Sequence
from tools.exceptions import BadAttributeException


class Campaign(ModelBase):

    _ModelBase__schema = {
        '_id': '',
        'prepid': '',
        'cmssw_release': '',
        'energy': -1.0,
        'events_per_lumi': {'singlecore': 100, 'multicore': 1000},
        'generators': [],
        'history': [],
        'input_dataset': '',
        'memory': 2000,
        'next': [],
        'keep_output': {},  # dict of lists that correspond to sequences
        'notes': '',
        'pileup_dataset_name': '',
        'root': 1,  # -1: possible root, 0: root, 1: non-root
        'sequences': {},  # dict of lists of sequences
        'status': 'stopped',
        'type': '',  # 'LHE', 'Prod', 'MCReproc'
        'www': '',
    }
    database_name = 'campaigns'

    def validate(self):
        """
        Validate attributes of current object
        """
        prepid = self.get('prepid')
        if not self.campaign_prepid_regex(prepid):
            raise BadAttributeException('Invalid campaign prepid')

        cmssw_release = self.get('cmssw_release')
        if cmssw_release and not self.cmssw_regex(cmssw_release):
            raise BadAttributeException('Invalid CMSSW release')

        input_dataset = self.get('input_dataset')
        if input_dataset and not self.dataset_regex(input_dataset):
            raise BadAttributeException('Invalid input dataset')

        pileup_dataset_name = self.get('pileup_dataset_name')
        if pileup_dataset_name and not self.dataset_regex(pileup_dataset_name):
            raise BadAttributeException('Invalid pileup dataset name')

        status = self.get('status')
        if status not in ('started', 'stopped'):
            raise BadAttributeException('Invalid status')

        campaign_type = self.get('type')
        if campaign_type and campaign_type not in ('LHE', 'Prod', 'MCReproc'):
            raise BadAttributeException('Invalid campaign type')

        keep_output = self.get('keep_output')
        sequences = self.get('sequences')
        if sorted(list(keep_output.keys())) != sorted(list(sequences.keys())):
            raise BadAttributeException('Different dictionaries for keep output and sequences')

        for name, group in sequences.items():
            if name not in keep_output:
                raise BadAttributeException(f'Missing keep output for "{name}"')

            if len(group) != len(keep_output[name]):
                raise BadAttributeException(f'Inconsistent sequences and keep output for "{name}"')

        return super().validate()

    def get_cmsdrivers(self):
        """
        Return a list of dictionaries of cmsDrivers
        """
        drivers = {}
        all_sequences = self.get_attribute('sequences')
        for sequence_name, sequences in all_sequences.items():
            drivers[sequence_name] = []
            for sequence_dict  in sequences:
                sequence = Sequence(sequence_dict)
                pileup_dataset_name = self.get_attribute('pileup_dataset_name')
                driver = sequence.get_cmsdriver('FRAGMENT', pileup_dataset_name, None)
                drivers[sequence_name].append(driver)

        return drivers

    def toggle_status(self):
        """
        Toggle campaign status between started and stopped
        """
        status = self.get_attribute('status')
        if status == 'started':
            new_status = 'stopped'
        elif status == 'stopped':
            # make a few checks here
            if self.get_attribute('energy') < 0:
                raise BadAttributeException('Cannot start a campaign with negative energy')
            if not self.get_attribute('cmssw_release'):
                raise BadAttributeException('Cannot start a campaign with no release')
            if not self.get_attribute('type'):
                raise BadAttributeException('Cannot start a campaign with no type')

            new_status = 'started'
        else:
            raise BadAttributeException(f'Unrecognized status "{status}"')

        prepid = self.get('prepid')
        self.logger.info('Toggling %s status to %s', prepid, new_status)
        self.set_attribute('status', new_status)
        self.update_history('set status', new_status)

    def is_started(self):
        """
        Return whether campaign is started
        """
        return self.get('status') == 'started'

    def get_editing_info(self):
        info = super().get_editing_info()
        info['cmssw_release'] = True
        info['energy'] = True
        info['events_per_lumi'] = True
        info['generators'] = True
        info['input_dataset'] = True
        info['keep_output'] = True
        info['memory'] = True
        info['notes'] = True
        info['pileup_dataset_name'] = True
        info['root'] = True
        info['sequences'] = True
        info['type'] = True
        info['www'] = True
        return info
