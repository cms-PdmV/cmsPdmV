from urllib import request
from json_layer.chained_campaign import ChainedCampaign

from json_layer.json_base import json_base
from json_layer.request import Request
from json_layer.campaign import Campaign
from json_layer.flow import Flow
from couchdb_layer.mcm_database import database as Database
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

    def __bool__(self):
        """
        Return that object is truthy
        """
        return True

    def current(self):
        """
        Return prepid of current step
        """
        return self[self.get('step')]

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
        self.logger.info('Request %s is joining %s', request_prepid, chain_prepid)
        # Update request
        chains = request.get_attribute('member_of_chain')
        if chain_prepid not in chains:
            self.logger.info('Adding %s to %s', chain_prepid, request_prepid)
            request.set_attribute('member_of_chain', sorted(chains + [chain_prepid]))
            request.update_history('join chain', chain_prepid)

        # Update chained request
        chain = self.get_attribute('chain')
        if request_prepid not in chain:
            self.logger.info('Adding %s to %s', request_prepid, chain_prepid)
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

    def flow(self, reserve=False, trigger_others=True):
        """
        Flow chained request further
        Flowing will go as long as flow types are "together"
        If possible, reuse requests, if not - create new ones
        """
        prepid = self.get('prepid')
        self.logger.info('Flowing %s', prepid)
        chain = self.get('chain')
        if not chain:
            # Empty chained requests are not valid, they must have at least a
            # root request
            raise Exception('Chained request is missing root request')

        if not self.get('enabled'):
            raise Exception('Chained request is not enabled')

        # Fetch chained campaign and check if it is enabled
        chained_campaign_id = self.get('member_of_campaign')
        chained_campaign = ChainedCampaign.fetch(chained_campaign_id)
        if not chained_campaign.get('enabled'):
            raise Exception(f'Chained campaign {chained_campaign_id} is not enabled')

        # Current step and next step indices
        current_step = self.get('step')
        next_step = current_step + 1
        if next_step >= len(chained_campaign):
            raise Exception('Chained campaign does not allow any futher flowing')

        # Fetch root request as it will be needed when searching for requests
        # that could be reused
        root_request_id = chain[0]
        root_request = Request.fetch(root_request_id)

        start_flowing_at = self.current()
        other_chains_to_flow = set()
        next_request = None
        while next_step < len(chained_campaign):
            current_id = chain[current_step]
            next_flow_id = chained_campaign.flow(next_step)
            next_campaign_id = chained_campaign.campaign(next_step)
            self.logger.info('Flowing %s to step %s/%s (%s + %s)',
                             prepid,
                             next_step + 1,
                             len(chained_campaign),
                             next_flow_id,
                             next_campaign_id)
            self.logger.info('Current step %s in chain %s', current_id, ', '.join(chain))
            # Next campaign
            next_campaign = Campaign.fetch(next_campaign_id)
            if not next_campaign.is_started():
                raise Exception(f'Campaign {next_campaign_id} is not started')

            # Next flow
            next_flow = Flow.fetch(next_flow_id)
            next_flow_approval = next_flow.get('approval')
            if next_flow_approval == 'none':
                raise Exception(f'Flow {next_flow_id} is {next_flow_approval}')

            # Current request
            if current_id == root_request_id:
                current_request = root_request
            else:
                current_request = Request.fetch(current_id)

            current_status = current_request.get_approval_status()
            self.logger.info('Current request %s status %s', current_id, current_status)
            if not reserve:
                if current_id != start_flowing_at:
                    # During normal flow, stop when next flow is not "together"
                    self.logger.info('Next flow %s type is "%s"', next_flow_id, next_flow_approval)
                    if next_flow_approval != 'together':
                        break
                else:
                    # When trying to flow to after_done, current request must be
                    # submit-done
                    if next_flow_approval == 'after_done' and current_status != 'submit-done':
                        raise Exception(f'Flow {next_flow_id} type is "{next_flow_approval}", '
                                        f'but {current_id} is {current_status}')

            next_request = self.get_request_for_step(next_step, root_request, current_request, next_flow, next_campaign)
            next_request_id = next_request.get('prepid')
            self.logger.info('Next request %s (%s)',
                             next_request_id,
                             next_request.get_approval_status())
            # TODO: set next request to "approved"?
            self.request_join(next_request)
            if trigger_others:
                for chain_prepid in current_request.get('member_of_chain'):
                    other_chained_request = ChainedRequest.fetch(chain_prepid)
                    if other_chained_request.current() == current_id:
                        other_chains_to_flow.add(chain_prepid)

            # Reset options for the next request
            next_request.reload(save=False)
            if next_request.get('approval') != 'submit':
                next_request.reset_options()
                # Output dataset as input for the next request if available
                current_output = current_request.get('output_dataset')
                if current_output:
                    input_dataset = next_request.get_input_dataset(current_output)
                    if input_dataset:
                        self.logger.info('Will use %s from %s as input to %s',
                                        input_dataset,
                                        current_id,
                                        next_request_id)
                        next_request.set_attribute('input_dataset', input_dataset)

                next_request.change_priority(self.get('priority'))

            if not next_request.save():
                raise Exception('Could not save next request %s to the database' % (next_request_id))

            if not reserve:
                self.set_attribute('step', current_step)

            self.update_history('flow', next_request_id)
            # Prepare for next iteration
            current_step += 1
            next_step = current_step + 1

        if not reserve:
            # Do not flow itself again
            other_chains_to_flow -= {prepid}
            for other_chain in sorted(list(other_chains_to_flow)):
                chained_request = ChainedRequest.fetch(other_chain)
                chained_request.flow(trigger_others=False)
                chained_request.reload()

        if not reserve:
            # sync last status
            self.set_last_status()
            # we can only be processing at this point
            self.set_attribute('status', 'processing')

        return self

    def get_request_for_step(self, step, root_request, current_request, next_flow, next_campaign):
        """
        Return existing in chain, existing elsewhere or create a new request
        """
        prepid = self.get('prepid')
        # Get the next request in the chain
        if step < len(self):
            # Next request is already in the chain
            next_request_id = self[step]
            self.logger.info('Next request %s is in the chain - use it', next_request_id)
            next_request = Request.fetch(next_request_id)
        else:
            # Next request is NOT in the chain
            # Try to reuse existing requests by looking at other chains
            # Requests should come from chained requests with same root
            next_request = self.find_request_to_reuse(root_request, step)
            if next_request:
                next_request_id = next_request.get('prepid')
                self.logger.info('Found request %s to reuse in %s', next_request_id, prepid)
            else:
                self.logger.info('Could not find request to reuse for %s', prepid)

        request_data = {'pwg': current_request.get('pwg'),
                        'member_of_campaign': next_campaign.get('prepid'),
                        'process_string': current_request.get('process_string'),
                        'extension': current_request.get('extension'),
                        'dataset_name': current_request.get('dataset_name'),
                        'generators': current_request.get('generators'),
                        'flown_with': next_flow.get('prepid'),
                        'interested_pwg': current_request.get('interested_pwg'),}

        if next_request:
            if next_request.get('approval') != 'submit':
                # If request is not submitted, update it's info
                for key, value in request_data.items():
                    next_request.set(key, value)
        else:
            self.logger.info('Creating a request for %s (%s + %s + %s)',
                             prepid,
                             request_data['pwg'],
                             request_data['flown_with'],
                             request_data['member_of_campaign'])
            from rest_api.RequestFactory import RequestFactory
            # Create new request from the data for the next request
            next_request = RequestFactory.make(request_data)
            next_request_id = next_request.get('prepid')
            self.logger.info('Created new request %s for chain %s', next_request_id, prepid)

        next_request.set('total_events', self.get_next_request_events(current_request, next_request))
        return next_request

    def get_next_request_events(self, current_request, next_request):
        """
        Get number of total events for the next request request
        Take number of completed/total events of current request and filter
        efficiency of next request
        """
        if current_request.get_attribute('status') != 'done':
            current_request.get_stats()

        statistics_fraction = Settings.get('statistics_fraction')
        current_completed_events = current_request.get('completed_events')
        current_total_events = current_request.get('total_events')
        current_keeps_output = current_request.keeps_output()
        min_events = int(current_total_events * statistics_fraction)
        if current_completed_events <= min_events and current_keeps_output:
            raise Exception('%s keeps output, but has only %s completed events, at least '
                            '%s are required' % (current_request.get('prepid'),
                                                 current_completed_events,
                                                 min_events,
                                                 ))

        next_events = int(current_completed_events * next_request.get_efficiency())
        return next_events

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


    def rewind(self):
        """
        Rewind chained request by one step
        Also move step back in related chained requests
        """
        step = self.get('step')
        if step == 0:
            raise Exception('Already at the root')

        # Most of the logic revolves around request that is current step of the
        # given chained request
        current_prepid = self.current()
        current_request = Request.fetch(current_prepid)
        # Chained requests of request that is current step of the chain
        chained_requests = [ChainedRequest(cr) for cr in current_request.get_chained_requests()]
        # Simple check first - if other chained requests have same current step
        for chained_request in chained_requests:
            if chained_request.get('prepid') == self.get('prepid'):
                continue

            step = chained_request.get('step')
            chain = chained_request.get('chain')
            if chain.index(current_prepid) < step:
                raise Exception('Rewind %s first' % (chained_request.get('prepid')))

        # More demanding request check - if requests "down the chain" in this
        # and in all other chains are already reset
        request_db = Database('requests')
        checked_requests = set()
        for chained_request in chained_requests:
            prepid = chained_request.get('prepid')
            chain = chained_request.get('chain')
            # Only leave requests after the "current" request
            chain = chain[chain.index(current_prepid) + 1:]
            request_ids = [r for r in list(reversed(chain)) if r not in checked_requests]
            requests = request_db.bulk_get(request_ids)
            for request_id, request in zip(request_ids, requests):
                if not request:
                    raise Exception('%s is part of %s but does not exist' % (request_id, prepid))

                request_status = '%s-%s' % (request['approval'], request['status'])
                if request_status != 'none-new':
                    raise Exception('%s is after %s but is not new' % (request_id, current_prepid))

        # Move step back in all chained requests
        for chained_request in chained_requests:
            chain_prepid = chained_request.get('prepid')
            step = chained_request.get('step')
            chain = chained_request.get('chain')
            chained_request.set('step', chain.index(current_prepid) - 1)
            chained_request.set_last_status()
            chained_request.set('status', 'processing')
            if not chained_request.save():
                raise Exception('Could not save %s' % (chain_prepid))

        # Reload after save above
        self.reload(save=False)
        # Reset request that was current before reset
        if current_request.get_approval_status() != 'none-new':
            current_request.reset(soft=False)

        current_request.set_attribute('input_dataset', '')
        if not current_request.save():
            raise Exception('Could not save %s' % (current_prepid))

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
