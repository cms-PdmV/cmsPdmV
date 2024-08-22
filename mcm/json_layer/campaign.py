import re
from json_layer.json_base import json_base
from json_layer.sequence import sequence


class campaign(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'energy': -1.0,
        'type': '',
        'next': [],
        'cmssw_release': '',
        'input_dataset': '',
        'notes': '',
        'status': '',
        'pileup_dataset_name': '',
        'generators': [],
        'www': '',
        'events_per_lumi': {'singlecore': 100, 'multicore': 1000},  # default events per lumi for single core.
        # TO-DO: migrate existing campaigns to have the default value
        'root': 1,  # -1: possible root, 0: root, 1: non-root
        'sequences': [],  # list of jsons of jsons
        'history': [],
        'memory': 2000,
        'no_output': False}

    _json_base__status = ['stopped', 'started']

    _prepid_pattern = '[a-zA-Z0-9]{3,60}'

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}

        self._json_base__schema['status'] = self.get_status_steps()[0]

        # update self according to json_input
        self.update(json_input)
        self.validate()

    def build_cmsDrivers(self):
        cds = []
        for (stepindex, step) in enumerate(self.get_attribute('sequences')):
            stepcd = {}
            for key in step:
                seq = sequence(step[key])
                cdarg = seq.build_cmsDriver()
                fragment = 'NameOfFragment'
                if self.get_attribute('root') == 1:
                    fragment = 'step%d' % (stepindex + 1)
                if stepindex == 0:
                    if self.get_attribute('input_dataset'):
                        cdarg += " --filein dbs:%s" % self.get_attribute('input_dataset')
                    else:
                        cdarg += " --filein file:step%s.root" % (stepindex - 1)
                cdarg += " --fileout file:step%s.root" % stepindex
                # the classic mixing identified by the presence of --pileup ; this is untouched
                if self.get_attribute('pileup_dataset_name') and not (seq.get_attribute('pileup') in ['', 'NoPileUp']):
                    cdarg += ' --pileup_input "dbs:%s" ' % (self.get_attribute('pileup_dataset_name'))
                # the mixing using premixed events: absesence of --pileup and presence of datamix
                elif self.get_attribute('pileup_dataset_name') and (seq.get_attribute('pileup') in ['']) and (seq.get_attribute('datamix') in ['PreMix']):
                    cdarg += ' --pileup_input "dbs:%s" ' % (self.get_attribute('pileup_dataset_name'))
                cd = 'cmsDriver.py %s %s' % (fragment, cdarg)
                if cd:
                    stepcd[key] = cd
            cds.append(stepcd)
        return cds

    def add_request(self, req_json):
        from .request import request
        req = request(json_input=req_json)
        req.transfer_from(self)
        return req.json()

    def toggle_status(self):
        status_steps = self.get_status_steps()
        status = self.get_attribute('status')

        if status_steps.index(status) == 1:
            self.set_status(0)
        elif status_steps.index(status) == 0:
            # make a few checks here
            if self.get_attribute('energy') < 0:
                raise Exception('Cannot start a campaign with negative energy')
            if not self.get_attribute('cmssw_release'):
                raise Exception('Cannot start a campaign with no release')
            if not self.get_attribute('type'):
                raise Exception('Cannot start a campaign with no type')

            self.set_status(1)
        else:
            campaign_id = self.get_attribute('_id')
            raise NotImplementedError('Could not toggle status for %s' % (campaign_id))

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
