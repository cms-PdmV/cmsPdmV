#!/usr/bin/env python

from json_base import json_base
from json_base import submission_details

class generator_parameters(json_base):
            
    #def __init__(self, author_name,  author_cmsid=-1,   author_inst_code='',  author_project='', json_input={} ):
    def __init__(self, json_input={}):
        self._json_base__schema = {
            'version':0, 
            #'submission_details':submission_details().build(author_name,  author_cmsid,  author_inst_code,  author_project), 
            'submission_details':self._json_base__get_submission_details(),
            'cross_section':-1.0,
            'filter_efficiency':-1.0,
            'filter_efficiency_error':-1.0,
            'match_efficiency':-1.0,
            'match_efficiency_error':-1.0               
            }
        # update self according to json_input
        self.update(json_input)
        self.validate()

    def isInValid(self):
        for (k,v) in self._json_base__json.items():
            if len(k)>=4 and k[0:5] in ['cross','filte','match'] and v<0:
                return True
            if 'efficiency' in k and v>1. or v==0:
                return True
        return False

"""
    def __validate(self):
        if not self._json_base__json:
            return 
        for key in self._json_base__schema:
            if key not in self._json_base__json:
                raise self.IllegalAttributeName(key)
    
    # for all parameters in json_input store their values 
    # in self._json_base__json
    def __update(self,  json_input):
        if not json_input:
            self._json_base__json = self._json_base__schema
        else:
            for key in self._json_base__schema:
                if key in json_input:
                    self._json_base__json[key] = json_input[key]
                else:
                    self._json_base__json[key] = self._json_base__schema[key]  
"""
    
    #def build(self, cross_section=-1.0,filter_efficiency=-1.0,filter_efficiency_error=-1.0,match_efficiency=-1.0, match_efficiency_error=-1.0):
    #    self.set_attribute('cross_section',  cross_section)
    #    self.set_attribute('filter_efficiency',  filter_efficiency)
    #    self.set_attribute('filter_efficiency_error',  filter_efficiency_error)
    #    self.set_attribute('match_efficiency',  match_efficiency)
    #    self.set_attribute('match_efficiency_error', match_efficiency_error)
    #    return self._json_base__json
        
if __name__=='__main__':
    g = generator_parameters(' ')
    g.print_self()
