from couchdb_layer.prep_database import database
from json_layer.json_base import json_base
from tools.locator import locator
import re
from tools.settings import settings

class batch(json_base):
    def __init__(self, json_input={}):
        self._json_base__status = ['new','announced','done']
        self._json_base__schema = {
            '_id':'',
            'prepid':'',
            'history':[],
            'notes':'',
            'status':self.get_status_steps()[0],
            'requests':[],
            'extension':0,
            'process_string':'',
            'version':0
            }
        self.setup()
        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()

    def add_requests(self,a_list):
        b_requests=self.get_attribute('requests')
        b_requests.extend(a_list)
        ## sort them
        b_requests = sorted(b_requests, key=lambda d : d['name'])
        self.set_attribute('requests', b_requests ) 

    def add_notes(self,notes):
        b_notes=self.get_attribute('notes')
        b_notes+=notes
        self.set_attribute('notes',b_notes)

    def announce(self,notes="",user=""):
        if self.get_attribute('status')!='new':
            return False
        if len(self.get_attribute('requests'))==0:
            return False

        current_notes=self.get_attribute('notes')
        if current_notes:
            current_notes+='\n'
        if notes:
            current_notes+=notes
            self.set_attribute('notes',current_notes)

        total_events=0
        content = self.get_attribute('requests')
        total_requests=len(content)
        rdb =database('requests')

        ## prepare the announcing message
        (campaign,batchNumber)=self.get_attribute('prepid').split('_')[-1].split('-')
        subject="New %s production, batch %d"%(campaign,int(batchNumber))

        if self.get_attribute('version'):
            subject+=', Resubmission'
        if self.get_attribute('extension'):
            subject+=', Extension'
        if self.get_attribute('process_string'):
            subject+=', (%s)' % (self.get_attribute('process_string'))

        message=""
        message+="Dear Data Operation Team,\n\n"
        message+="may you please consider the following batch number %d of %s requests for the campaign %s:\n\n"%(int(batchNumber),total_requests, campaign)
        for r in content:
            ##loose binding of the prepid to the request name, might change later on
            if 'pdmv_prepid_id' in r['content']:
                pid=r['content']['pdmv_prepid_id']
            else:
                pid=r['name'].split('_')[1]
            mcm_r = rdb.get(pid)
            total_events+=mcm_r['total_events']
            message+=" * %s -> %s \n"%(pid,r['name'])
        message+="\n"
        message+="For a total of %s events\n\n"%( re.sub("(\d)(?=(\d{3})+(?!\d))", r"\1,", "%d" % total_events ))
        message+="Link to the batch:\n"
        l_type = locator()
        message+='%s/batches?prepid=%s \n\n'%(l_type.baseurl(), self.get_attribute('prepid'))
        if current_notes:
            message+="Additional comments for this batch:\n"+current_notes+'\n'
        
        if self.get_attribute('process_string'):
            message+='Please use "%s" in the dataset name.\n' % self.get_attribute('process_string')

        self.logger.log('Message send for batch %s'%(self.get_attribute('prepid')))
        
        self.get_current_user_role_level()


        to_who = [settings().get_value('service_account')]
        if l_type.isDev():
            to_who.append( settings().get_value('hypernews_test'))
        else:
            to_who.append( settings().get_value('dataops_announce' ))

        self.notify(subject,
                    message,
                    who=to_who
                    )

        ## toggle the status
        ### only when we are sure it functions self.set_status()
        self.set_status()

        return True
