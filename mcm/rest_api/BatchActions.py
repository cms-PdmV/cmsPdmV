#!/usr/bin/env python

import flask

from RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from json_layer.batch import batch
from json_layer.request import request
from json_layer.notification import notification
from tools.locker import semaphore_events
import tools.settings as settings
from tools.locator import locator
from tools.user_management import access_rights
from tools.handlers import RequestApprover
from simplejson import loads


class GetBatch(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, prepid):
        """
        Retrieve the json content of given batch id
        """
        db = database('batches')
        return {'results': db.get(prepid=prepid)}


class BatchAnnouncer(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def announce_with_text(self, bid, message):
        bdb = database('batches')
        if not semaphore_events.is_set(bid):
            return {"results": False, "message":
                    "Batch {0} has on-going submissions.".format(bid), "prepid": bid}

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
            if (result['results']):
                r = b.announce(message)
        else:
            r = b.announce(message)
        if r:
            map_wf_to_prepid = {}
            for dictionary in b.get_attribute('requests'):
                wf = dictionary.get('name')
                prepid = dictionary.get('content', {}).get('pdmv_prep_id')
                if not wf or not prepid:
                    continue

                if wf not in map_wf_to_prepid:
                    map_wf_to_prepid[wf] = []

                map_wf_to_prepid[wf].append(prepid)

            rdb = database('requests')
            priority_coeff = settings.get_value('nanoaod_priority_increase_coefficient')
            if priority_coeff > 0:
                for wf, requests in map_wf_to_prepid.iteritems():
                    if len(requests) == 1 and 'nanoaod' in requests[0].lower():
                        for r_prepid in requests:
                            req = request(rdb.get(r_prepid))
                            current_priority = req.get_attribute('priority')
                            new_priority = int(current_priority / 1000 + priority_coeff * 1000)
                            req.change_priority(new_priority)

            return {
                "results": bdb.update(b.json()),
                "message": r,
                "prepid": bid
            }
        else:
            return {
                "results": False,
                "prepid": bid,
                "message": result['message'] if 'message' in result and not r else r
            }


class AnnounceBatch(BatchAnnouncer):
    def __init__(self):
        BatchAnnouncer.__init__(self)

    def put(self):
        """
        Annouce a given batch id, with the provided notes in json content
        """
        return self.announce(loads(flask.request.data))

    def announce(self, data):
        if 'prepid' not in data or 'notes' not in data:
            raise ValueError('no prepid nor notes in batch announcement api')

        bdb = database('batches')
        bid = data['prepid']
        res = []

        if bid.__class__ == list:
            ##if it's multiple announce iterate on the list of prepids
            for el in bid:
                if not bdb.document_exists(el):
                    res.append({"results": False, "message": "%s is not a valid batch name" % el})

                res.append(self.announce_with_text(el, data['notes']))
        else:
            if not bdb.document_exists(bid):
                res = {"results": False, "message": "%s is not a valid batch name" % bid}

            res = self.announce_with_text(bid, data['notes'])

        return res


class InspectBatches(BatchAnnouncer):
    def __init__(self):
        BatchAnnouncer.__init__(self)

    def get(self, batch_id=None, n_to_go=1):
        """
        Look for batches that are new and with 1 requests or /N and announce them,
        or /batchid or /batchid/N
        """
        bdb = database('batches')
        res = []
        if settings.get_value('batch_announce'):
            __query = bdb.construct_lucene_query({'status': 'new'})
            new_batches = bdb.full_text_search('search', __query, page=-1)
            for new_batch in new_batches:
                if batch_id and new_batch['prepid'] != batch_id:
                    continue
                if len(new_batch['requests']) >= n_to_go:
                    # it is good to be announced !
                    res.append(self.announce_with_text(new_batch['_id'], 'Automatic announcement.'))
        else:
            self.logger.info('Not announcing any batch')

        if settings.get_value('batch_set_done'):
            # check on on-going batches
            rdb = database('requests')
            __query2 = bdb.construct_lucene_query({'status': 'announced'})
            announced_batches = bdb.full_text_search('search', __query2, page=-1)
            for announced_batch in announced_batches:
                if batch_id and announced_batch['prepid'] != batch_id:
                    continue
                this_bid = announced_batch['prepid']
                all_done = False
                for r in announced_batch['requests']:
                    all_done = False
                    wma_name = r['name']
                    rid = r['content']['pdmv_prep_id']
                    if not rdb.document_exists(rid):
                        # it OK like this.
                        # It could happen that a request has been deleted and yet in a batch
                        continue
                    mcm_r = rdb.get(rid)
                    if mcm_r['status'] == 'done':
                        # if done, it's done
                        all_done = True
                    else:
                        if len(mcm_r['reqmgr_name']) == 0:
                            # not done, and no requests in request manager, ignore = all_done
                            all_done = True
                        else:
                            if wma_name != mcm_r['reqmgr_name'][0]['name']:
                                # not done, and a first requests that does not correspond
                                # to the one in the batch, ignore = all_done
                                all_done = True
                    if not all_done:
                        # no need to go further
                        break
                if all_done:
                    # set the status and save
                    mcm_b = batch(announced_batch)
                    mcm_b.set_status()
                    bdb.update(mcm_b.json())
                    res.append({"results": True, "prepid": this_bid, "message": "Set to done"})
                else:
                    res.append({"results": False, "prepid": this_bid, "message": "Not completed"})
        else:
            self.logger.info('Not setting any batch to done')

        # anyways return something
        return res


class ResetBatch(BatchAnnouncer):
    def __init__(self):
        BatchAnnouncer.__init__(self)

    def get(self, batch_ids):
        """
        Reset all requests in a batch (or list of) and set the status to reset
        """
        res = []
        bdb = database('batches')
        rdb = database('requests')
        for bid in batch_ids.split(','):
            mcm_b = bdb.get(bid)
            for r in mcm_b['requests']:
                if 'pdmv_prep_id' not in r['content']:
                    continue
                rid = r['content']['pdmv_prep_id']
                if not rdb.document_exists(rid):
                    continue
                mcm_r = request(rdb.get(rid))
                try:
                    mcm_r.reset()
                    rdb.update(mcm_r.json())
                except Exception:
                    continue
            batch_to_update = batch(mcm_b)
            batch_to_update.set_attribute('status', 'reset')
            batch_to_update.update_history({'action': 'set status', 'step': 'reset'})
            bdb.update(batch_to_update.json())
            res.append({'prepid': bid, 'results': True})
        return res


class HoldBatch(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, batch_ids):
        """
        Set batch status to hold (from new) or to new (from hold)
        """
        res = []
        bdb = database('batches')
        for bid in batch_ids.split(','):
            mcm_b = batch(bdb.get(bid))
            if mcm_b.get_attribute('status') == 'new':
                mcm_b.set_attribute('status', 'hold')
                mcm_b.update_history({'action': 'set status', 'step': 'hold'})
            elif mcm_b.get_attribute('status') == 'hold':
                mcm_b.set_attribute('status', 'new')
                mcm_b.update_history({'action': 'set status','step': 'new'})
            else:
                res.append({'prepid': bid, 'results': False, 'message': 'Only status hold or new allowed'})
                continue

            bdb.update(mcm_b.json())
            res.append({'prepid': bid, 'results': True})
        return res


class NotifyBatch(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()
        self.bdb = database('batches')

    def put(self):
        """
        This allows to send a message to data operation in the same thread
         of the announcement of a given batch
        """
        data = loads(flask.request.data)
        if 'prepid' not in data or 'notes' not in data:
            raise ValueError('no prepid nor notes in batch announcement api')
        bid = data['prepid']
        if not self.bdb.document_exists(bid):
            return {"results": False, "message": "%s is not a valid batch name" % bid}
        return self.notify_batch(bid, data['notes'])

    def notify_batch(self, batch_id, message_notes):
        message = message_notes
        to_who = [settings.get_value('service_account')]
        l_type = locator()
        if l_type.isDev():
            to_who.append(settings.get_value('hypernews_test'))
        else:
            to_who.append(settings.get_value('dataops_announce'))

        single_batch = batch(self.bdb.get(batch_id))
        subject = single_batch.get_subject('[Notification]')
        current_message_id = single_batch.get_attribute('message_id')
        self.logger.info('current msgID: %s' % current_message_id)
        if current_message_id != '':
            result = single_batch.notify(subject, message, who=to_who, sender=None, reply_msg_ID=current_message_id)
            self.logger.info('result if True : %s' % result)
        else:
            result = single_batch.notify(subject, message, who=to_who, sender=None)
            self.logger.info('result if False : %s' % result)
        notification(
            subject,
            message,
            [],
            group=notification.BATCHES,
            target_role='production_manager',
            action_objects=[single_batch.get_attribute('prepid')],
            object_type='batches',
            base_object=single_batch
        )
        single_batch.update_history({'action': 'notify', 'step': message})
        single_batch.reload()
        return {'results': result}
