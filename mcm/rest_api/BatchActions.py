#!/usr/bin/env python

import cherrypy
from json import dumps
from RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from json_layer.batch import batch
from json_layer.request import request
from json_layer.notification import notification
from tools.locker import semaphore_events
from tools.settings import settings
from tools.locator import locator
from tools.user_management import access_rights
from tools.json import threaded_loads
from tools.handlers import RequestApprover, submit_pool

class SaveBatch(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def PUT(self):
        """
        Save the content of a batch given the json content
        """
        bdb = database('batches')
        data = threaded_loads(cherrypy.request.body.read().strip())

        data.pop('_rev')

        mcm_b = batch(data)

        bdb.save(mcm_b.json())

class UpdateBatch(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def PUT(self):
        """
        Update the content of a batch given the json content
        """
        bdb = database('batches')
        data = threaded_loads(cherrypy.request.body.read().strip())

        mcm_b = batch(data)

        bdb.update(mcm_b.json())

class GetBatch(RESTResource):
    def __init__(self):
        self.db_name = 'batches'

    def GET(self, *args):
        """
        Retrieve the json content of given batch id
        """
        if not args:
            self.logger.error("No Arguments were given")
            return dumps({"results":'Error: No arguments were given'})
        return dumps({'results':self.get_request(args[0])})

    def get_request(self, data):
        db = database(self.db_name)
        return db.get(prepid=data)

class GetAllBatches(RESTResource):
    def __init__(self):
        self.db_name = 'batches'

    def GET(self, *args):
        """
        Retrieve the json content of the batch db
        """
        return dumps({'results':self.get_all()})

    def get_all(self):
        db = database(self.db_name)
        return db.get_all()

class GetIndex(RESTResource):
    def __init__(self):
        self.db_name = 'batches'

    def GET(self, *args):
        """
        Redirect to the proper link to a given batch id
        """
        if not args:
            self.logger.error("No Arguments were given")
            return dumps({"results":'Error: No arguments were given'})
        db = database(self.db_name)
        b_id = args[0]
        if not db.document_exists(b_id):
            return dumps({"results":False, "message": "%s is not a valid batch name" % (b_id)})
        #yurks ?
        redirect = """\
<html>
<meta http-equiv="REFRESH" content="0; url=/mcm/batches?prepid=%s&page=0">
</html>
"""% b_id
        return redirect

class BatchAnnouncer(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def announce_with_text(self, bid, message):
        bdb = database('batches')
        if not semaphore_events.is_set(bid):
            return {"results": False, "message":
                    "Batch {0} has on-going submissions.".format(bid), "prepid" : bid}

        b = batch(bdb.get(bid))
        workflows = ''
        for dictionary in b.get_attribute('requests'):
            workflows += dictionary['name'] + ','
        workflows = workflows[:-1]
        r = ''
        result = {}
        if workflows != '':
            approver = RequestApprover(bid, workflows)
            result = approver.internal_run()
            if(result['results']):
                r = b.announce(message)
        else:
            r = b.announce(message)
        if r:
            return {
                "results":bdb.update(b.json()),
                "message" : r,
                "prepid" : bid
            }
        else:
            return {
                "results":False,
                "prepid" : bid,
                "message": result['message'] if 'message' in result and not r else r
            }

class AnnounceBatch(BatchAnnouncer):
    def __init__(self):
        BatchAnnouncer.__init__(self)

    def PUT(self):
        """
        Annouce a given batch id, with the provided notes in json content
        """
        return dumps(self.announce(threaded_loads(cherrypy.request.body.read().strip())))

    def announce(self, data):
        if not 'prepid' in data or not 'notes' in data:
            raise ValueError('no prepid nor notes in batch announcement api')
        bdb = database('batches')
        bid=data['prepid']
        if not bdb.document_exists(bid):
            return {"results":False, "message": "%s is not a valid batch name" % bid}

        return self.announce_with_text(bid, data['notes'])

class InspectBatches(BatchAnnouncer):
    def __init__(self):
        BatchAnnouncer.__init__(self)

    def GET(self, *args):
        """
        Look for batches that are new and with 1 requests or /N and announce them,
        or /batchid or /batchid/N
        """
        self.N_to_go = 1
        bid = None
        if len(args):
            if args[0].isdigit():
                self.N_to_go = int(args[0])
            else:
                bid = args[0]
            if len(args) == 2:
                self.N_to_go = int(args[1])
        bdb = database('batches')
        res = []
        if settings().get_value('batch_announce'):
            __query = bdb.construct_lucene_query({'status' : 'new'})
            new_batches = bdb.full_text_search('search', __query, page=-1)
            for new_batch in new_batches:
                if bid and new_batch['prepid'] != bid:  continue
                if len(new_batch['requests']) >= self.N_to_go:
                    ## it is good to be announced !
                    res.append(self.announce_with_text(new_batch['_id'],
                            'Automatic announcement.'))
        else:
            self.logger.info('Not announcing any batch')

        if settings().get_value('batch_set_done'):
            ## check on on-going batches
            rdb = database('requests')
            __query2 = bdb.construct_lucene_query({'status' : 'announced'})
            announced_batches = bdb.full_text_search('search', __query2, page=-1)
            for announced_batch in announced_batches:
                if bid and announced_batch['prepid'] != bid:  continue
                this_bid = announced_batch['prepid']

                all_done = False
                for r in announced_batch['requests']:
                    all_done = False
                    wma_name = r['name']
                    rid = r['content']['pdmv_prep_id']
                    if not rdb.document_exists( rid ):
                        ##it OK like this.
                        ##It could happen that a request has been deleted and yet in a batch
                        continue
                    mcm_r = rdb.get( rid )
                    if mcm_r['status'] == 'done':
                        ## if done, it's done
                        all_done = True
                    else:
                        if len(mcm_r['reqmgr_name']) == 0:
                            ## not done, and no requests in request manager, ignore = all_done
                            all_done = True
                        else:
                            if wma_name != mcm_r['reqmgr_name'][0]['name']:
                                ## not done, and a first requests that does not correspond
                                ##to the one in the batch, ignore = all_done
                                all_done = True
                    if not all_done:
                        ## no need to go further
                        break
                if all_done:
                    ## set the status and save
                    mcm_b = batch(announced_batch)
                    mcm_b.set_status()
                    bdb.update(mcm_b.json())
                    res.append({"results": True, "prepid" : this_bid, "message" : "Set to done"})
                else:
                    res.append({"results": False, "prepid" : this_bid,
                            "message" : "Not completed"})
        else:
            self.logger.info('Not setting any batch to done')

        #anyways return something
        return dumps(res)

class ResetBatch(BatchAnnouncer):

    def __init__(self):
        self.access_limit = access_rights.production_manager

    def GET(self, *args):
        """
        Reset all requests in a batch (or list of) and set the status to reset
        """
        res = []
        bdb = database('batches')
        rdb = database('requests')
        bids = args[0]
        for bid in bids.split(','):
            mcm_b = bdb.get(bid)
            for r in mcm_b['requests']:
                if not 'pdmv_prep_id' in r['content']:
                    continue
                rid = r['content']['pdmv_prep_id']
                if not rdb.document_exists(rid):
                    continue
                mcm_r = request(rdb.get(rid))
                try:
                    mcm_r.reset()
                    rdb.update(mcm_r.json())
                except Exception as ex:
                    continue
            batch_to_update = batch(mcm_b)
            batch_to_update.set_attribute('status', 'reset')
            batch_to_update.update_history({'action': 'set status',
                    'step': 'reset'})

            bdb.update(batch_to_update.json())
            res.append({'prepid': bid, 'results': True})
        return dumps(res)

class HoldBatch(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def GET(self, *args):
        """
        Set batch status to hold (from new) or to new (from hold)
        """
        res = []
        bdb = database('batches')
        if not len(args):
            return dumps({'results': False, 'message': 'No batch ids given'})
        bids = args[0]
        for bid in bids.split(','):
            mcm_b = batch(bdb.get(bid))
            if mcm_b.get_attribute('status') == 'new':
                mcm_b.set_attribute('status', 'hold')
                mcm_b.update_history({'action':'set status','step':'hold'})
            elif mcm_b.get_attribute('status') == 'hold':
                mcm_b.set_attribute('status', 'new')
                mcm_b.update_history({'action':'set status','step':'new'})
            else:
                res.append({'prepid':bid, 'results': False,
                        'message': 'Only status hold or new allowed'})

                continue

            bdb.update( mcm_b.json())
            res.append({'prepid':bid, 'results': True})
        return dumps(res)

class NotifyBatch(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        self.bdb = database('batches')

    def PUT(self):
        """
        This allows to send a message to data operation in the same thread
         of the announcement of a given batch
        """
        data = threaded_loads(cherrypy.request.body.read().strip())
        if not 'prepid' in data or not 'notes' in data:
            raise ValueError('no prepid nor notes in batch announcement api')
        bid = data['prepid']
        if not self.bdb.document_exists(bid):
            return dumps({"results":False, "message": "%s is not a valid batch name" % bid})
        return dumps(self.notify_batch(bid, data['notes'] ))

    def notify_batch(self, batch_id, message_notes):
        message = message_notes
        to_who = [settings().get_value('service_account')]
        l_type = locator()
        if l_type.isDev():
            to_who.append(settings().get_value('hypernews_test'))
        else:
            to_who.append(settings().get_value('dataops_announce'))

        single_batch = batch(self.bdb.get(batch_id))
        subject = single_batch.get_subject('[Notification]')
        current_message_id = single_batch.get_attribute('message_id')

        self.logger.info('current msgID: %s' % current_message_id)
        if current_message_id != '':
            result = single_batch.notify(subject, message, who=to_who,
                    sender=None, reply_msg_ID=current_message_id)

            self.logger.info('result if True : %s' % result)
        else:
            result = single_batch.notify(subject, message, who=to_who, sender=None)
            self.logger.info('result if False : %s' % result)
        notification.create_notification(
                subject,
                message,
                group=notification.BATCHES,
                target_role='production_manager',
                action_objects=[single_batch.get_attribute('prepid')],
                object_type='batches',
                base_object=single_batch
        )
        single_batch.update_history({'action':'notify', 'step' : message})
        single_batch.reload()

        return {'results': result}
