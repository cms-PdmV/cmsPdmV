import json
from copy import deepcopy
from shlex import quote as shell_quote
from json_layer.model_base import ModelBase


class Sequence(ModelBase):

    _ModelBase__schema = {"beamspot": "",
                          "conditions": "",
                          "custom_conditions": "",
                          "customise": "",
                          "customise_commands": "",
                          "datamix": "",
                          "datatier": [],
                          "donotDropOnInput": "",
                          "dropDescendant": False,
                          "era": "",
                          "eventcontent": [],
                          "extra": "",
                          "filtername": "",
                          "geometry": "",
                          "gflash": "",
                          "harvesting": "",
                          "himix": False,
                          "hltProcess": "",
                          "index": -1,
                          "inline_custom": False,
                          "inputCommands": "",
                          "inputEventContent": "",
                          "magField": "",
                          "nStreams": 0,
                          "nThreads": 1,
                          "outputCommand": "",
                          "particle_table": "",
                          "pileup": "",
                          "procModifiers": "",
                          "processName": "",
                          "repacked": "",
                          "restoreRNDSeeds": "",
                          "runsAndWeightsForMC": "",
                          "runsScenarioForMC": "",
                          "scenario": "",
                          "slhc": "",
                          "step": [],
                          "triggerResultsProcess": ""}

    def get_cmsdriver(self, fragment_name, pileup_dataset_name, update_dict):
        """
        Build a cmsDriver command
        """
        arguments = deepcopy(self.json())
        # Always --mc
        arguments['mc'] = True
        # Always --noexec
        arguments['no_exec'] = True
        if update_dict:
            arguments.update(update_dict)

        command = 'cmsDriver.py'
        if fragment_name:
            command += f' {fragment_name}'

        pileup = arguments.get('pileup')
        datamix = arguments.get('datamix')
        if pileup_dataset_name:
            if (pileup and pileup != 'NoPileUp') or (not pileup and datamix == 'PreMix'):
                arguments['pileup_input'] = f'dbs:{pileup_dataset_name}'

        for key in sorted(arguments.keys()):
            if key in ('index', 'extra'):
                continue

            value = arguments[key]
            if not value:
                continue

            if key == 'nThreads' and int(value) <= 1:
                # Do not add nThreads if it's <= 1
                continue

            if key == 'nStreams' and int(value) <= 0:
                # Do not add nStreams if it's <= 0
                continue

            if isinstance(value, bool):
                value = ''
            elif isinstance(value, list):
                value = ','.join(str(x) for x in value)
            elif not isinstance(value, str):
                value = str(value)

            command += (' --%s=%s' % (key, value)).rstrip(' =')

        extra_value = arguments.get('extra')
        if extra_value:
            command += ' %s' % (shell_quote(extra_value))

        return command

    def to_string(self):
        return json.dumps(self.json(), sort_keys=True)
