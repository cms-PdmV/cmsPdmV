#!/usr/bin/env python

import cherrypy
from tools.logger import logfactory
from tools.user_management import authenticator, user_pack
from tools.communicator import communicator
from tools.settings import settings
from tools.locker import locker
from couchdb_layer.mcm_database import database

class json_base:
    __json = {}
    __approvalsteps = ['none', 'validation', 'define', 'approve', 'submit']
    __status = ['new', 'validation', 'defined', 'approved', 'submitted', 'done']
    __schema = {}
    logger = logfactory

    class WrongApprovalSequence(Exception):
        def __init__(self, status, approval, message=''):
            self.text = 'It is illegale to approve %s in status %s. %s' % (approval, status, message)
            json_base.logger.error(self.text)

        def __str__(self):
            return self.text

    class WrongStatusSequence(Exception):
        def __init__(self, status, approval, message=''):
            self.text = 'It is illegale to change status %s in approval %s. %s' % (status, approval, message)
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
        def __init__(self, step=None):
            self.__step = repr(step)
            json_base.logger.error('Illegal approval step: %s' % (self.__step))

        def __str__(self):
            return 'Illegal Approval Step: ' + self.__step

    class IllegalStatusStep(Exception):
        def __init__(self, step=None):
            self.__step = repr(step)
            json_base.logger.error('Illegal Status: %s' % (self.__step))

        def __str__(self):
            return 'Illegal Status: ' + self.__step

    def __init__(self, json=None):
        json = json if json else {}
        if json:
            self.__json = json

    def setup(self):
        self.com = communicator()

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

    def reload(self):
        """
        Updates or creates document in database with name db_name
        and reloads the object with info from database (new revision)
        """
        try:
            if self.__class__.__name__ =="batch":
                db = database(self.__class__.__name__ + "es")
            else:
                db = database(self.__class__.__name__ + "s")
        except (database.DatabaseNotFoundException, database.DatabaseAccessError) as ex:
            self.logger.error("Problem with database creation:\n{0}".format(ex))
            return False
        with locker.lock(self.get_attribute('_id')):
            if not db.document_exists(self.get_attribute('_id')):
                saved = db.save(self.json())
            else:
                saved = db.update(self.json())
            if not saved:
                return False
            self.__init__(db.get(self.get_attribute('_id')))
            return True

    def update(self, json_input):
        self._json_base__json = {}
        if not json_input:
            self._json_base__json = self._json_base__schema
        else:
            for key in self._json_base__schema:
                if key in json_input:
                    try:
                        if type(self._json_base__schema[key]) is int:
                            self._json_base__json[key] = int(float(json_input[key]))
                        else:
                            self._json_base__json[key] = type(self._json_base__schema[key])(json_input[key])
                    except:
                        self._json_base__json[key] = json_input[key]
                else:
                    self._json_base__json[key] = self._json_base__schema[key]
            if '_rev' in json_input:
                self._json_base__json['_rev'] = json_input['_rev']

    def update_history(self, history):
        hist = self.get_attribute('history')
        ## in case there was an issue with the history initialisation
        if not hist:
            hist=[]
        if not history:
            return

        # get the updater's details and exact time and date
        history['updater'] = self.__get_submission_details()

        hist.append(history)
        self.set_attribute('history', hist)

        ## there is really no need to update the version number here.
        # the version number is meant for when we have resubmission and stuff !
        #if 'version' in self.__json:
        #    self.set_attribute('version', int(self.get_attribute('version')) + 1)

    def __get_submission_details(self):
        user_p = user_pack(db=True)
        if user_p.get_username() and user_p.get_fullname() and user_p.get_email():
            return submission_details().build(user_p.get_username(), user_p.get_fullname(), user_p.get_email())
        return submission_details().build('automatic')

    def set_attribute(self, attribute='', value=None):
        if not attribute or attribute not in self.__schema:
            raise self.IllegalAttributeName(attribute)

        self.__json[attribute] = value
        return self.__json

    def get_attribute(self, attribute=''):
        if not attribute or attribute not in self.__schema:
            raise self.IllegalAttributeName(attribute)
        return self.__json[attribute]

    def get_current_user_role_level(self):
        auth = authenticator()
        updater_user = self.__get_submission_details()
        updater = updater_user['author_username']
        self.current_user = None
        if updater != 'automatic':
            self.current_user = updater
        self.current_user_email = updater_user['author_email']
        self.current_user_level, self.current_user_role = auth.get_user_role_index(updater)
        #return self.current_user_level

    def get_actors(self, N=-1, what='author_username', Nchild=-1):
        actors = []
        #that's a way of removing history ...
        ban = ['nnazirid', 'automatic']
        for (n, step) in enumerate(self.get_attribute('history')):
            ## stop when asked
            if N > 0 and N == n:
                break
            try:
                if not step['updater']['author_username'] in ban:
                    actors.append(step['updater'][what])
            except:
                pass
        return list(set(actors))


    def approve(self, step=-1, to_approval=None):
        if 'approval' not in self.__schema:
            raise NotImplementedError('Could not approve object %s' % (self.__json['_id']))

        if to_approval:
            if not to_approval in self.__approvalsteps:
                self.logger.error(
                    'cannot set approval to %s because it is unknown %s allowed' % (to_approval, self.__approvalsteps))
            else:
                #override step, whatever it is
                step = self.__approvalsteps.index(to_approval)

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
            raise self.IllegalApprovalStep(next_step)

        ## already in the next step
        if self.__json['approval'] == self.__approvalsteps[next_step]:
            return
            #raise self.IllegalApprovalStep(self.__json['approval'])

        ## move the approval field along, so that in the history, it comes before the status change
        self.__json['approval'] = self.__approvalsteps[next_step]
        self.update_history({'action': 'approve', 'step': self.__json['approval']})

        ## is it allowed to move on
        fcn = 'ok_to_move_to_approval_%s' % (self.__approvalsteps[next_step])
        if hasattr(self, fcn):
            #self.logger.log('Calling %s '%(fcn))
            ## that function should through if not approvable
            getattr(self, fcn)()
            self.notify('Approval %s for %s %s' % (self.__approvalsteps[next_step],
                                                   self.__class__.__name__,
                                                   self.get_attribute('prepid')),
                        self.textified(),
                        accumulate=True
            )

    def textified(self):
        return 'no body'

    def set_status(self, step=-1, with_notification=False, to_status=None):
        if 'status' not in self.__schema:
            raise NotImplementedError('Could not approve object %s' % (self.__json['_id']))

        #self.logger.log('Updating to step %s'%(step))
        next_step = 0
        if to_status:
            if not to_status in self.__status:
                self.logger.error(
                    'cannot set status to %s because it is unknown %s allowed' % (to_status, self.__status))
            else:
                #override step, whatever it is
                step = self.__status.index(to_status)

        if step < 0: # not specified: move to next logical status
            lst = self.__json['status']
            next_step = self.__status.index(lst) + 1
        elif step >= len(self.__status): # specified outside boundary
            raise self.IllegalStatusStep(step)
        else:
            #specified
            next_step = step

        if next_step == len(self.__status):
            self.logger.error(
                'Updating to step %s means going to the last status or %s' % (next_step, str(self.__status)))
            return

        if self.__json['status'] == self.__status[next_step]:
            return

        #self.logger.log('Updating the status for object %s to %s...' % (self.get_attribute('_id'), self.__status[next_step]))
        if with_notification:
            self.notify(
                'Status changed for request %s to %s' % (self.get_attribute('prepid'), self.__status[next_step]),
                self.textified(),
                accumulate=True)

        self.__json['status'] = self.__status[next_step]
        self.update_history({'action': 'set status', 'step': self.__json['status']})

    def add_comment(self, comment=''):
        if not comment:
            return
        comm = {'action': 'comment', 'step': comment}
        self.update_history(comm)

        return comm

    def json(self):
        return self.__json

    def schema(self):
        return self.__schema

    @classmethod
    def class_schema(cls):
        return cls.__schema

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
            print key, ': ', self.__json[key], '\t(', type(self.__json[key]), ')'
        print '}'

    def get_approval_steps(self):
        return self.__approvalsteps

    def get_status_steps(self):
        return self.__status

    def notify(self,
               subject, message,
               who=[],
               actors=True,
               service=True,
               HN=False,
               sender = None,
               Nchild=-1,
               reply_msg_ID=None,
               accumulate=False):

        dest = map(lambda i: i, who)
        if actors:
            #add the actors to the object
            dest.extend(self.get_actors(what='author_email',Nchild=Nchild))
        if service:
            #let the service know at any time
            dest.append(settings().get_value('service_account'))
        if HN:
            ## back bone HN notification ?
            dest.append(settings().get_value('hypernews_test'))

        #be sure to not have duplicates
        dest = list(set(dest))

        if not len(dest):
            dest.append(settings().get_value('service_account'))
            subject += '. And no destination was set'

        sender = sender if sender else self.current_user_email
        self.logger.log('Notification %s from %s send to %s' % (subject, sender,', '.join(dest)))
        return self.com.sendMail(dest,
                                 subject,
                                 message,
                                 sender,
                                 reply_msg_ID,
                                 accumulate=accumulate)

    def correct_types(self):
        for key in self.__schema:
            if not isinstance(self.__json[key], type(self.__schema[key])):
                return False
        return True


class submission_details(json_base):
    def __init__(self, json_input={}):
        self._json_base__schema = {
            'author_username': '',
            'author_name': '',
            'author_email': '',
            'submission_date': '',
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
