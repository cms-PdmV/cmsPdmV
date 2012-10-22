#!/usr/bin/env python

from json_base import json_base

class sequence(json_base):
    def __init__(self,  json_input={}):
        self._json_base__schema = {
            'index':-1,
            'step':'', 
            'beamspot':'', 
            'geometry':'', 
            'magnetic_field':'', 
            'conditions':[], 
            'pileup_scenario':[], 
            'datamixer_scenario':[], 
            'scenario':'', 
            'customize_name':'',
            'customize_function':'',
            'slhc':'', 
            'event_content':[],
            'data_tier':[], 
            'customize_name':'',
            'customize_function':'',
            'sequence':[] }

        # update self according to json_input
        self.__update(json_input)
        self.__validate()

    def __validate(self):
        if not self._json_base__json:
            return 
        for key in self._json_base__schema:
            if key not in self._json_base__json:
                raise self.IllegalAttributeName(key)
    
    # for all parameters in json_input store their values 
    # in self._json_base__json
    def __update(self,  json_input):
        self._json_base__json = {}
        if not json_input:
            self._json_base__json = self._json_base__schema
        else:
            for key in self._json_base__schema:
                if key in json_input:
                    self._json_base__json[key] = json_input[key]
                else:
                    self._json_base__json[key] = self._json_base__schema[key]

    def build(self,  customize_name=[],  customize_function=[],  sequence=''):
        self.set_attribute('customize_name',  customize_name)
        self.set_attribute('customize_function',  customize_function)
        self.set_attribute('sequence',  sequence)
        return self._json_base__json
    
if __name__=='__main__':
    s = sequence()
    s.print_self()
