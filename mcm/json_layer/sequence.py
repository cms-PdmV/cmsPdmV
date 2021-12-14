import json
from json_base import json_base
from copy import deepcopy
from pipes import quote as shell_quote


class Sequence(json_base):

    _json_base__schema = {"beamspot": "",
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

    def get_cmsdriver(self, fragmant_name, update_dict):
        """
        Build a cmsDriver command
        """
        arguments = deepcopy(self.json())
        # Always --mc
        arguments['mc'] = True
        # Always --noexec
        arguments['no_exec'] = True
        arguments.update(update_dict)
        command = 'cmsDriver.py'
        if fragmant_name:
            command += ' %s' % (fragmant_name)

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

            value = shell_quote(value) if value else value
            command += (' --%s=%s' % (key, value)).rstrip(' =')

        extra_value = arguments.get('extra')
        if extra_value:
            command += ' %s' % (shell_quote(extra_value))

        return command

    def to_string(self):
        return json.dumps(self.json(), sort_keys=True)
