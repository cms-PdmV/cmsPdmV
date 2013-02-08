#!/usr/bin/env python

from tools.logger import logger as logfactory

class json_base:
    __json = {}
    __approvalsteps = ['validation',  'define',  'approve', 'submit']
    __status = ['new',  'validation', 'defined',  'approved', 'submitted', 'done']
    logger = logfactory("prep2")


    class IllegalAttributeName(Exception):
        def __init__(self, attribute=None):
                self.logger = logfactory("prep2")
                self.__attribute = repr(attribute)
                json_base.logger.error('Invalid Json Format: Attribute \'' + self.__attribute + '\' is illegal')
        def __str__(self):
            return 'Invalid Json Format: Attribute \'' + self.__attribute + '\' is illegal'

    def __init__(self,  json={}):
        if json:
            self.__json = json
        self.__schema = {}  
   
    def update_history(self, history):
        hist = self.get_attribute('history')
        if not history:
            return
        hist.append(history)
        self.logger.log('Updating history...')
        self.set_attribute('history', hist)
        self.set_attribute('version', int(self.get_attribute('version')) + 1)
    
    def set_attribute(self,  attribute='',  value=None):
        if not attribute or attribute not in self.__schema:
            raise self.IllegalAttributeName(attribute)
            
        self.__json[attribute] = value
        return self.__json
    
    def get_attribute(self,  attribute=''):
        if not attribute or attribute not in self.__schema:
            raise self.IllegalAttributeName(attribute)
        return self.__json[attribute]
        
    def json(self):
        return self.__json
    
    def schema(self):
        return self.__schema
    
    def print_self(self):
        try:
            import json
        except ImportError as ex:
            self.logger.error('Error: Could not import "json" module')
            print self.__json
        print json.dumps(self.__json, indent=4)   
    
    def keys(self): 
        return self.__schema.keys()     

    def print_schema(self):
        print '{'
        for key in self.__json:
            print key, ': ',  self.__json[key],  '\t(',  type(self.__json[key]), ')'
        print '}'
    
    def get_approval_steps(self):
            return self.__approvalsteps
        
