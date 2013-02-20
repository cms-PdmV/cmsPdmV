#!/usr/bin/env python

from json_layer.json_base import json_base

class submission_details(json_base):

    def __init__(self,  json_input={}):
        self._json_base__schema = { 
            'author_username':'',
            'author_name':'',
            'author_email':'',
            'submission_date':'',
            }
                
        # update self according to json_input
        self.__update(json_input)
        self.__validate()

    def __get_datetime(self):
        try:
            import time
        except ImportError as ex: 
            self.logger.error('Could not import "time" module. Returned: %s' % (ex), level='critical')    
                                                        
        localtime = time.localtime(time.time())
        
        datetime = ''
        for i in range(5):
            datetime += str(localtime[i]).zfill(2) + '-'
        return datetime.rstrip('-') 

    def build(self, author_name='automatic', author_username='', author_email=''):
        self.set_attribute('author_name', author_name)
        self.set_attribute('author_username', author_username)
        self.set_attribute('author_email', author_email)
        self.set_attribute('submission_date', self.__get_datetime())
        return self._json_base__json
