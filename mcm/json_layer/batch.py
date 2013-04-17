from couchdb_layer.prep_database import database
from json_layer.json_base import json_base
from tools.communicator import communicator

class batch(json_base):
    def __init__(self, json_input={}):
        self._json_base__status = ['new','announced','done']
        self._json_base__schema = {
            '_id':'',
            'prepid':'',
            'history':[],
            'notes':'',
            'status':self.get_status_steps()[0],
            'requests':[]
            }
        
        self.update(json_input)
        self.validate()
        self.com = communicator()
        
    def add_requests(self,a_list):
        b_requests=self.get_attribute('requests')
        b_requests.extend(a_list)
        self.set_attribute('requests', b_requests ) 

    def add_notes(self,notes):
        b_notes=self.get_attribute('notes')
        b_notes+=notes
        self.set_attribute('notes',b_notes)

    def announce(self,notes="",user="McM Announcing service"):
        if self.get_attribute('status')!='new':
            return False
        
        current_notes=self.get_attribute('notes')
        if current_notes:
            current_notes+='\n'
        if notes:
            current_notes+=notes
            self.set_attribute('notes',current_notes)

        ## prepare the announcing message
        (campaign,batchNumber)=self.get_attribute('prepid').split('_')[-1].split('-')
        subject="New %s production, batch %d"%(campaign,int(batchNumber))
        message=""
        message+="Dear Data Operation Team,\n\n"
        message+="may you please consider the following batch number %d of request for the campaign %s:\n\n"%(int(batchNumber),campaign)
        content = self.get_attribute('requests')
        for r in content:
            ##loose binding of the prepid to the request name, might change later on
            if 'prepid' in r['content']:
                pid=r['content']
            else:
                pid=r['name'].split('_')[1]
            message+=" * %s -> %s \n"%(pid,r['name'])
        message+="\n"
        message+="Link to the batch:\n"
        #message+="https://cms-pdmv.cern.ch/mcm/batches/%s\n"%(self.get_attribute('prepid'))
        message+='https://cms-pdmv.cern.ch/mcm/batches?query=prepid%%3D%%3D%s \n\n'%(self.get_attribute('prepid'))
        if current_notes:
            message+="Additional comments for this batch:\n"+current_notes+'\n\n'
        message+="Thank you,\n"+user

        #self.logger.log(message)
        self.logger.log('Message send for batch %s'%(self.get_attribute('prepid')))
        
        self.get_current_user_role_level()

        self.com.sendMail(['vlimant@cern.ch'],
                          subject,
                          message,
                          self.current_user_email
                          )

        ## toggle the status
        ### only when we are sure it functions self.set_status()
        self.set_status()

        return True
