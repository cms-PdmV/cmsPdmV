#!/usr/bin/env python

from json import dumps

from couchdb_layer.prep_database import database 
from json_layer.batch import batch


# generates the next valid prepid 
class BatchPrepId():
    def __init__(self):
        self.bdb = database('batches')

    def generate_prepid(self, flow_with, next_campaign, processstring=None):

        if flown_with:
            batchName = flown_with+'_'+next_campaign
        else:
            batchName = next_campaign
        
        #### doing the query by hand    
        res = self.bdb.queries([])
        res_this = filter(lambda x: x['prepid'].split('-')[0] == batchName, res)
        ## filter to have the ones of that family, that are NEW
        res_new = filter(lambda x: x['status']=='new', res_this)
        ##get only the serial number of those
        res_new = map(lambda x: int(x['prepid'].split('-')[-1]), res_new)

        ##find out the next one
        if not res_new:
            ##no open batch of this kind
            res_next = filter(lambda x: x['prepid'].split('-')[0].endswith(next_campaign) , res) 
            if not res_next:
                ## not even a document with *_<campaign>-* existing: ---> creating a new family
                batchNumber=1
            else:
                ## pick up the last+1 serial number of *_<campaign>-*  family
                batchNumber=max(map(lambda x: int(x['prepid'].split('-')[-1]), res_next)) + 1
        else:
            ## pick up the last serial number of that family
            batchNumber=max(res_new)
            
        
        batchName+='-%05d'%(batchNumber)
        if not self.bdb.document_exists(batchName):
            newBatch = batch({'_id':batchName,'prepid':batchName})
            notes=""
            cdb = database('campaigns')
            mcm_c = cdb.get( next_campaign )
            if mcm_c['notes']:
                notes+="Notes about the campaign:\n"+mcm_c['notes']+"\n"
            if flow_with:
                fdb = database('flows')
                mcm_f = fdb.get(req_json['flown_with'])
                if mcm_f['notes']:
                    notes+="Notes about the flow:\n"+mcm_f['notes']+"\n"
            if notes:
                newBatch.set_attribute('notes',notes)
            newBatch.update_history({'action':'created'})
            self.bdb.save(newBatch.json())
        
        return batchName
