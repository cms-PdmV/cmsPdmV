#!/usr/bin/env python

from json_base import json_base
from json_base import submission_details

class comment(json_base):
    def __init__(self, author_name,  author_cmsid=-1,   author_inst_code='',  author_project='',json_input={}):
        self._json_base__schema = {
            'submission_details':submission_details().build(author_name,  author_cmsid,  author_inst_code,  author_project), 
            'message':'' 
            }
            
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
                
    def build(self,  message):
        self.set_attribute('message',  message)
        return self._json_base__json
        
if __name__=='__main__':
    c = comment(' ')
    c.print_self()
