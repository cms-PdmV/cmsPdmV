#!/usr/bin/env python

from json_base import json_base

class submission_details(json_base):

    def __init__(self,  json_input={}):
        self._json_base__schema = { 
            'author_cmsid':-1,
            'author_name':'',
            'author_inst_code':'',
            'submission_date':'',
            'author_project':'' 
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
            
    def __get_datetime(self):
        try:
            import time
        except ImportError as ex: 
            print 'Error while attempting to import time module.'
            print 'Returned: ' + str(ex)
                                                        
        localtime = time.localtime(time.time())
        
        datetime = ''
        for i in range(5):
            datetime += str(localtime[i]).zfill(2) + '-'
        return datetime.rstrip('-') 

    def build(self, author_name='automatic', author_cmsid=-1, author_inst_code='', author_project=''):
        self.set_attribute('author_name', author_name)
        self.set_attribute('author_cmsid', author_cmsid)
        self.set_attribute('author_inst_code', author_inst_code)
        self.set_attribute('author_project', author_project)
        self.set_attribute('submission_date', self.__get_datetime())
        return self._json_base__json
        
if __name__=='__main__':
    s = submission_details()
    s.print_self()
