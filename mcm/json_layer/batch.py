import re

from couchdb_layer.mcm_database import database
from json_layer.json_base import json_base
from tools.locator import locator
import tools.settings as settings
from json_layer.notification import notification

class batch(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'history': [],
        'notes': '',
        'status': '',
        'requests': [],
        'extension': 0,
        'process_string': '',
        'message_id': '',
        'version': 0
    }

    _json_base__status = ['new', 'being_announced', 'announced', 'done']

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}
        self._json_base__schema['status'] = self.get_status_steps()[0]
        self.setup()
        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()

    def remove_request(self, rid):
        b_requests = self.get_attribute('requests')
        b_requests = filter(lambda r: r['content']['pdmv_prep_id'] != rid, b_requests)
        self.set_attribute('requests', b_requests)
        self.reload()

    def add_requests(self, a_list):
        b_requests = self.get_attribute('requests')
        b_requests.extend(a_list)
        # sort them
        b_requests = sorted(b_requests, key=lambda d: d['content']['pdmv_prep_id'])
        self.set_attribute('requests', b_requests)

    def add_notes(self, notes):
        b_notes = self.get_attribute('notes')
        b_notes += notes
        self.set_attribute('notes', b_notes)

    def get_subject(self, added=""):

        (campaign, batchNumber) = self.get_attribute('prepid').split('_')[-1].split('-')
        if self.get_attribute('prepid').split('_')[0] == 'Task':  # convention for taskchain
            rdb = database('requests')
            campaigns = set()
            for r in self.get_attribute('requests'):
                pid = r['content']['pdmv_prep_id']
                mcm_r = rdb.get(pid)
                campaigns.add(mcm_r['member_of_campaign'])

            subject = "New %s production, batch %d" % (','.join(campaigns), int(batchNumber))
        else:
            subject = "New %s production, batch %d" % (campaign, int(batchNumber))

        if self.get_attribute('version'):
            subject += ', Resubmission'
        if self.get_attribute('extension'):
            subject += ', Extension'
        if self.get_attribute('process_string'):
            subject += ', (%s)' % (self.get_attribute('process_string'))
        if added:
            subject += " " + added

        return subject

    def announce(self, notes="", user=""):
        if self.get_attribute('status') != 'new':
            return False
        if len(self.get_attribute('requests')) == 0:
            return False

        # Toggle status to being_announced
        self.logger.info('Will announce %s' % (self.get_attribute('prepid')))
        self.set_status()
        self.logger.info('Batch "%s" status is %s' % (self.get_attribute('prepid'), self.get_attribute('status')))

        current_notes = self.get_attribute('notes')
        if current_notes:
            current_notes += '\n'
        if notes:
            current_notes += notes
            self.set_attribute('notes', current_notes)

        total_events = 0
        content = self.get_attribute('requests')
        total_requests = len(content)
        rdb = database('requests')

        # prepare the announcing message
        (campaign, batchNumber) = self.get_attribute('prepid').split('_')[-1].split('-')

        subject = self.get_subject()

        request_messages = {}

        for r in content:
            # loose binding of the prepid to the request name, might change later on
            if 'pdmv_prep_id' in r['content']:
                pid = r['content']['pdmv_prep_id']
            else:
                pid = r['name'].split('_')[1]
            mcm_r = rdb.get(pid)
            total_events += mcm_r['total_events']
            c = mcm_r['member_of_campaign']
            if c not in request_messages:
                request_messages[c] = ""

            request_messages[c] += " * %s (%s) -> %s\n" % (pid, mcm_r['dataset_name'], r['name'])

        campaigns = sorted(request_messages.keys())
        message = ""
        message += "Dear Data Operation Team,\n\n"
        message += "may you please consider the following batch number %d of %s requests for the campaign%s %s:\n\n" % (
            int(batchNumber),
            total_requests,
            "s" if len(campaigns) > 1 else "",
            ','.join(campaigns))
        for c in campaigns:
            message += request_messages[c]
            message += "\n"
        message += "For a total of %s events\n\n" % (re.sub("(\d)(?=(\d{3})+(?!\d))", r"\1,", "%d" % total_events))
        if self.get_attribute('extension'):
            message += "This batch is for an extension : {0}\n".format(self.get_attribute('extension'))
        if self.get_attribute('version'):
            message += "This batch is a resubmission : v{0}\n".format(self.get_attribute('version') + 1)
        message += "Link to the batch:\n"
        l_type = locator()
        message += '%s/batches?prepid=%s \n\n' % (l_type.baseurl(), self.get_attribute('prepid'))
        if current_notes:
            message += "Additional comments for this batch:\n" + current_notes + '\n'

        self.logger.info('Message send for batch %s' % (self.get_attribute('prepid')))

        self.get_current_user_role_level()


        to_who = [settings.get_value('service_account')]
        if l_type.isDev():
            to_who.append(settings.get_value('hypernews_test'))
        else:
            to_who.append(settings.get_value('dataops_announce'))
        notification(
            subject,
            message,
            [],
            group=notification.BATCHES,
            target_role='production_manager',
            action_objects=[self.get_attribute('prepid')],
            object_type='batches',
            base_object=self)
        returned_id = self.notify(
            subject,
            message,
            who=to_who)
        self.set_attribute('message_id', returned_id)
        self.reload()

        # toggle the status
        # only when we are sure it functions self.set_status()
        self.set_status()
        self.logger.info('Batch "%s" status is %s' % (self.get_attribute('prepid'), self.get_attribute('status')))

        return True
