import time
import json
from json_layer.chained_campaign import ChainedCampaign

from json_layer.json_base import json_base
from json_layer.request import Request
from json_layer.campaign import Campaign
from json_layer.mccm import MccM
from json_layer.flow import Flow
from couchdb_layer.mcm_database import database as Database
from tools.locker import locker
from tools.locator import locator
from tools.settings import Settings


class ChainedRequest(json_base):

    _json_base__status = ['new', 'processing', 'done', 'force_done']

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'chain': [],
        'dataset_name': '',
        'enabled': True,
        'history': [],
        'last_status': 'new',
        'member_of_campaign': '',
        'priority': 0,
        'pwg': '',
        'status': '',
        'step': 0,
        'threshold': 0,
        'validate': False,  # Whether the chain should be validated
    }

    def __getitem__(self, index):
        """
        Given index, return request prepid at index in the chain
        """
        return self.get_attribute('chain')[index]

    def __len__(self):
        """
        Return length of chain
        """
        return len(self.get_attribute('chain'))

    @classmethod
    def get_database(cls):
        """
        Return shared database instance
        """
        if not hasattr(cls, 'database'):
            cls.database = Database('chained_requests')

        return cls.database

    def request_join(self, request):
        """
        Update request's member of chain and history
        Add request's prepid to the chain
        """
        chain_prepid = self.get('prepid')
        request_prepid = request.get('prepid')
        # Update request
        chains = request.get_attribute('member_of_chain')
        if chain_prepid not in chains:
            request.set_attribute('member_of_chain', sorted(chains + [chain_prepid]))
            request.update_history('join chain', chain_prepid)

        # Update chained request
        chain = self.get_attribute('chain')
        if request_prepid not in chain:
            chain.append(request_prepid)
            self.set_attribute('chain', chain)
            self.update_history('add request', request_prepid)

    def reserve(self, limit=None, save_requests=True):
        steps = 0
        count_limit = 35
        campaign_limit = None
        if limit:
            self.logger.info('limit: %s was passed on to reservation.' % (limit))
            if limit.__class__ == bool:
                campaign_limit = None
            elif limit.isdigit():
                count_limit = int(limit)
            else:
                campaign_limit = limit
        generated_requests = []
        while True:
            steps += 1
            if count_limit and steps > count_limit:
                # stop here
                break
            try:
                results_dict = self.flow_to_next_step(check_stats=False, reserve=True, stop_at_campaign=campaign_limit)
                if not results_dict['result']:
                    break
                saved = self.reload()
                if not saved:
                    return {
                        "prepid": self.get_attribute("prepid"),
                        "results": False,
                        "message": "Failed to save chained request to database"}
                if 'generated_request' in results_dict:
                    generated_requests.append(results_dict['generated_request'])
            except Exception as ex:
                return {
                    "prepid": self.get_attribute("prepid"),
                    "results": False,
                    "message": str(ex)}
        if save_requests:
            self.save_requests(generated_requests)
            return {
                "prepid": self.get_attribute("prepid"),
                "results": True}
        return {
            "prepid": self.get_attribute("prepid"),
            "results": True,
            'generated_requests': generated_requests}

    def save_requests(self, generated_requests):
        chain_id = self.get_attribute('prepid')
        mccm_ticket = mccm.get_mccm_by_generated_chain(chain_id)
        if mccm_ticket is not None:
            mccm_ticket.update_mccm_generated_chains({chain_id: generated_requests})

    def get_setup(self, for_validation, automatic_validation, scratch=False):
        if scratch:
            req_ids = self.get_attribute('chain')
        else:
            req_ids = self.get_attribute('chain')[self.get_attribute('step'):]

        rdb = database('requests')
        setup_file = ''
        for req_id in req_ids:
            req = request(rdb.get(req_id))
            if not req.is_root and 'validation' not in req._json_base__status:  # do it only for root or possible root request
                break

            setup_file += req.get_setup_file2(for_validation=for_validation, automatic_validation=automatic_validation, threads=1)

        return setup_file

    def flow(self, reserve=False, stop_at_campaign=None):
        """
        Flow chained request one step further
        If possible, reuse requests, if not - create new ones
        """
        prepid = self.get('prepid')
        self.logger.info('Flowing chained request %s to next step, reserve=%s', prepid, reserve)
        chain = self.get('chain')
        if not chain:
            # Empty chained requests are not valid, they must have at least a
            # root request
            raise Exception('Chained request %s has no requests' % (prepid))

        if not self.get('enabled'):
            return {'results': False,
                    'message': 'Chained request is not enabled'}

        if not reserve:
            # Normally the chain's step is the current step
            current_step = self.get('step')
        else:
            # During reservation, step is not moved, so this needs to point to
            # the last available request in the chain
            current_step = len(chain) - 1

        current_prepid = chain[current_step]
        next_step = current_step + 1
        chained_campaign_id = self.get('member_of_campaign')
        chained_campaign = ChainedCampaign.fetch(chained_campaign_id)

        if next_step >= len(chained_campaign):
            return {'result': False,
                    'message': 'Chained request does not allow any futher flowing'}

        if not chained_campaign.get('enabled'):
            return {'result': False,
                    'message': 'Chained campaign is not enabled'}

        next_flow_id = chained_campaign.flow(next_step)
        next_campaign_id = chained_campaign.campaign(next_step)

        self.logger.debug('Flowing %s to step %s/%s (%s + %s)',
                          prepid,
                          next_step + 1,
                          len(chained_campaign),
                          next_flow_id,
                          next_campaign_id)

        current_request = Request.fetch(current_prepid)
        current_campaign_id = current_request.get('member_of_campaign')
        if reserve and stop_at_campaign == current_campaign_id:
            return {'result': False,
                    'message': 'Reached limit'}

        current_campaign = Campaign.fetch(current_campaign_id)
        next_campaign = Campaign.fetch(next_campaign_id)
        if not next_campaign.get_attribute('status') == 'started':
            return {'results': False,
                    'message': 'Campaign %s is not started' % (next_campaign)}

        if not reserve:
            # If not reserving a chain, current step must be done
            current_request_status = current_request.get_approval_status()
            if current_request_status != 'submit-done':
                return {'results': False,
                        'message': 'Cannot flow, %s is %s and not submit-done' (current_prepid,
                                                                                current_request_status)}

        # Get root request
        root_request_id = chain[0]
        if root_request_id == current_prepid:
            root_request = current_request
        else:
            root_request = Request.fetch(root_request_id)

        next_campaign = Campaign.fetch(next_campaign_id)
        if next_campaign.get('energy') != current_campaign.get('energy'):
            return {'results': False,
                    'message': 'Cannot flow %s, inconsistent energy in %s' % (prepid, next_campaign_id)}

        next_flow = Flow.fetch(next_flow_id)
        if not next_flow.get('approval') == 'none':
            return {'results': False,
                    'message': 'Flow %s does not allow flowing' % (next_flow_id)}

        next_events = current_request.get('total_events')
        # Check if current request produced at least 5% of expected events
        if not reserve:
            if current_request.get_attribute('status') != 'done':
                current_request.get_stats()

            statistics_fraction = Settings.get('statistics_fraction')
            current_completed_events = current_request.get('completed_events')
            current_total_events = current_request.get('total_events')
            current_keeps_output = current_request.keeps_output()
            min_events = int(current_total_events * statistics_fraction)
            if current_completed_events <= min_events and current_keeps_output:
                raise Exception('%s keeps output, but has only %s completed events, at least '
                                '%s are required. Will not flow %s' % (current_prepid,
                                                                       current_completed_events,
                                                                       min_events,
                                                                       prepid))

            next_events = int(current_completed_events * current_request.get_efficiency())

        # Get the next request in the chain
        if next_step < len(self):
            # Next request is already in the chain
            next_request_id = chain[next_step]
            self.logger.debug('Next request %s is in the chain - use it', next_request_id)
            next_request = Request.fetch(next_request_id)
        else:
            # Next request is NOT in the chain
            # Try to reuse existing requests by looking at other chains
            # Requests should come from chained requests with same root
            next_request = self.find_request_to_reuse(root_request, next_step)

        next_request_data = {'pwg': current_request.get('pwg'),
                             'member_of_campaign': next_campaign_id,
                             'process_string': current_request.get('process_string'),
                             'extension': current_request.get('extension'),
                             'dataset_name': current_request.get('dataset_name'),
                             'generators': current_request.get('generators'),
                             'total_events': next_events,
                             'flown_with': next_flow_id,
                             'interested_pwg': current_request.get('interested_pwg'),}
        if next_request:
            self.logger.info('Next request already exists - %s', next_request.get('prepid'))
            if next_request.get('approval') != 'submit':
                # If request is not submitted, update it's info
                for key, value in next_request_data.items():
                    next_request.set(key, value)
        else:
            self.logger.info('Next request does not exist and should be created')
            from rest_api.RequestFactory import RequestFactory
            # Create new request from the data for the next request
            next_request = RequestFactory.make(next_request_data)
            self.logger.info('Created new request %s for chain %s',
                             next_request.get('prepid'),
                             prepid)

        next_request_id = next_request.get('prepid')
        self.request_join(next_request)

        # Move current step in other chains to this request too
        # TODO: trigger/flow other chains of current_request

        # for other_chained_request_prepid in next_request.get_attribute('member_of_chain'):
        #     if other_chained_request_prepid == self.get_attribute('prepid'):
        #         # Skipping itself
        #         continue

        #     other_chained_request = crdb.get(other_chained_request_prepid)
        #     if other_chained_request['chain'].index(next_id) > other_chained_request['step']:
        #         other_chained_request['step'] = other_chained_request['chain'].index(next_id)
        #         crdb.save(other_chained_request)

        # Reset options for the next request
        if next_request.get('approval') != 'submit':
            next_request.reset_options()
            # Output dataset as input for the next request if available
            current_output = current_request.get('output_dataset')
            if current_output:
                input_dataset = next_request.get_input_dataset(current_output)
                if input_dataset:
                    self.logger.info('Will use %s from %s as input to %s',
                                    input_dataset,
                                    current_prepid,
                                    next_request_id)
                    next_request.set_attribute('input_dataset', input_dataset)

            next_request.change_priority(self.get('priority'))

        if not next_request.save():
            raise Exception('Could not save next request %s to the database' % (next_request_id))

        if not reserve:
            # sync last status
            self.set_attribute('last_status', next_request.get_attribute('status'))
            # we can only be processing at this point
            self.set_attribute('status', 'processing')
            # set to next step
            self.set_attribute('step', next_step)
            self.update_history('flow', next_request_id)

        return next_request

    def find_request_to_reuse(self, root_request, next_step):
        """
        Find and return a request that could be reused as `next_step` of this
        chained request
        If no request could be found, return None indicating that request should
        be created
        """
        prepid = self.get('prepid')
        campaign_id = self.get_attribute('member_of_campaign')
        chained_request_ids = root_request['member_of_chain']
        self.logger.debug('Chained request %s is flowing, next step - %s', prepid, next_step)
        self.logger.debug('Root request %s is member of %s chained requests',
                          root_request.get('prepid'),
                          len(chained_request_ids))
        # Remove current chained request
        chained_request_ids = [p for p in chained_request_ids if p != prepid]
        # Remove chained requests in the same chained campaign
        chained_request_ids = [p for p in chained_request_ids if '-%s-' % (campaign_id) not in p]
        # Sort by matching length
        def matching_length(a, b):
            a_parts = tuple(a.split('-')[1].split('_'))
            b_parts = tuple(b.split('-')[1].split('_'))
            for i in range(min(len(a_parts), len(b_parts)), 0, -1):
                if a_parts[:i] == b_parts[:i]:
                    return i - 1

            return 0

        # Save matching length
        chained_request_ids = [(c, matching_length(c, prepid)) for c in chained_request_ids]
        # Remove ones that are not macthing enough to reach next step
        chained_request_ids = [c for c in chained_request_ids if c[1] > next_step]
        # Sort by matching length
        chained_request_ids = sorted(chained_request_ids, key=lambda c: c[1], reverse=True)
        # Get existing chain
        chain = self.get_attribute('chain')
        # Do not proceed if none of the ids fit
        if not chained_request_ids:
            return None

        # Store matching length in dictionary
        matching = dict(chained_request_ids)
        chained_request_db = Database('chained_requests')
        chained_requests = chained_request_db.bulk_get([c[0] for c in chained_request_ids])
        # Remove all that are not long enough
        chained_requests = [c for c in chained_requests if len(c) > next_step]
        self.logger.debug('%s chained requests are long enough, at least %s length:\n%s',
                          len(chained_requests),
                          next_step + 1,
                          '\n'.join('%s - %s' % (c['prepid'], len(c)) for c in chained_requests))

        # All requests in the chain must match up to current step
        self.logger.debug('Making sure these match: %s', chain[:next_step])
        chained_requests = [c for c in chained_requests
                            if c['chain'][:next_step] == chain[:next_step]]
        checked_requests = set()

        # Check if requests in chain save the output
        request_db = Database('requests')
        for candidate in chained_requests:
            self.logger.debug('Looking at %s, chain: %s, matching: %s',
                              candidate['prepid'],
                              '->'.join(candidate['chain']),
                              matching[candidate['prepid']])

            match = matching[candidate['prepid']]
            # This is part starting at next request and ending at last
            # matching request. At least one of them should save
            # output or be not-submitted and not-done
            other_chain = candidate['chain'][len(chain):match]
            self.logger.debug('Relevant part of chain: %s', other_chain)
            # Do not check same requests twice
            other_chain = [o for o in other_chain if o not in checked_requests]
            if not other_chain:
                continue

            other_requests = request_db.bulk_get(other_chain)
            for other_request in other_requests:
                other_prepid = other_request['prepid']
                other_keep_output = other_request['keep_output'][-1]
                other_approval = other_request['approval']
                self.logger.debug('Other request %s keep output: %s and approval: %s',
                                    other_request['prepid'],
                                    other_keep_output,
                                    other_approval)
                checked_requests.add(other_prepid)
                if other_approval != 'submit' or other_keep_output:
                    # Important to take the first request from the checked
                    # part of the chain, not the matching request!
                    return other_requests[0]['prepid']

            self.logger.info('None of available requests of %s are suitable',
                             candidate['prepid'])

        return None


    def set_last_status(self, status=None):
        """
        Update last status of the chained request
        If status is None, fetch the request first
        """
        if status is None:
            request = Request.fetch(self[self.get('step')])
            status = request.get('status')

        if status == self.get_attribute('last_status'):
            return False

        self.update_history('set last status', status)
        self.set_attribute('last_status', status)
        return True

    def set_processing_status(self, pid=None, status=None):
        if pid == self.get_attribute('chain')[self.get_attribute('step')]:
            cdb = database("chained_campaigns")
            chained_camp = cdb.get(self.get_attribute("member_of_campaign"))
            # we do -1 as chained_request step counts from 0
            expected_end = len(chained_camp["campaigns"]) - 1
            current_status = self.get_attribute('status')
            # the current request is the one the status has just changed
            self.logger.info('processing status %s given %s and at %s and stops at %s ' % (current_status, status, self.get_attribute('step'), expected_end))

            if self.get_attribute('step') == expected_end and status == 'done' and current_status == 'processing':
                # you're supposed to be in processing status
                self.set_status()
                return True
            # only when updating with a submitted request status do we change to processing
            if status in ['submitted'] and current_status == 'new':
                self.set_status()
                return True
            return False
        else:
            return False

    def set_priority(self, priority):
        request_db = Database('requests')
        at_least_one_changed = False
        for request_prepid in self.get_attribute('chain'):
            request = Request(request_db.get(request_prepid))
            if request.change_priority(priority):
                at_least_one_changed = True

        return at_least_one_changed

    def inspect(self):
        not_good = {"prepid": self.get_attribute('prepid'), "results": False}

        if self.get_attribute('status') == 'force_done':
            not_good.update({'message': 'cannot inspect in force_done status'})
            return not_good

        if self.get_attribute('last_status') == 'done':
            return self.inspect_done()

        not_good.update({'message': 'Nothing to inspect on chained request in %s last status' % (self.get_attribute('last_status'))})
        return not_good

    def inspect_done(self):
        return self.flow_trial()

    def reset_requests(self, message, what='Chained validation run test', notify_one=None, except_requests=[]):
        request_db = database('requests')
        for request_prepid in self.get_attribute('chain')[self.get_attribute('step'):]:
            mcm_request = request(request_db.get(request_prepid))
            if not mcm_request.is_root and 'validation' not in mcm_request._json_base__status:
                break
            if request_prepid in except_requests:
                continue
            # If somebody changed a request during validation, let's keep the changes
            if mcm_request.get_attribute('status') != 'new':
                subject = '%s failed for request %s' % (what, mcm_request.get_attribute('prepid'))
                mcm_request.notify(subject, message)
                continue
            notify = True
            if notify_one and notify_one != request_prepid:
                notify = False
            mcm_request.test_failure(message, what=what, rewind=True, with_notification=notify)
        chained_requests_db = database('chained_requests')
        self.set_attribute('validate', 0)
        if not chained_requests_db.update(self.json()):
            subject = 'Chained validation run test'
            message = 'Problem saving changes in chain %s, set validate = False ASAP!' % self.get_attribute('prepid')
            self.notify(subject, message)
