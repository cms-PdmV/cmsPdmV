import re
from couchdb_layer.mcm_database import database as Database
from json_layer.json_base import json_base
from json_layer.sequence import Sequence


class Campaign(json_base):

    _json_base__schema = {
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

    def validate(self):
        prepid = self.get('prepid')
        if not self.campaign_prepid_regex(prepid):
            raise Exception('Invalid campaign prepid')

        cmssw_release = self.get('cmssw_release')
        if cmssw_release and not self.cmssw_regex(cmssw_release):
            raise Exception('Invalid CMSSW release')

        input_dataset = self.get('input_dataset')
        if input_dataset and not self.dataset_regex(input_dataset):
            raise Exception('Invalid input dataset')

        pileup_dataset_name = self.get('pileup_dataset_name')
        if pileup_dataset_name and not self.dataset_regex(pileup_dataset_name):
            raise Exception('Invalid pileup dataset name')

        status = self.get('status')
        if status not in ('started', 'stopped'):
            raise Exception('Invalid status')

        campaign_type = self.get('type')
        if campaign_type and campaign_type not in ('LHE', 'Prod', 'MCReproc'):
            raise Exception('Invalid campaign type')

        keep_output = self.get('keep_output')
        sequences = self.get('sequences')
        if sorted(list(keep_output.keys())) != sorted(list(sequences.keys())):
            raise Exception('Different dictionaries for keep output and sequences')

        for name, group in sequences.items():
            if name not in keep_output:
                raise Exception('Missing keep output for %s' % (name))

            if len(group) != len(keep_output[name]):
                raise Exception('Different lengths of sequences and keep output for %s' % (name))

        return super().validate()

    def get_cmsdrivers(self):
        """
        Return a list of dictionaries of cmsDrivers
        """
        prepid = self.get_attribute('prepid')
        drivers = {}
        all_sequences = self.get_attribute('sequences')
        for sequence_name, sequences in all_sequences.items():
            drivers[sequence_name] = []
            sequence_count = len(sequences)
            for index, sequence_dict  in enumerate(sequences):
                sequence = Sequence(sequence_dict)
                sequence_args = {}
                # --fileout is campaign name and index for non-last sequence
                if index == sequence_count - 1:
                    sequence_args['fileout'] = 'file:%s.root' % (prepid)
                else:
                    sequence_args['fileout'] = 'file:%s_%s.root' % (prepid, index)

                # --filein by default is unset - some input.root filr
                sequence_args['filein'] = 'file:input.root'
                if index == 0:
                    # If input dataset is set, it is the input of first sequence
                    input_dataset = self.get_attribute('input_dataset')
                    if input_dataset:
                        sequence_args['filein'] = 'dbs:%s' % (input_dataset)
                else:
                    # For non-first sequences input is output of last sequence
                    sequence_args['filein'] = 'file:%s_%s.root' % (prepid, index - 1)

                pileup_dataset_name = self.get_attribute('pileup_dataset_name')
                if pileup_dataset_name:
                    pileup = sequence.get_attribute('pileup')
                    datamix = sequence.get_attribute('datamix')
                    # Classic mixing identified by the presence of --pileup
                    # Mixing using premixed events - absesence of --pileup and presence of --datamix
                    if (pileup and pileup != 'NoPileUp') or (not pileup and datamix == 'PreMix'):
                        sequence_args['pileup_input'] = 'dbs:%s' % (pileup_dataset_name)

                driver = sequence.get_cmsdriver('NameOfFragment', sequence_args)
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
                raise Exception('Cannot start a campaign with negative energy')
            if not self.get_attribute('cmssw_release'):
                raise Exception('Cannot start a campaign with no release')
            if not self.get_attribute('type'):
                raise Exception('Cannot start a campaign with no type')

            new_status = 'started'
        else:
            campaign_id = self.get_attribute('_id')
            raise Exception('Could not toggle status for %s' % (campaign_id))

        self.set_attribute('status', new_status)
        self.update_history('set status', new_status)

    def is_release_greater_or_equal_to(self, cmssw_release):
        my_release = self.get_attribute('cmssw_release')
        my_release = tuple(int(x) for x in re.sub('[^0-9_]', '', my_release).split('_') if x)
        other_release = tuple(int(x) for x in re.sub('[^0-9_]', '', cmssw_release).split('_') if x)
        # It only compares major and minor version, does not compare the build,
        # i.e. CMSSW_X_Y_Z, it compares only X and Y parts
        # Why? Because it was like this for ever
        my_release = my_release[:2]
        other_release = other_release[:2]
        return my_release >= other_release

    def is_started(self):
        """
        Return whether campaign is started
        """
        return self.get('status') == 'started'

    @classmethod
    def get_database(cls):
        """
        Return shared database instance
        """
        if not hasattr(cls, 'database'):
            cls.database = Database('campaigns')

        return cls.database
