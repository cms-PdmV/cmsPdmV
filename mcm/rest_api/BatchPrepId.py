#!/usr/bin/env python

from json import dumps

from couchdb_layer.mcm_database import database
from json_layer.batch import batch
from tools.locker import locker,semaphore_events
from tools.settings import settings

# generates the next valid prepid
class BatchPrepId():
    def __init__(self):
        self.bdb = database('batches')

    def next_id(self, for_request, create_batch=True):
        flown_with = for_request['flown_with']
        next_campaign = for_request['member_of_campaign']
        version = for_request['version']
        extension = for_request['extension']
        process_string = for_request['process_string']

        return self.next_batch_id(next_campaign,
                     version,
                     extension,
                     process_string,
                     flown_with,
                     create_batch)

    def next_batch_id(self, next_campaign, version=0, extension=0, process_string="",
            flown_with="", create_batch=True):

        with locker.lock('batch name clashing protection'):
            if flown_with:
                batchName = flown_with+'_'+next_campaign
            else:
                batchName = next_campaign

            #### doing the query by hand
            res = self.bdb.queries([])
            res_this = filter(lambda x: x['prepid'].split('-')[0] == batchName, res)
            ## filter to have the ones of that family, that are NEW or on hold
            res_new = filter(lambda x: x['status']=='new' or x['status']=='hold', res_this)

            ## add limitation to version, extension and process string
            res_new = filter(lambda x: x['version'] == version, res_new)
            res_new = filter(lambda x: x['extension'] == extension, res_new)
            res_new = filter(lambda x: x['process_string'] == process_string, res_new)

            ## limit to a certain number of entry per batch : at name reservation time, so it does not work if one submitts more at a time
            max_in_batch = settings().get_value('max_in_batch')
            # for existing batches
            res_new = filter(lambda x: len(x['requests']) <= max_in_batch, res_new)
            # for dynamic allocation from locks
            res_new = filter(lambda x: semaphore_events.count(x['prepid']) <= max_in_batch, res_new)


            ##get only the serial number of those
            res_new = map(lambda x: int(x['prepid'].split('-')[-1]), res_new)

            ##find out the next one
            if not res_new:
                ##no open batch of this kind
                res_next = filter(lambda x: x['prepid'].split('-')[0].split('_')[-1] == next_campaign.split('_')[-1] , res)
                if not res_next:
                    ## not even a document with *_<campaign>-* existing: ---> creating a new family
                    batchNumber = 1
                else:
                    ## pick up the last+1 serial number of *_<campaign>-*  family
                    batchNumber = max(map(lambda x: int(x['prepid'].split('-')[-1]), res_next)) + 1
            else:
                ## pick up the last serial number of that family
                batchNumber = max(res_new)

            batchName += '-%05d' % (batchNumber)

            if not self.bdb.document_exists(batchName) and create_batch:
                newBatch = batch({'_id':batchName,
                                  'prepid':batchName,
                                  'version' : version,
                                  'extension' : extension,
                                  'process_string' : process_string})
                notes = ""
                cdb = database('campaigns')
                cs = []
                if not cdb.document_exists(next_campaign):
                    ccdb = database('chained_campaigns')
                    if ccdb.document_exists(next_campaign):
                        mcm_cc = ccdb.get(next_campaign)
                        for (c,f) in mcm_cc['campaigns']:
                            cs.append(cdb.get(c))
                else:
                    cs = [cdb.get(next_campaign)]
                for mcm_c in cs:
                    if mcm_c['notes']:
                        notes+="Notes about the campaign %s:\n"%mcm_c['prepid']+mcm_c['notes']+"\n"
                if flown_with:
                    fdb = database('flows')
                    mcm_f = fdb.get(flown_with)
                    if mcm_f['notes']:
                        notes+="Notes about the flow:\n"+mcm_f['notes']+"\n"
                if notes:
                    newBatch.set_attribute('notes',notes)
                newBatch.update_history({'action':'created'})
                self.bdb.save(newBatch.json())

            return batchName
