import flask
import time

from simplejson import dumps, loads

from rest_api.RestAPIMethod import RESTResource
from rest_api.RequestActions import RequestLister
from couchdb_layer.mcm_database import database
from json_layer.mccm import mccm
from json_layer.user import user
from json_layer.chained_campaign import chained_campaign
from json_layer.chained_request import chained_request
from json_layer.request import request
from json_layer.notification import notification
from tools.locker import locker
from tools.locator import locator
from tools.communicator import communicator
import tools.settings as settings
from tools.user_management import access_rights
from tools.priority import priority


class GetMccm(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, mccm_id):
        """
        Retreive the dictionnary for a given mccm
        """
        return self.get_doc(mccm_id)

    def get_doc(self, mccm_id):
        db = database('mccms')
        if not db.document_exists(mccm_id):
            return {"results": {}}
        mccm_doc = db.get(prepid=mccm_id)

        return {"results": mccm_doc}


class UpdateMccm(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Updating an existing mccm with an updated dictionary
        """
        try:
            return self.update(flask.request.data.strip())
        except Exception as ex:
            self.logger.error('Failed to update an mccm from API. Reason: %s' % (str(ex)))
            return {'results': False, 'message': 'Failed to update an mccm from API. Reason: %s' % (
                    str(ex))}

    def is_there_difference(self, previous_requests, new_requests):
        frequency = {}
        for req in previous_requests:
            if req in frequency:
                frequency[req] += 1
            else:
                frequency[req] = 1
        for req in new_requests:
            if req not in frequency or frequency[req] == 0:
                return True
            else:
                frequency[req] -= 1
        for value in frequency.itervalues():
            if value != 0:
                return True
        return False

    def update(self, body):
        data = loads(body)
        if '_rev' not in data:
            self.logger.error('Could not locate the CouchDB revision number in object: %s' % data)
            return {"results": False, 'message': 'could not locate revision number in the object'}
        db = database('mccms')
        if not db.document_exists(data['_id']):
            return {"results": False, 'message': 'mccm %s does not exist' % (data['_id'])}
        else:
            if db.get(data['_id'])['_rev'] != data['_rev']:
                return {"results": False, 'message': 'revision clash'}

        new_version = mccm(json_input=data)

        if not new_version.get_attribute('prepid') and not new_version.get_attribute('_id'):
            self.logger.error('Prepid returned was None')
            raise ValueError('Prepid returned was None')

        # operate a check on whether it can be changed
        previous_version = mccm(db.get(new_version.get_attribute('prepid')))
        editable = previous_version.get_editable()
        for (key, right) in editable.items():
            # does not need to inspect the ones that can be edited
            if right:
                continue
            if previous_version.get_attribute(key) != new_version.get_attribute(key):
                self.logger.error('Illegal change of parameter, %s: %s vs %s : %s' % (
                        key, previous_version.get_attribute(key),
                        new_version.get_attribute(key), right))

                return {"results": False, 'message': 'Illegal change of parameter %s' % key}

        self.logger.info('Updating mccm %s...' % (new_version.get_attribute('prepid')))

        if self.is_there_difference(previous_version.get_request_list(previous_version.get_attribute("requests")),
                new_version.get_request_list(new_version.get_attribute("requests"))):

            self.logger.info("Found difference in requests, calculating total_events")
            new_version.update_total_events()

        # update history
        new_version.update_history({'action': 'update'})
        return {"results": db.update(new_version.json())}


class CreateMccm(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        sdb = database('settings')
        self.possible_pwgs = sdb.get("pwg")["value"]
        self.before_request()
        self.count_call()

    def put(self):
        """
        Create the mccm with the provided json content
        """
        try:
            mccm_d = mccm(loads(flask.request.data.strip()))
        except Exception as e:
            self.logger.error(mccm_d.json())
            self.logger.error("Something went wrong with loading the mccm data:\n {0}".format(e))
            return {
                "results": False,
                "message": "Something went wrong with loading the mccm data:\n {0}".format(e)}

        if not mccm_d.get_attribute('prepid'):
            self.logger.error('Non-existent prepid')
            return {"results": False, "message": "The mccm ticket has no id!"}

        if mccm_d.get_attribute("pwg") not in self.possible_pwgs:
            self.logger.error('Trying to create Mccm with non-existant PWG: %s' % (mccm_d.get_attribute("pwg")))
            return {
                "results": False,
                "message": "The mccm ticket has non-existant PWG!"}

        db = database('mccms')
        # need to complete the prepid
        if mccm_d.get_attribute('prepid') == mccm_d.get_attribute('pwg'):
            mccm_d.set_attribute('prepid', self.fill_id(mccm_d.get_attribute('pwg'), db))
        elif db.document_exists(mccm_d.get_attribute('prepid')):
            return {"results": False,
                    "message": "Mccm document {0} already exists".format(
                            mccm_d.get_attribute('prepid'))}

        mccm_d.set_attribute('_id', mccm_d.get_attribute('prepid'))
        mccm_d.set_attribute('meeting', mccm.get_meeting_date().strftime("%Y-%m-%d"))
        mccm_d.update_history({'action': 'created'})
        self.logger.info('Saving mccm {0}'.format(mccm_d.get_attribute('prepid')))

        return {
            "results": db.save(mccm_d.json()),
            "prepid": mccm_d.get_attribute('prepid')}

    def fill_id(self, pwg, db):
        mccm_id = pwg
        with locker.lock(mccm_id):  # get date and number
            t = mccm.get_meeting_date()
            mccm_id += '-' + t.strftime("%Y%b%d") + '-'  # date
            final_mccm_id = mccm_id + '00001'
            i = 2
            while db.document_exists(final_mccm_id):
                final_mccm_id = mccm_id + str(i).zfill(5)
                i += 1
            return final_mccm_id


class CancelMccm(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, mccm_id):
        """
        Cancel the MccM ticket provided in argument. Does not delete it but put the status as cancelled.
        """
        db = database('mccms')
        udb = database('users')

        mcm_mccm = mccm(db.get(mccm_id))
        curr_user = user(udb.get(mcm_mccm.current_user))

        self.logger.info("Canceling an mccm: %s" % (mccm_id))

        if mcm_mccm.get_attribute('status') == 'done':
            self.logger.info("You cannot cancel 'done' mccm ticket")
            return {"results": False, "message": "Cannot cancel done tickets"}

        if not mcm_mccm.get_attribute("pwg") in curr_user.get_pwgs():
            self.logger.info("User's PWGs: %s doesnt include ticket's PWG: %s" % (
                    curr_user.get_pwgs(), mcm_mccm.get_attribute("pwg")))

            return {"results": False, "message": "You cannot cancel ticket with different PWG than yours"}

        mcm_mccm.set_attribute('status', 'cancelled')
        mcm_mccm.update_history({'action': 'cancelled'})
        saved = db.update(mcm_mccm.json())
        if saved:
            return {"results": True}
        else:
            return {"results": False, "message": "Could not save the ticket to be cancelled."}


class DeleteMccm(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def delete(self, mccm_id):
        db = database('mccms')
        mcm_mccm = db.get(mccm_id)
        if mcm_mccm['status'] == 'done':
            return {"results": False, "message": "Cannot delete a ticket that is done"}
        return {"results": db.delete(mccm_id)}


class GetEditableMccmFields(RESTResource):

    def __init__(self):
        self.db_name = 'mccms'
        self.before_request()
        self.count_call()

    def get(self, mccm_id):
        """
        Retrieve the fields that are currently editable for a given mccm
        """
        return self.get_editable(mccm_id)

    def get_editable(self, prepid):
        db = database(self.db_name)
        mccm_d = mccm(db.get(prepid))
        editable = mccm_d.get_editable()
        return {"results": editable}


class GenerateChains(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, mccm_id, reserve_input='', limit_campaign_id=''):
        """
        Operate the chaining for a given MccM document id
        """
        reserve = False
        if reserve_input == 'reserve':
            reserve = True
            if limit_campaign_id != '':
                reserve = limit_campaign_id

        ignore_existing = flask.request.args.get('ignore_existing', 'False').lower() != 'false'
        lock = locker.lock(mccm_id)
        if lock.acquire(blocking=False):
            try:
                res = self.generate(mccm_id, reserve, ignore_existing)
            finally:
                lock.release()
            return res
        else:
            return {
                "results": False,
                "message": "%s is already being operated on" % mccm_id}

    def generate(self, mid, reserve=False, ignore_existing=False):
        mdb = database('mccms')
        rdb = database('requests')

        mcm_m = mccm(mdb.get(mid))

        if mcm_m.get_attribute('status') != 'new' and not ignore_existing:
            return {
                "prepid": mid,
                "results": False,
                "message": "status is %s, expecting new" % (
                            mcm_m.get_attribute('status'))}

        if mcm_m.get_attribute('block') == 0:
            return {
                "prepid": mid,
                "results": False,
                "message": "No block selected"}

        if len(mcm_m.get_attribute('chains')) == 0:
            return {
                "prepid": mid,
                "results": False,
                "message": "No chains selected"}

        if len(mcm_m.get_attribute('requests')) == 0:
            return {
                "prepid": mid,
                "results": False,
                "message": "No requests selected"}

        request_prepids = []
        for r in mcm_m.get_attribute('requests'):
            if type(r) == list:
                if len(r) > 2:
                    return {
                        "prepid": mid,
                        "results": False,
                        "message": "range of id too large"}

                (pwg1, campaign1, serial1) = r[0].split('-')
                (pwg2, campaign2, serial2) = r[1].split('-')
                serial1 = int(serial1)
                serial2 = int(serial2)
                if pwg1 != pwg2 or campaign1 != campaign2:
                    return {
                        "prepid": mid,
                        "results": False,
                        "message": "inconsistent range of ids %s -> %s" % (r[0], r[1])}

                request_prepids.extend(map(lambda s: "%s-%s-%05d" % (pwg1, campaign1, s),
                        range(serial1, serial2 + 1)))

            else:
                request_prepids.append(r)

        if len(request_prepids) != len(set(request_prepids)):
            return {
                "prepid": mid,
                "results": False,
                "message": "There are duplicate actions in the ticket"}

        ccdb = database('chained_campaigns')
        chained_campaigns = []
        for cc in mcm_m.get_attribute('chains'):
            __query = ccdb.construct_lucene_query({
                    'prepid': cc,
                    'alias': cc
                }, boolean_operator="OR"
            )
            query_result = ccdb.full_text_search('search', __query, page=-1)
            if len(query_result) == 0:
                return {
                    'prepid' : mid,
                    'results' : False,
                    'message' : 'Chained campaign "%s" does not exist' % (cc)}

            chained_campaigns.extend(map(lambda cc: chained_campaign(cc), query_result))
        # collect the name of the campaigns it can belong to
        ccs = list(set(map(lambda cc: cc.get_attribute('campaigns')[0][0], chained_campaigns)))
        if len(ccs) != 1:
            return {
                "prepid": mid,
                "results": False,
                "message": "inconsistent list of chains %s, leading to different root campaigns %s" % (mcm_m.get_attribute('chains'), ccs)}

        allowed_campaign = ccs[0]
        crdb = database('chained_requests')
        chained_campaigns_for_requests = {}
        for request_prepid in request_prepids:
            mcm_r = rdb.get(request_prepid)
            if mcm_r['member_of_campaign'] != allowed_campaign:
                return {
                    "prepid" : mid,
                    "results" : False,
                    "message" : "A request (%s) is not from the allowed root campaign %s" % (request_prepid, allowed_campaign)}

            if mcm_r['status'] == 'new' and mcm_r['approval'] == 'validation':
                return {
                    "prepid": mid,
                    "results": False,
                    "message": "A request (%s) is being validated." % (request_prepid)}

            if mcm_r['flown_with']:
                return {
                    "prepid": mid,
                     "results": False,
                    "message": "A request (%s) is in the middle of a chain already." % (request_prepid)}

            chained_campaigns_for_requests[mcm_r['prepid']] = []
            for cc in chained_campaigns:
                duplicate_query = ccdb.construct_lucene_query({
                        'member_of_campaign': cc.get_attribute('prepid'),
                        'contains': request_prepid,
                        'pwg': mcm_r['pwg']
                    },
                    boolean_operator='AND')
                duplicate_query_result = crdb.full_text_search('search', duplicate_query, page=-1)
                if len(duplicate_query_result) > 0:
                    if not ignore_existing:
                        return {
                            'prepid' : mid,
                            'results' : False,
                            'message' : 'Chain(s) with request "%s" and chained campaign "%s" already exist. '
                                        'Chained request(s): %s' % (request_prepid,
                                                                    cc.get_attribute('prepid'),
                                                                    ',\n'.join([x['prepid'] for x in duplicate_query_result]))}
                else:
                    chained_campaigns_for_requests[mcm_r['prepid']].append(cc.get_attribute('prepid'))

        if not mcm_m.get_attribute('repetitions'):
            return {
                "prepid": mid,
                "results": False,
                "message": "The number of repetitions (%s) is invalid" % (mcm_m.get_attribute('repetitions'))}

        self.logger.info('Will generate chains for these requests and campaigns:\n%s', dumps(chained_campaigns_for_requests, indent=4))
        res = []
        special = mcm_m.get_attribute('special')
        if isinstance(reserve, bool):
            reserve_campaigns = [reserve] * len(request_prepids)
        else:
            reserve_campaigns = reserve.split(',')

        generated_chains = mcm_m.get_attribute('generated_chains')
        if generated_chains is None:
            generated_chains = {}

        for request_prepid in request_prepids:
            self.logger.info("Generating all chained request for request %s" % request_prepid)
            for times in range(mcm_m.get_attribute('repetitions')):
                for index, mcm_chained_campaign in enumerate(chained_campaigns):
                    if mcm_chained_campaign.get_attribute('prepid') in chained_campaigns_for_requests.get(request_prepid, []):
                        generated_dict = self.generate_chained_requests(mcm_m, request_prepid, mcm_chained_campaign, reserve=reserve_campaigns[index], special=special)
                        # for now we put a small delay to not crash index with a lot of action
                        time.sleep(1)
                        if not generated_dict['results']:
                            return {"prepid": mid,
                                    "results": False,
                                    "message": generated_dict['message'],
                                    'chained_request_prepid': generated_dict['prepid'] if 'prepid' in generated_dict else ''}

                        generated_chains[generated_dict['prepid']] = generated_dict['generated_requests']
                        mcm_m.set_attribute("generated_chains", generated_chains)
                        mdb.update(mcm_m.json())
                        mcm_m.reload(save_current=False)
                        time.sleep(0.5)
                    else:
                        self.logger.info('Skipping %s and %s' % (request_prepid, mcm_chained_campaign.get_attribute('prepid')))

        mcm_m.set_status()
        mdb.update(mcm_m.json())
        return {
                "prepid": mid,
                "results": True,
                "message": res}

    def generate_chained_requests(self, mccm_ticket, request_prepid, mcm_chained_campaign, reserve=False, with_notify=True, special=False):
        try:
            mcm_chained_campaign.reload(save_current=False)
            generated_chained_request = chained_request(mcm_chained_campaign.generate_request(request_prepid))
        except Exception as e:
            message = "Unable to generate chained request for ticket %s request %s, message: " % (mccm_ticket.get_attribute('prepid'), request_prepid, str(e))
            self.logger.error(message)
            return {
                "results": False,
                "message": message}
        requests_db = database('requests')
        self.overwrite_action_parameters_from_ticket(generated_chained_request, mccm_ticket)
        mcm_request = request(json_input=requests_db.get(request_prepid))
        generated_chained_request.set_attribute('last_status', mcm_request.get_attribute('status'))
        if generated_chained_request.get_attribute('last_status') in ['submitted', 'done']:
            generated_chained_request.set_attribute('status', 'processing')
        if special:
            generated_chained_request.set_attribute('approval', 'none')
        new_chain_prepid = generated_chained_request.get_attribute('prepid')
        if not generated_chained_request.reload():
            return {
                'results': False,
                'message': 'Unable to save chained request %s' % new_chain_prepid}
        # update the history of chained campaign
        mcm_chained_campaign.save()
        # let the root request know that it is part of a chained request
        chains = mcm_request.get_attribute('member_of_chain')
        chains.append(new_chain_prepid)
        chains.sort()
        mcm_request.set_attribute('member_of_chain', list(set(chains)))
        mcm_request.update_history({'action': 'join chain', 'step': new_chain_prepid})
        mcm_request.save()
        mcm_request_status = mcm_request.get_attribute('status')
        # do the reservation of the whole chain ?
        generated_requests = []
        if reserve:
            results_dict = generated_chained_request.reserve(limit=reserve, save_requests=False)
            if results_dict['results'] and 'generated_requests' in results_dict:
                generated_requests = results_dict['generated_requests']
                results_dict.pop('generated_requests')
            else:
                return {
                    "results": False,
                    "prepid": new_chain_prepid,
                    "message": results_dict['message']}

        block = mccm_ticket.get_attribute('block')
        self.logger.info('Generated requests for %s are %s' % (generated_chained_request.get_attribute('prepid'), generated_requests))
        self.logger.info('Status of %s root request %s is %s' % (generated_chained_request.get_attribute('prepid'), request_prepid, mcm_request_status))
        if mcm_request_status == 'done' or mcm_request_status == 'approved':
            # change priority of the whole chain
            self.logger.info('Setting block %s for %s' % (block, generated_chained_request.get_attribute('prepid')))
            generated_chained_request.set_priority(block)
        elif mcm_request_status == 'submitted':
            # change priority only for the newly created requests
            new_priority = priority().priority(block)
            for generated_request_prepid in generated_requests:
                generated_request = request(json_input=requests_db.get(generated_request_prepid))
                self.logger.info('Setting priority %s for %s' % (new_priority, generated_request_prepid))
                generated_request.change_priority(new_priority)

        return {
                "results":True,
                "prepid": new_chain_prepid,
                'generated_requests': generated_requests}

    def overwrite_action_parameters_from_ticket(self, generated_chained_request, mccm_ticket):
        block = mccm_ticket.get_attribute('block')
        staged = mccm_ticket.get_attribute('staged')
        threshold = mccm_ticket.get_attribute('threshold')
        # generated_chained_request.set_priority(block)
        action_parameters = generated_chained_request.get_attribute('action_parameters')
        action_parameters.update(
            {
                'block_number': block,  # block is mandatory
                'staged': staged if staged != 0 else action_parameters['staged'],
                'threshold': threshold if threshold != 0 else action_parameters['threshold']})


class MccMReminderGenContacts(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        """
        Send a reminder to all generator contacts that have tickets with status equal to new
        """
        def streaming_function():
            mccms_db = database('mccms')
            users_db = database('users')
            generator_contacts_query = users_db.construct_lucene_query({'role': 'generator_contact'})
            generator_contacts = users_db.full_text_search("search", generator_contacts_query, page=-1)
            generator_contacts_by_pwg = {}
            generator_contacts_emails = set()
            for contact in generator_contacts:
                for pwg in contact.get('pwg', []):
                    if pwg not in generator_contacts_by_pwg:
                        generator_contacts_by_pwg[pwg] = []

                    generator_contacts_by_pwg[pwg].append(contact.get('email'))
                    generator_contacts_emails.add(contact.get('email'))

            __query = mccms_db.construct_lucene_query({'status': 'new'})
            mccms_tickets = mccms_db.full_text_search('search', __query, page=-1)
            authors_tickets_dict = dict()
            yield '<pre>'
            for ticket in mccms_tickets:
                yield 'Processing ticket %s\n' % (ticket['prepid'])
                mccm_ticket = mccm(json_input=ticket)
                pwg = mccm_ticket.get_attribute('pwg')
                authors = mccm_ticket.get_actors(what='author_email')
                yield '%s worked on %s\n' % (authors, ticket['prepid'])
                authors = filter(lambda e: e in generator_contacts_emails, list(set(authors + generator_contacts_by_pwg.get(pwg, []))))
                yield '%s will be notified about %s\n' % (authors, ticket['prepid'])
                for author_email in authors:
                    if author_email in generator_contacts_emails:
                        if author_email not in authors_tickets_dict:
                            authors_tickets_dict[author_email] = set()

                        authors_tickets_dict[author_email].add(ticket['prepid'])

            subject_template = 'Gentle reminder on %s ticket%s to be operated by you'
            message_template = ('Dear GEN Contact,\nPlease find below the details of %s MccM ticket%s in status "new". ' + 
                                'Please present them in next MccM googledoc or cancel tickets if these are not needed anymore.\n\n')
            base_url = locator().baseurl()
            mail_communicator = communicator()
            service_account = settings.get_value('service_account')
            for author_email, ticket_prepids in authors_tickets_dict.iteritems():
                num_tickets = len(ticket_prepids)
                subject = subject_template % (num_tickets, '' if num_tickets == 1 else 's')
                message = message_template % (num_tickets, '' if num_tickets == 1 else 's')
                for ticket_prepid in ticket_prepids:
                    message += 'Ticket: %s\n%smccms?prepid=%s\n\n' % (ticket_prepid, base_url, ticket_prepid)
                    yield '.'

                yield '\n'
                message += 'You received this email because you are listed as generator contact of physics group(s) of these tickets.\n'
                self.logger.info('Email:%s\nSubject: %s\nMessage:%s' % (author_email, subject, message))
                mail_communicator.sendMail([author_email, service_account], subject, message)
                yield 'Email sent to %s\n' % (author_email)

        return flask.Response(flask.stream_with_context(streaming_function()))


class MccMReminderProdManagers(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, block_threshold=0):
        """
        Send a reminder to the production managers for existing opened mccm documents
        """
        mdb = database('mccms')
        udb = database('users')

        __query = mdb.construct_lucene_query({'status': 'new'})
        mccms = mdb.full_text_search('search', __query, page=-1)

        mccms = filter(lambda m: m['block'] <= block_threshold, mccms)
        mccms = sorted(mccms, key=lambda m: m['block'])
        if len(mccms) == 0:
            return {"results": True, "message": "nothing to remind of at level %s, %s" % (block_threshold, mccms)}

        l_type = locator()
        com = communicator()
        subject = 'Gentle reminder on %s tickets to be operated by you' % (len( mccms))
        message = '''\
Dear Production Managers,
 please find below the details of %s opened MccM tickets that need to be operated.

''' % (len(mccms))
        mccm_prepids = []
        for _mccm in mccms:
            prepid = _mccm['prepid']
            message += 'Ticket : %s (block %s)\n' % (prepid, _mccm['block'])
            message += ' %smccms?prepid=%s \n\n' % (l_type.baseurl(), prepid)
            mccm_prepids.append(prepid)
        message += '\n'

        to_who = [settings.get_value('service_account')]
        to_who.extend(map(lambda u: u['email'], udb.query(query="role==production_manager", page_num=-1)))
        notification(
            subject,
            message,
            [],
            group=notification.REMINDERS,
            action_objects=mccm_prepids,
            object_type='mccms',
            target_role='production_manager')
        com.sendMail(
            to_who,
            subject,
            message)

        return {"results": True, "message": map(lambda m: m['prepid'], mccms)}


class CalculateTotalEvts(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, mccm_id):
        """
        Force to recalculate total_events for ticket
        """
        db = database('mccms')

        if not db.document_exists(mccm_id):
            return {"results": {}}

        mccm_doc = mccm(db.get(prepid=mccm_id))
        mccm_doc.update_total_events()

        saved = db.update(mccm_doc.json())
        if saved:
            return {"results": True}
        else:
            return {"results": False, "message": "Could not save the ticket to be cancelled."}

class CheckIfAllApproved(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, mccm_id):
        """
        Return whether all requests in MccM are approve-approved
        """
        mccm_db = database('mccms')

        if not mccm_db.document_exists(mccm_id):
            return {"results": False}

        mccm_doc = mccm_db.get(prepid=mccm_id)
        req_db = database('requests')
        query = ''
        for root_request in mccm_doc.get('requests', []):
            if isinstance(root_request, str) or isinstance(root_request, unicode):
                query += '%s\n' % (root_request)
            elif isinstance(root_request, list):
                # List always contains two elements - start and end of a range
                query += '%s -> %s\n' % (root_request[0], root_request[1])

        req_lister = RequestLister()
        req_lister.logger = self.logger
        requests = req_lister.get_list_of_ids(req_db, {'contents' : query})
        allowed_approvals = set(['approve', 'submit'])
        for request_prepid in requests:
            req = req_db.get(request_prepid)
            approval = req.get('approval')
            if approval not in allowed_approvals:
                return {'results': False}

        return {'results': True}
