#!/usr/bin/env python

class json_base:
    __json = {}
    class IllegalAttributeName(Exception):
        def __init__(self, attribute=None):
                self.__attribute = repr(attribute)
        def	__str__(self):
            return 'Invalid Json Format: Attribute \'' + self.__attribute + '\' is illegal'
    
    def __init__(self,  json={}):
        if json:
            self.__json = json
        self.__schema = {}	
    
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
            import simplejson
        except ImportError as ex:
            print 'Error: Could not import json module'
            print self.__json
        print simplejson.dumps(self.__json, indent=4)	
	
    def keys(self):	
        return self.__schema.keys() 	

    def print_schema(self):
        print '{'
        for key in self.__json:
            print key, ': ',  self.__json[key],  '\t(',  type(self.__json[key]), ')'
        print '}'
