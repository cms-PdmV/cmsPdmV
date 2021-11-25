#!/usr/bin/env python

from json_base import json_base
from json_base import submission_details


class generator_parameters(json_base):

    _json_base__schema = {
        'version': 0,
        #'submission_details':submission_details().build(author_name,  author_cmsid,  author_inst_code,  author_project),
        'submission_details': '',
        'cross_section': -1.0,
        'filter_efficiency': -1.0,
        'filter_efficiency_error': -1.0,
        'match_efficiency': -1.0,
        'match_efficiency_error': -1.0,
        'negative_weights_fraction': -1.0
    }

    #def __init__(self, author_name,  author_cmsid=-1,   author_inst_code='',  author_project='', json_input={} ):
    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}
        self._json_base__schema['submission_details'] = self._json_base__get_submission_details()
        # update self according to json_input
        self.update(json_input)
        self.validate()

    def isInValid(self):
        for (k,v) in self._json_base__json.items():
            if len(k)>=4 and k[0:5] in ['cross','filte','match'] and v<0:
                return True
            if 'efficiency' in k and v>1.:
                return True
            if 'efficiency' in k and not 'error' in k and v==0:
                return True
        return False
