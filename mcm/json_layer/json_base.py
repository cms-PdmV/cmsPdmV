#!/usr/bin/env python

import cherrypy
from tools.logger import logger as logfactory
from tools.authenticator import authenticator

class json_base:
    __json = {}
    __approvalsteps = ['none','validation',  'define',  'approve', 'submit']
    __status = ['new',  'validation', 'defined',  'approved', 'submitted', 'done']
    logger = logfactory("prep2")

    class WrongApprovalSequence(Exception):
        def __init__(self,status,approval,message=''):
            self.text='It is illegale to approve %s in status %s. %s'%(approval,status,message)
            json_base.logger.error(self.text)
        def __str__(self):
            return self.text

    class WrongStatusSequence(Exception):
        def __init__(self,status,approval,message=''):
            self.text='It is illegale to change status %s in approval %s. %s'%(status,approval,message)
            json_base.logger.error(self.text)
        def __str__(self):
            return self.text

    class IllegalAttributeName(Exception):
        def __init__(self, attribute=None):
                self.__attribute = repr(attribute)
                json_base.logger.error('Invalid Json Format: Attribute \'' + self.__attribute + '\' is illegal')
        def __str__(self):
            return 'Invalid Json Format: Attribute \'' + self.__attribute + '\' is illegal'

    class IllegalApprovalStep(Exception):
        def __init__(self,  step=None):
            self.__step = repr(step)
            json_base.logger.error('Illegal approval step: %s' % (self.__step))
        def __str__(self):
            return 'Illegal Approval Step: ' + self.__step

    class IllegalStatusStep(Exception):
        def __init__(self,  step=None):
            self.__step = repr(step)
            json_base.logger.error('Illegal Status: %s' % (self.__step))
        def __str__(self):
            return 'Illegal Status: ' + self.__step


    def __init__(self,  json={}):
        if json:
            self.__json = json
        self.__schema = {}

    def validate(self):
        if not self.__json:
            return
        #looks for keys that are missing, from the schema requirement
        for key in self.__schema:
            if key not in self.__json:
                raise self.IllegalAttributeName(key)

        ##JR: how to test exactness of information
        #look for keys that are in extras to the schema requirement
        #for key in self.__json:
        #    if key not in self.__schema:
        #        json_base.logger.error('Parameter %s is not mandatory anymore: removing ?'%(key))


    def update(self,  json_input):
        self._json_base__json = {}
        if not json_input:
            self._json_base__json = self._json_base__schema
        else:
            for key in self._json_base__schema:
                if key in json_input:
                    try:
                        self._json_base__json[key] = type(self._json_base__schema[key])(json_input[key])
                    except:
                        self._json_base__json[key]  = json_input[key]
                else:
                    self._json_base__json[key] = self._json_base__schema[key]
            if '_rev' in json_input:
                self._json_base__json['_rev'] = json_input['_rev']

   
    def update_history(self, history):
        hist = self.get_attribute('history')
        if not history:
            return

        # get the updater's details and exact time and date
        history['updater'] = self.__get_submission_details()

        hist.append(history)
        self.set_attribute('history', hist)

        if 'version' in self.__json:
            self.set_attribute('version', int(self.get_attribute('version')) + 1)

    def __get_submission_details(self):
        if cherrypy.request.headers:
            if 'ADFS-LOGIN' in cherrypy.request.headers and 'ADFS-FIRSTNAME' in cherrypy.request.headers and 'ADFS-LASTNAME' in cherrypy.request.headers and 'ADFS-EMAIL' in cherrypy.request.headers:
                return submission_details().build(author_username=cherrypy.request.headers['ADFS-LOGIN'], author_name='%s %s' % (cherrypy.request.headers['ADFS-FIRSTNAME'], cherrypy.request.headers['ADFS-LASTNAME']), author_email=cherrypy.request.headers['ADFS-EMAIL']) 
        return submission_details().build('automatic')
    
    def set_attribute(self,  attribute='',  value=None):
        if not attribute or attribute not in self.__schema:
            raise self.IllegalAttributeName(attribute)
            
        self.__json[attribute] = value
        return self.__json
    
    def get_attribute(self,  attribute=''):
        if not attribute or attribute not in self.__schema:
            raise self.IllegalAttributeName(attribute)
        return self.__json[attribute]

    def get_current_user_role_level(self):
        auth =authenticator()
        updater_user=self._json_base__get_submission_details()
        updater=updater_user['author_username']
        self.current_user =None
        if updater != 'automatic':
            self.current_user = updater
        self.current_user_email = updater_user['author_email']
        self.current_user_level,self.current_user_role=auth.get_user_roles_index(updater)
        #return self.current_user_level

    def get_actors(self,N=-1,what='author_username'):
        actors=[]
        for (n,step) in enumerate(self.get_attribute('history')):
            ## stop when asked
            if N>0 and N==n: 
                break
            try:
                actors.append(step['updater'][what])
            except:
                pass
        return list(set(actors))



    def approve(self, step=-1):
        if 'approval' not in self.__schema:
            raise NotImplementedError('Could not approve object %s' % (self.__json['_id']))

        next_step = 0
        if step < 0:
            lapp = self.__json['approval']
            next_step = self.__approvalsteps.index(lapp) + 1
        elif step >= len(self.__approvalsteps):
            raise self.IllegalApprovalStep(step)
        else:
            next_step = step

        ## if at the end of the change
        if next_step == len(self.__approvalsteps):
            return

        ## already in the next step
        if self.__json['approval'] == self.__approvalsteps[next_step]:
            return
        
        ## is it allowed to move on
        fcn='ok_to_move_to_approval_%s'%(self.__approvalsteps[next_step])
        if hasattr(self,fcn):
            self.logger.log('Calling %s '%(fcn))
            ## that function should through if not approvable
            getattr(self,fcn)()

        self.__json['approval'] = self.__approvalsteps[next_step]
        self.update_history({'action':'approve', 'step':self.__json['approval']})

    def set_status(self, step=-1,to_status=None):
        if 'status' not in self.__schema:
            raise NotImplementedError('Could not approve object %s' % (self.__json['_id']))

        next_step = 0
        if step < 0:
            lst = self.__json['status']
            next_step = self.__status.index(lst) + 1
        elif step >= len(self.__status):
            raise self.IllegalStatusStep(step)
        else:
            next_step = step

        if next_step == len(self.__status):
            return

        if self.__json['status'] == self.__status[next_step]:
            return

        self.logger.log('Updating the status for object %s...' % (self.get_attribute('_id')))

        self.__json['status'] = self.__status[next_step]
        self.update_history({'action':'set status', 'step':self.__json['status']})


    def add_comment(self, comment=''):
        if not comment:
            return
        comm = {'action': 'comment', 'step': comment}
	self.update_history(comm)

        return comments
        
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

    def get_status_steps(self):
            return self.__status
        

class submission_details(json_base):

    def __init__(self,  json_input={}):
        self._json_base__schema = { 
            'author_username':'',
            'author_name':'',
            'author_email':'',
            'submission_date':'',
            }   
    
        # update self according to json_input
        self.update(json_input)
        self.validate()

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

    def build(self, author_username='automatic', author_name='', author_email=''):
        self.set_attribute('author_name', author_name)
        self.set_attribute('author_username', author_username)
        self.set_attribute('author_email', author_email)
        self.set_attribute('submission_date', self.__get_datetime())
        return self._json_base__json

