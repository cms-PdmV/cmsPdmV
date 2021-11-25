import logging
import traceback
import re

from tools.user_management import authenticator, user_pack
from tools.communicator import communicator
import tools.settings as settings
from tools.locker import locker
from couchdb_layer.mcm_database import database
from copy import deepcopy
from tools.user_management import access_rights

class json_base:
    __json = {}
    __approvalsteps = []
    __status = []
    __schema = {}
    __database = None
    logger = logging.getLogger("mcm_error")

    def __init__(self, json_input=None):
        if not json_input:
            # If no data is provided, use default values from schema
            json_input = self.schema()

        self.__json = deepcopy(json_input)

    def validate(self):
        if not self.__json:
            return

        for key in self.__schema:
            if key not in self.__json:
                raise Exception('Missing attribute "%s"' % (key))

    @classmethod
    def get_database(cls):
        return cls.__database

    def reload(self, save_current=True):
        """
        Save and reload the object from database
        """
        object_id = self.get_attribute('_id')
        database = self.get_database()
        with locker.lock(object_id):
            if save_current:
                if not self.save():
                    return False

            self.__init__(database.get(object_id))

        return True

    def save(self):
        """
        Updates or creates document in the database
        """
        object_id = self.get_attribute('_id')
        database = self.get_database()
        with locker.lock(object_id):
            if database.document_exists(object_id):
                return database.update(self.json())

            return database.save(self.json())

    def update(self, json_input):
        self._json_base__json = {}
        if not json_input:
            self._json_base__json = deepcopy(self._json_base__schema)
        else:
            for key in self._json_base__schema:
                if key in json_input:
                    try:
                        if type(self._json_base__schema[key]) is int:
                            self._json_base__json[key] = int(float(json_input[key]))
                        elif self._json_base__schema[key] is None:
                            self._json_base__json[key] = json_input[key]
                        else:
                            self._json_base__json[key] = type(self._json_base__schema[key])(json_input[key])
                    except Exception:
                        # do through a bad exception here !
                        # self._json_base__json[key] = json_input[key]
                        raise Exception("%s of type %s does not match the schema type %s" % (
                            key,
                            type(json_input[key]),
                            type(self._json_base__schema[key])))
                else:
                    self._json_base__json[key] = deepcopy(self._json_base__schema[key])
            if '_rev' in json_input:
                self._json_base__json['_rev'] = json_input['_rev']

    def update_history(self, history):
        hist = self.get_attribute('history')
        # in case there was an issue with the history initialisation
        if not hist:
            hist = []
        if not history:
            return

        # get the updater's details and exact time and date
        history['updater'] = self.__get_submission_details()

        hist.append(history)
        self.set_attribute('history', hist)

        # there is really no need to update the version number here.
        # the version number is meant for when we have resubmission and stuff !
        # if 'version' in self.__json:
        #     self.set_attribute('version', int(self.get_attribute('version')) + 1)

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

    def get_actors(self, N=-1, what='author_username', Nchild=-1):
        actors = []
        # that's a way of removing history ...
        ban = ['nnazirid', 'automatic']
        for (n, step) in enumerate(self.get_attribute('history')):
            # stop when asked
            if N > 0 and N == n:
                break
            try:
                if not step['updater']['author_username'] in ban:
                    actors.append(step['updater'][what])
            except Exception:
                pass
        return list(set(actors))

    def approve(self, step=-1, to_approval=None):
        if 'approval' not in self.__schema:
            raise NotImplementedError('Could not approve object %s' % (self.__json['_id']))

        if to_approval:
            if to_approval not in self.__approvalsteps:
                self.logger.error('cannot set approval to %s because it is unknown %s allowed' % (to_approval, self.__approvalsteps))
            else:
                # override step, whatever it is
                step = self.__approvalsteps.index(to_approval)

        next_step = 0
        if step < 0:
            lapp = self.__json['approval']
            next_step = self.__approvalsteps.index(lapp) + 1
        elif step >= len(self.__approvalsteps):
            raise self.IllegalApprovalStep(step)
        else:
            next_step = step

        # if at the end of the change
        if next_step == len(self.__approvalsteps):
            raise self.IllegalApprovalStep(next_step)

        # already in the next step
        if self.__json['approval'] == self.__approvalsteps[next_step]:
            return
            # raise self.IllegalApprovalStep(self.__json['approval'])

        # move the approval field along, so that in the history, it comes before the status change
        self.__json['approval'] = self.__approvalsteps[next_step]
        self.update_history({'action': 'approve', 'step': self.__json['approval']})

    def textified(self):
        return 'no body'

    def set_status(self, step=-1, to_status=None):
        if 'status' not in self.__schema:
            raise NotImplementedError('Could not approve object %s' % (self.__json['_id']))

        next_step = 0
        if to_status:
            if to_status not in self.__status:
                self.logger.error('cannot set status to %s because it is unknown %s allowed' % (to_status, self.__status))
            else:
                # override step, whatever it is
                step = self.__status.index(to_status)

        if step < 0:  # not specified: move to next logical status
            lst = self.__json['status']
            next_step = self.__status.index(lst) + 1
        elif step >= len(self.__status):  # specified outside boundary
            raise self.IllegalStatusStep(step)
        else:
            # specified
            next_step = step

        if next_step == len(self.__status):
            self.logger.error('Updating to step %s means going to the last status or %s' % (next_step, str(self.__status)))
            return

        if self.__json['status'] == self.__status[next_step]:
            return

        self.__json['status'] = self.__status[next_step]
        self.update_history({'action': 'set status', 'step': self.__json['status']})

    def json(self):
        return self.__json

    def schema(self):
        return self.__schema

    @classmethod
    def class_schema(cls):
        return cls.__schema

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
               sender=None,
               Nchild=-1,
               reply_msg_ID=None,
               accumulate=False):

        dest = map(lambda i: i, who)
        if actors:
            auth = authenticator()
            # add the actors to the object
            for history_entry in self.get_attribute('history'):
                username = history_entry.get('updater', {}).get('author_username')
                if not username:
                    continue

                email = history_entry.get('updater', {}).get('author_email')
                if not email:
                    continue

                if email in dest:
                    # No need to chech the same person again
                    continue

                action = history_entry.get('action')
                if not action:
                    continue

                user_level, user_role = auth.get_user_role_index(username)
                if user_level == access_rights.user and action != 'register':
                    continue

                dest.append(email)

        if service:
            # let the service know at any time
            dest.append(settings.get_value('service_account'))
        if HN:
            # back bone HN notification ?
            dest.append(settings.get_value('hypernews_test'))

        # be sure to not have duplicates
        dest = set(dest)
        exclude_emails = set(settings.get_value('exclude_from_notify'))
        dest = list(dest - exclude_emails)
        if not len(dest):
            dest.append(settings.get_value('service_account'))
            subject += '. And no destination was set'

        sender = sender if sender else self.current_user_email
        self.logger.info('Notification %s from %s send to %s [acc:%s]' % (subject, sender, ', '.join(dest), accumulate))

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

    def get_ds_input(self, __output_dataset, __seq):
        try:
            input_ds = ""
            possible_dt_inputs = settings.get_value('datatier_input')
            # we take sequence 1step datetier
            # check if "step" is a string -> some DR requests has single step string with , in it...
            # some DR requests has it.... most probably the generated ones

            if isinstance(__seq[0]["step"], basestring):
                __step = __seq[0]["step"].split(",")[0].split(":")[0]
            else:
                __step = __seq[0]["step"][0].split(":")[0]

            if __step in possible_dt_inputs:
                __possible_inputs = possible_dt_inputs[__step]
                # highest priority is first.. we should take acording output_ds
                __prev_output = __output_dataset
                __prev_tiers = [el.split("/")[-1] for el in __prev_output]

                for elem in __possible_inputs:
                    if elem in __prev_tiers:
                        input_ds = __prev_output[__prev_tiers.index(elem)]
                        # dirty stuff
                        # self.logger.info("get_ds_input found a possible DS: %s" % (input_ds))
                        # self.logger.info("get_ds_input\t elem: %s __possible_inputs %s" % (elem, __possible_inputs))
                        break
            else:
                # if step is not defined in dictionary -> we default to previous logic
                input_ds = __output_dataset[0]
            # if we didn't find anything in for loop above, fall back to previous
            if not input_ds:
                if len(__output_dataset) > 0:
                    # in case the output_dataset is ""
                    input_ds = __output_dataset[0]

            self.logger.info("get_ds_input returns input_ds: %s" % (input_ds))
            return input_ds
        except Exception:
            self.logger.error("Error looking for input dataset: %s" % (traceback.format_exc()))
            return ""

    def fullmatch(self, pattern, string):
        return re.match("(?:" + pattern + r")\Z", string)


class submission_details(json_base):
    def __init__(self, json_input={}):
        self._json_base__schema = {
            'author_username': '',
            'author_name': '',
            'author_email': '',
            'submission_date': '',}

        # update self according to json_input
        self.update(json_input)
        self.validate()

    def __get_datetime(self):
        try:
            import time
        except ImportError as ex:
            self.logger.error('Could not import "time" module. Returned: %s' % (ex))

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
