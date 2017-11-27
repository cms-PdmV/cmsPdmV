#!/usr/bin/env python
from couchdb_layer.mcm_database import database
from json_layer.batch import batch
from tools.locker import locker, semaphore_events
import tools.settings as settings

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
            self.bdb.logger.debug("working on batch prepid")
            if flown_with:
                batchName = flown_with+'_'+next_campaign
            else:
                batchName = next_campaign

            ##find the max batch with similar name, descending guarantees that
            #the returned one will be biggest
            __query_options = {"endkey":'"%s-00001"' % (batchName),
                    "startkey":'"%s-99999"' % (batchName),
                    "descending":"true", "limit":1}

            max_in_batch = settings.get_value('max_in_batch')
            top_batch = self.bdb.raw_query("prepid", __query_options)
            new_batch = True

            if len(top_batch) != 0:
                ##we already have some existing batch, check if its fine for appending
                #get a single batch
                single_batch = self.bdb.get(top_batch[0]["id"])
                if single_batch["status"] == "new":
                    #check if batch is not locked in other threads.
                    if len(single_batch["requests"]) + semaphore_events.count(single_batch['prepid']) < max_in_batch:
                        ##we found a needed batch
                        self.bdb.logger.debug("found a matching batch:%s" % (single_batch["prepid"]))
                        batchNumber = int(single_batch["prepid"].split("-")[-1])
                        new_batch = False
                if new_batch:
                    ##we default to max batch and increment its number
                    self.bdb.logger.debug("no new batch. incementing:%s +1" % (single_batch["prepid"]))
                    batchNumber = int(top_batch[0]["id"].split("-")[-1]) + 1
            else:
                self.bdb.logger.debug("starting new batch family:%s" % (batchName))
                batchNumber = 1

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