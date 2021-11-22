import flask
import time

import json
from rest_api.RestAPIMethod import RESTResource
from rest_api.RequestActions import RequestLister
from couchdb_layer.mcm_database import database as Database
from json_layer.mccm import mccm as MccM
from json_layer.user import user as User
from json_layer.chained_campaign import chained_campaign as ChainedCampaign
from json_layer.chained_request import chained_request as ChainedRequest
from json_layer.request import request as Request
from tools.locker import locker
from tools.locator import locator
from tools.communicator import communicator
import tools.settings as settings
from tools.user_management import access_rights
from tools.user_management import user_pack as UserPack
from tools.priority import priority


class CreateMccm(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        settings_db = Database('settings')
        self.possible_pwgs = settings_db.get("pwg")["value"]
        self.before_request()
        self.count_call()

    def put(self):
        """
        Create the mccm with the provided json content
        """
        mccm = MccM(json.loads(flask.request.data.strip()))
        pwg = mccm.get_attribute('pwg').upper()

        if pwg not in self.possible_pwgs:
            self.logger.error('Bad PWG: %s', pwg)
            return {'results': False,
                    'message': 'Bad PWG "%s"' % (pwg)}

        duplicates = mccm.get_duplicate_requests()
        if duplicates:
            return {'results': False,
                    'message': 'Duplicated requests: %s' % (', '.join(duplicates))}

        mccm_db = Database('mccms')
        # need to complete the prepid
        with locker.lock('create-ticket-%s' % (pwg)):
            meeting_date = MccM.get_meeting_date()
            meeting_date_full = meeting_date.strftime('%Y-%m-%d')
            meeting_date_short = meeting_date.strftime('%Y%b%d')
            prepid_part = '%s-%s' % (pwg, meeting_date_short)

            newest = mccm_db.raw_query_view('mccms',
                                            'serial_number',
                                            page=0,
                                            limit=1,
                                            options={'group': True,
                                                     'include_docs': False,
                                                     'key': [meeting_date_full, pwg]})
            number = 1
            if newest:
                self.logger.info('Highest prepid number: %05d', newest[0])
                number = newest[0] + 1

            # Save last used prepid
            # Make sure to include all deleted ones
            prepid = '%s-%05d' % (prepid_part, number)
            while mccm_db.document_exists(prepid, include_deleted=True):
                number += 1
                prepid = '%s-%05d' % (prepid_part, number)

            mccm.set_attribute('prepid', prepid)
            mccm.set_attribute('_id', prepid)
            mccm.set_attribute('pwg', pwg) # Uppercase
            mccm.set_attribute('meeting', meeting_date_full)
            mccm.update_history({'action': 'created'})
            if mccm_db.save(mccm.json()):
                return {'results': True,
                        'prepid': prepid}

        return {'results': False,
                'message': 'MccM ticket could not be created'}


class UpdateMccm(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Updating a MccM with an updated dictionary
        """
        data = json.loads(flask.request.data)
        if '_rev' not in data:
            return {'results': False,
                    'message': 'No revision provided'}

        mccm_db = Database('mccms')
        try:
            mccm = MccM(json_input=data)
        except Exception as ex:
            return {'results': False,
                    'message': str(ex)}

        prepid = mccm.get_attribute('prepid')
        if not prepid:
            self.logger.error('Invalid prepid "%s"', prepid)
            return {'results': False,
                    'message': 'Invalid prepid "%s"' % (prepid)}

        mccm_json = mccm_db.get(prepid)
        if not mccm_json:
            self.logger.error('Cannot update, %s does not exist', prepid)
            return {'results': False,
                    'message': 'Cannot update, "%s" does not exist' % (prepid)}

        duplicates = mccm.get_duplicate_requests()
        if duplicates:
            return {'results': False,
                    'message': 'Duplicated requests: %s' % (', '.join(duplicates))}

        old_mccm = MccM(json_input=mccm_json)
        # Find what changed
        for (key, editable) in old_mccm.get_editable().items():
            old_value = old_mccm.get_attribute(key)
            new_value = mccm.get_attribute(key)
            if not editable and old_value != new_value:
                message = 'Not allowed to change "%s": "%s" -> "%s' % (key, old_value, new_value)
                self.logger.error(message)
                return {'results': False,
                        'message': message}

        if set(old_mccm.get_request_list()) != set(mccm.get_request_list()):
            self.logger.info('Request list changed, recalculating total events')
            mccm.update_total_events()

        difference = self.get_obj_diff(old_mccm.json(),
                                       mccm.json(),
                                       ('history', '_rev'))
        if not difference:
            return {'results': True}

        difference = ', '.join(difference)
        mccm.update_history({'action': 'update', 'step': difference})

        # Save to DB
        if not mccm_db.update(mccm.json()):
            self.logger.error('Could not save MccM %s to database', prepid)
            return {'results': False,
                    'message': 'Could not save MccM %s to database' % (prepid)}

        return {'results': True}


class DeleteMccm(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def delete(self, mccm_id):
        """
        Delete a MccM ticket
        """
        mccm_db = Database('mccms')
        mccm_json = mccm_db.get(mccm_id)
        if not mccm_json:
            self.logger.error('Cannot delete, %s does not exist', mccm_id)
            return {'results': False,
                    'message': 'Cannot delete, %s does not exist' % (mccm_id)}

        mccm = MccM(json_input=mccm_json)
        if mccm.get_attribute('status') == 'done':
            return {"results": False,
                    "message": "Cannot delete a ticket that is done"}

        # User info
        user = UserPack(db=True)
        user_role = user.user_dict.get('role')
        self.logger.info('User %s (%s) is trying to delete %s',
                         user.get_username(),
                         user_role,
                         mccm_id)
        if user_role not in {'production_manager', 'administrator'}:
            username = user.get_username()
            history = mccm.get_attribute('history')
            owner = None
            owner_name = None
            if history:
                for history_entry in history:
                    if history_entry['action'] == 'created':
                        owner = history_entry['updater']['author_username']
                        owner_name = history_entry['updater']['author_name']

            if not owner:
                return {'results': False,
                        'message': 'Could not get owner of the ticket'}

            if owner != username:
                return {'results': False,
                        'message': 'Only the owner (%s) is allowed to delete the ticket' % (owner_name)}

        # Delete from DB
        if not mccm_db.delete(mccm_id):
            self.logger.error('Could not delete %s from database', mccm_id)
            return {'results': False,
                    'message': 'Could not delete %s from database' % (mccm_id)}

        return {'results': True}


class GetMccm(RESTResource):

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, mccm_id):
        """
        Retrieve the MccM for given id
        """
        mccm_db = Database('mccms')
        return {'results': mccm_db.get(prepid=mccm_id)}


class CancelMccm(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, mccm_id):
        """
        Cancel the MccM ticket provided in argument
        Does not delete it but put the status as cancelled.
        """
        mccm_db = Database('mccms')
        user_db = Database('users')

        mccm = MccM(json_input=mccm_db.get(mccm_id))
        status = mccm.get_attribute('status')
        if status == 'done':
            return {"results": False,
                    "message": "Cannot cancel done tickets"}

        mccm.get_current_user_role_level()
        user = User(user_db.get(mccm.current_user))
        user_pwgs = user.get_pwgs()
        ticket_pwg = mccm.get_attribute("pwg")
        if ticket_pwg not in user_pwgs:
            self.logger.error('User\'s PWGs: %s, ticket: %s', user_pwgs, ticket_pwg)
            return {"results": False,
                    "message": "You cannot cancel ticket with different PWG than yours"}

        if status == 'new':
            mccm.set_attribute('status', 'cancelled')
            mccm.update_history({'action': 'cancelled'})
        elif status == 'cancelled':
            mccm.set_attribute('status', 'new')
            mccm.update_history({'action': 'uncancelled'})

        if not mccm_db.update(mccm.json()):
            return {"results": False,
                    "message": "Could not save to the database"}

        return {"results": True}


class NotifyMccm(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Sends the prodived posted text to the users who acted on MccM ticket
        """
        data = json.loads(flask.request.data)
        # Message
        message = data['message'].strip()
        if not message:
            return {'results': False,
                    'message': 'No message'}

        # Prepid
        prepid = data['prepid']
        mccm_db = Database('mccms')
        mccm_json = mccm_db.get(prepid)
        if not mccm_json:
            return {"results": False,
                    "message": "Could not find %s" % (prepid)}

        # Subject
        subject = data.get('subject', 'Communication about %s' % (prepid)).strip()
        mccm = MccM(json_input=mccm_json)
        mccm.notify(subject, message, accumulate=False)
        return {"results": True}


class GetEditableMccmFields(RESTResource):

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, mccm_id):
        """
        Retrieve the fields that are currently editable for a given mccm
        """
        mccm_db = Database('mccms')
        mccm = MccM(json_input=mccm_db.get(mccm_id))
        return {"results": mccm.get_editable()}


class GenerateChains(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, mccm_id):
        """
        Operate the chaining for a given MccM document id
        """
        args = flask.request.args
        # Reserve chains?
        reserve = args.get('reserve', 'false').lower() == 'true'
        # Limit reservation to campaign?
        limit_campaign = []
        if reserve:
            limit_campaign = args.get('limit', '').split(',')

        # Skip existing ones?
        skip_existing = flask.request.args.get('skip_existing', 'False').lower() == 'true'
        # Allow duplicated chained requests?
        allow_duplicates = flask.request.args.get('allow_duplicates', 'False').lower() == 'true'

        lock = locker.lock(mccm_id)
        if lock.acquire(blocking=False):
            try:
                res = self.generate(mccm_id, reserve, limit_campaign, skip_existing, allow_duplicates)
            finally:
                lock.release()
            return res
        else:
            return {"results": False,
                    "message": "%s is already being operated on" % (mccm_id)}

    def generate(self, mccm_id, reserve, limit_campaign, skip_existing, generate_all):
        mccm_db = Database('mccms')
        mccm_json = mccm_db.get(mccm_id)
        if not mccm_json:
            return {"results": False,
                    'message': '%s does not exist' % (mccm_id)}

        mccm = MccM(json_input=mccm_json)
        status = mccm.get_attribute('status')
        if status != 'new' and not skip_existing:
            return {"prepid": mccm_id,
                    "results": False,
                    "message": 'Status is "%s", expecting "new"' % (status)}

        block = mccm.get_attribute('block')
        if not block:
            return {"prepid": mccm_id,
                    "results": False,
                    "message": "No block selected"}

        chained_campaign_prepids = mccm.get_attribute('chains')
        if not chained_campaign_prepids:
            return {"prepid": mccm_id,
                    "results": False,
                    "message": "No chains selected"}

        if not mccm.get_attribute('requests'):
            return {"prepid": mccm_id,
                    "results": False,
                    "message": "No requests selected"}

        repetitions = mccm.get_attribute('repetitions')
        if not repetitions:
            return {"prepid": mccm_id,
                    "results": False,
                    "message": 'The number of repetitions "%s" is invalid' % (repetitions)}

        # Prepare limits dictionary
        if len(limit_campaign) == 1:
            # If there is one limit, set it to all
            limit_campaign = {c: limit_campaign[0] for c in chained_campaign_prepids}
        elif len(limit_campaign) == len(chained_campaign_prepids):
            # If there is same number of limits as chained campaigns, set 1 to 1
            limit_campaign = {cc: c for cc, c in zip(chained_campaign_prepids, limit_campaign)}
        elif len(limit_campaign):
            # If there is more than one, but not same number as chains
            return {"prepid": mccm_id,
                    "results": False,
                    "message": 'Number of limit campaigns must be the same as number of chains'}
        else:
            # No limit at all
            limit_campaign = {c: None for c in chained_campaign_prepids}

        # Make a set just to be sure they are unique
        request_prepids = sorted(list(set(mccm.get_request_list())))

        # Chained campaigns of ticket
        chained_campaign_db = Database('chained_campaigns')
        chained_campaigns = chained_campaign_db.bulk_get(chained_campaign_prepids)
        not_found_chained_campaigns = [c for c in chained_campaigns if not c]
        if not_found_chained_campaigns:
            not_found_ids = ', '.join(list(not_found_chained_campaigns))
            return {'prepid': mccm_id,
                    'results': False,
                    'message': 'Could not find %s chained campaigns' % (not_found_ids)}

        chained_campaigns = [ChainedCampaign(json_input=c) for c in chained_campaigns]
        # Requests of ticket
        request_db = Database('requests')
        requests = request_db.bulk_get(request_prepids)
        not_found_requests = [r for r in requests if not r]
        if not_found_requests:
            not_found_ids = ', '.join(list(not_found_requests))
            return {'prepid': mccm_id,
                    'results': False,
                    'message': 'Could not find %s requests' % (not_found_ids)}

        requests = [Request(json_input=r) for r in requests]
        # Root campaigns of chained campaigns
        root_campaigns = {}
        for chained_campaign in chained_campaigns:
            root_campaign = chained_campaign.get_attribute('campaigns')[0][0]
            root_campaigns.setdefault(root_campaign, []).append(chained_campaign)

        # Check requests
        chained_campaigns_for_requests = {}
        chained_request_db = Database('chained_requests')
        for request in requests:
            prepid = request.get_attribute('prepid')
            campaign = request.get_attribute('member_of_campaign')
            pwg = request.get_attribute('pwg')
            if campaign not in root_campaigns:
                return {"prepid" : mccm_id,
                        "results" : False,
                        "message" : '"%s" campaign is not in given chains' % (prepid)}

            if request.get_attribute('flown_with'):
                return {"prepid" : mccm_id,
                        "results" : False,
                        "message" : '"%s" is in the middle of the chain' % (prepid)}

            chained_campaigns_for_requests[prepid] = []
            for chained_campaign in root_campaigns[campaign]:
                chained_campaign_prepid = chained_campaign.get_attribute('prepid')
                query_dict = {'member_of_campaign': chained_campaign_prepid,
                              'contains': prepid,
                              'pwg': pwg}
                duplicates = chained_request_db.search(query_dict, limit=1)
                if duplicates and not generate_all:
                    if not skip_existing:
                        return {'prepid': mccm_id,
                                'results': False,
                                'message': 'Chain(s) with request "%s" and chained campaign "%s" '
                                           'already exist. ' % (prepid, chained_campaign_prepid)}
                else:
                    chained_campaigns_for_requests[prepid].append(chained_campaign)

        results = []
        generated_chains = mccm.get_attribute('generated_chains')
        for request in requests:
            request_prepid = request.get_attribute('prepid')
            self.logger.info("Generating chained requests for %s", request_prepid)
            chained_campaigns = chained_campaigns_for_requests[request_prepid]
            for chained_campaign in chained_campaigns:
                chained_campaign_prepid = chained_campaign.get_attribute('prepid')
                limit = limit_campaign[chained_campaign_prepid] or None
                for _ in range(repetitions):
                    generated= self.generate_chained_requests(mccm,
                                                              request,
                                                              chained_campaign,
                                                              reserve,
                                                              limit)
                    results.append(generated)
                    # A small delay to not crash DB
                    time.sleep(0.05)
                    generated_prepid = generated.get('prepid', '')
                    if not generated['results']:
                        return {"prepid": mccm_id,
                                "results": False,
                                "message": generated['message'],
                                'chained_request_prepid': generated_prepid}

                    generated_chains[generated_prepid] = generated['generated_requests']
                    mccm.set_attribute("generated_chains", generated_chains)
                    mccm.reload(save_current=True)
                    # A small delay to not crash DB
                    time.sleep(0.05)

        if not results:
            return {"prepid": mccm_id,
                    "results": False,
                    "message": "Everything went fine, but nothing was generated"}

        mccm.set_status()
        mccm_db.update(mccm.json())
        return {"prepid": mccm_id,
                "results": True,
                "message": results}

    def generate_chained_requests(self, mccm, request, chained_campaign, reserve, limit):
        chained_request = chained_campaign.generate_request(request)
        chained_request_prepid = chained_request.get_attribute('prepid')
        # Updates from the ticket
        block = mccm.get_attribute('block')
        action_parameters = chained_request.get_attribute('action_parameters')
        action_parameters.update({'block_number': block})

        if not chained_request.reload():
            return {'results': False,
                    'message': 'Unable to save chained request %s' % (chained_request_prepid)}

        # let the root request know that it is part of a chained request
        root_chains = request.get_attribute('member_of_chain')
        root_chains.append(chained_request_prepid)
        request.set_attribute('member_of_chain', sorted(list(set(root_chains))))
        request.update_history({'action': 'join chain', 'step': chained_request_prepid})
        request.reload()
        request_status = request.get_attribute('status')
        # do the reservation of the whole chain ?
        generated_requests = []
        if reserve:
            results_dict = chained_request.reserve(limit=limit, save_requests=False)
            if results_dict['results'] and 'generated_requests' in results_dict:
                generated_requests = results_dict['generated_requests']
                results_dict.pop('generated_requests')
            else:
                return {"results": False,
                        "prepid": chained_request_prepid,
                        "message": results_dict['message']}

        self.logger.info('Generated requests for %s are %s',
                         chained_request_prepid,
                         generated_requests)
        if request_status in ('approved', 'done'):
            # change priority of the whole chain
            self.logger.info('Setting block %s for %s' % (block, chained_request_prepid))
            chained_request.set_priority(block)
        elif request_status == 'submitted':
            # change priority only for the newly created requests
            new_priority = priority().priority(block)
            request_db = Database('requests')
            for request_prepid in generated_requests:
                generated_request = Request(json_input=request_db.get(request_prepid))
                self.logger.info('Setting priority %s for %s' % (new_priority, request_prepid))
                generated_request.change_priority(new_priority)

        return {"results":True,
                "prepid": chained_request_prepid,
                'generated_requests': generated_requests}


class MccMReminderGenContacts(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        """
        Send a reminder to the generator conveners about "new" MccM tickets that
        don't have all requests "defined"
        """
        mccm_db = Database('mccms')
        mccm_jsons = mccm_db.search({'status': 'new'}, page=-1)
        if not mccm_jsons:
            return {"results": True,
                    "message": "No new tickets, what a splendid day!"}

        l_type = locator()
        com = communicator()
        self.logger.info('Found %s new MccM tickets', len(mccm_jsons))
        # Quickly filter-out no request, no chain and 0 block ones
        mccm_jsons = [m for m in mccm_jsons if m['requests'] and m['chains'] and m['block']]
        mccm_jsons = sorted(mccm_jsons, key=lambda x: x['prepid'])
        mccms = [MccM(json_input=mccm_json) for mccm_json in mccm_jsons]
        # Get all defined but not approved requests
        not_defined_requests = {}
        for mccm in mccms:
            prepid = mccm.get_attribute('prepid')
            not_defined_requests[prepid] = mccm.get_not_defined()

        # Only tickets that have all requests at least defined, but not all
        # approved
        mccms = [mccm for mccm in mccms if len(not_defined_requests[mccm.get_attribute('prepid')])]

        by_pwg = {}
        for mccm in mccms:
            pwg = mccm.get_attribute('pwg')
            by_pwg.setdefault(pwg, []).append(mccm)

        subject_template = 'Gentle reminder about %s %s tickets'
        message_template = 'Dear GEN Contacts of %s,\n\n'
        message_template += 'Below you can find a list of MccM tickets where not all requests are '
        message_template += 'in "defined" status.\n'
        message_template += 'Please check them and once all are defined, present them in MccM or '
        message_template += 'cancel/delete tickets if they are no longer needed.\n\n'
        base_url = l_type.baseurl()
        contacts = self.get_contacts_by_pwg()
        for pwg, pwg_mccms in by_pwg.items():
            recipients = contacts.get(pwg)
            if not recipients:
                self.logger.info('No recipients for %s, will not remind about tickets', pwg)
                continue

            subject = subject_template % (len(pwg_mccms), pwg)
            message = message_template % (pwg)
            for mccm in pwg_mccms:
                prepid = mccm.get_attribute('prepid')
                not_defined = len(not_defined_requests[prepid])
                total = len(mccm.get_request_list())
                message += 'Ticket: %s (%s/%s request(s) are not defined)\n' % (prepid,
                                                                                    not_defined,
                                                                                    total)
                message += '%smccms?prepid=%s\n\n' % (base_url, prepid)

            message += 'You received this email because you are listed as GEN contact of %s.\n' % (pwg)
            com.sendMail(recipients, subject, message)

        return {"results": True,
                "message": [mccm.get_attribute('prepid') for mccm in mccms]}


    def get_contacts_by_pwg(self):
        """
        Get list of generator contact emails by PWG
        """

        user_db = Database('users')
        generator_contacts = user_db.query_view('role', 'generator_contact', page_num=-1)
        by_pwg = {}
        for contact in generator_contacts:
            for pwg in contact.get('pwg', []):
                by_pwg.setdefault(pwg, []).append(contact['email'])

        return by_pwg


class MccMReminderProdManagers(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        """
        Send a reminder to the production managers about "new" MccM tickets that
        have all requests "approved"
        """
        mccm_db = Database('mccms')
        mccm_jsons = mccm_db.search({'status': 'new'}, page=-1)
        if not mccm_jsons:
            return {"results": True,
                    "message": "No new tickets, what a splendid day!"}

        l_type = locator()
        com = communicator()
        self.logger.info('Found %s new MccM tickets', len(mccm_jsons))
        # Quickly filter-out no request, no chain and 0 block ones
        mccm_jsons = [m for m in mccm_jsons if m['requests'] and m['chains'] and m['block']]
        def sort_attr(mccm):
            return (mccm['meeting'], 100000 - int(mccm['prepid'].split('-')[-1]))

        def comma_separate_thousands(number):
            return '{:,}'.format(int(number))

        mccm_jsons = sorted(mccm_jsons, key=sort_attr, reverse=True)
        mccms = [MccM(json_input=mccm_json) for mccm_json in mccm_jsons]
        mccms = [mccm for mccm in mccms if mccm.all_requests_approved()]
        self.logger.info('Have %s MccM tickets after filters', len(mccms))
        # Email
        subject = 'Gentle reminder about %s approved tickets' % (len(mccms))
        message = 'Dear Production Managers,\n\n'
        message += 'Below you can find a list of MccM tickets in status "new" '
        message += 'that have all requests "approved".\n'
        message += 'You can now operate on them or delete/cancel unneeded ones.\n'
        by_pwg = {}
        for mccm in mccms:
            pwg = mccm.get_attribute('pwg')
            by_pwg.setdefault(pwg, []).append(mccm)

        base_url = l_type.baseurl()
        for pwg in sorted(list(by_pwg.keys())):
            pwg_mccms = by_pwg[pwg]
            message += '\n%s (%s tickets)\n' % (pwg, len(pwg_mccms))
            for mccm in pwg_mccms:
                prepid = mccm.get_attribute('prepid')
                block = mccm.get_attribute('block')
                events = comma_separate_thousands(mccm.get_attribute('total_events'))
                message += '  Ticket: %s (block %s and %s events)\n' % (prepid, block, events)
                message += '  %smccms?prepid=%s\n\n' % (base_url, prepid)

        user_db = Database('users')
        production_managers = user_db.query_view('role', 'production_manager', page_num=-1)
        recipients = [manager['email'] for manager in production_managers]
        com.sendMail(recipients, subject, message)
        return {"results": True,
                "message": [mccm.get_attribute('prepid') for mccm in mccms]}


class MccMReminderGenConveners(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        """
        Send a reminder to the generator conveners about "new" MccM tickets that
        don't have all requests "approved"
        """
        mccm_db = Database('mccms')
        mccm_jsons = mccm_db.search({'status': 'new'}, page=-1)
        if not mccm_jsons:
            return {"results": True,
                    "message": "No new tickets, what a splendid day!"}

        l_type = locator()
        com = communicator()
        self.logger.info('Found %s new MccM tickets', len(mccm_jsons))
        # Quickly filter-out no request, no chain and 0 block ones
        mccm_jsons = [m for m in mccm_jsons if m['requests'] and m['chains'] and m['block']]
        mccm_jsons = sorted(mccm_jsons, key=lambda x: x['prepid'])
        mccms = [MccM(json_input=mccm_json) for mccm_json in mccm_jsons]
        # Get all defined but not approved requests
        defined_requests = {}
        for mccm in mccms:
            prepid = mccm.get_attribute('prepid')
            defined_requests[prepid] = mccm.get_defined_but_not_approved_requests()
        # Only tickets that have all requests at least defined, but not all
        # approved
        mccms = [mccm for mccm in mccms if len(defined_requests[mccm.get_attribute('prepid')])]
        self.logger.info('Have %s MccM tickets after filters', len(mccms))
        # Email
        subject = 'Gentle reminder about %s tickets that need approval' % (len(mccms))
        message = 'Dear GEN Conveners,\n\n'
        message += 'Below you can find a list of MccM tickets in status "new" '
        message += 'that have all requests "defined", but not all "approved".\n'
        message += 'You need to check the remaining requests and approve them '
        message += 'if they are correct and were presented in a meeting.\n'
        by_meeting_pwg = {}
        for mccm in mccms:
            pwg = mccm.get_attribute('pwg')
            meeting = mccm.get_attribute('meeting')
            by_meeting_pwg.setdefault(meeting, {}).setdefault(pwg, []).append(mccm)

        base_url = l_type.baseurl()
        for meeting in sorted(list(by_meeting_pwg.keys()), reverse=True):
            by_meeting = by_meeting_pwg[meeting]
            ticket_count = sum(len(mccms) for _, mccms in by_meeting.items())
            message += '\nMeeting %s (%s tickets)\n' % (meeting, ticket_count)
            for pwg in sorted(list(by_meeting.keys())):
                pwg_mccms = by_meeting[pwg]
                message += '  %s (%s tickets)\n' % (pwg, len(pwg_mccms))
                for mccm in pwg_mccms:
                    prepid = mccm.get_attribute('prepid')
                    defined = len(defined_requests[prepid])
                    total = len(mccm.get_request_list())
                    message += '    Ticket: %s (%s/%s request(s) are not approved)\n' % (prepid,
                                                                                         defined,
                                                                                         total)
                    message += '    %smccms?prepid=%s\n\n' % (base_url, prepid)


        user_db = Database('users')
        generator_conveners = user_db.query_view('role', 'generator_convener', page_num=-1)
        recipients = [manager['email'] for manager in generator_conveners]
        com.sendMail(recipients, subject, message)
        return {"results": True,
                "message": [mccm.get_attribute('prepid') for mccm in mccms]}


class CalculateTotalEvts(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, mccm_id):
        """
        Force to recalculate total_events for ticket
        """
        mccm_db = Database('mccms')
        mccm_json = mccm_db.get(mccm_id)
        if not mccm_json:
            return {"results": False,
                    'message': '%s does not exist' % (mccm_id)}

        mccm = MccM(json_input=mccm_json)
        mccm.update_total_events()
        if not mccm_db.update(mccm.json()):
            return {"results": False,
                    "message": "Could not save to the database"}

        return {'results': True}


class CheckIfAllApproved(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, mccm_id):
        """
        Return whether all requests in MccM are approve-approved
        """
        mccm_db = Database('mccms')
        mccm_json = mccm_db.get(mccm_id)
        if not mccm_json:
            return {"results": False,
                    'message': '%s does not exist' % (mccm_id)}

        mccm = MccM(json_input=mccm_json)
        requests_prepids = mccm.get_request_list()
        request_db = Database('requests')
        requests = request_db.bulk_get(requests_prepids)
        requests_prepids = set(requests_prepids)
        allowed_approvals = {'approve', 'submit'}
        for request in requests:
            if not request:
                continue

            requests_prepids.remove(request['prepid'])
            if request.get('approval') not in allowed_approvals:
                return {'results': False}

        if requests_prepids:
            return {'results': False,
                    'message': 'Request(s) %s do not exist' % (', '.join(list(requests_prepids)))}

        return {'results': True}
