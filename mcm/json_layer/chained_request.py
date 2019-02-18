import time

from json_base import json_base
from json_layer.request import request
from json_layer.campaign import campaign
from json_layer.notification import notification
from json_layer.mccm import mccm
from flow import flow
from couchdb_layer.mcm_database import database
from tools.priority import priority
from tools.locker import locker
from tools.locator import locator
import tools.settings as settings


class chained_request(json_base):
    class CampaignAlreadyInChainException(Exception):
        def __init__(self, campaign):
            self.c = campaign
            chained_request.logger.error('Campaign %s is already member of the chain.' % self.c)

        def __str__(self):
            return 'Error: Campaign', self.c, 'already represented in the chain.'

    class ChainedRequestCannotFlowException(Exception):
        def __init__(self, crname, message='cannot flow any further'):
            self.name = str(crname)
            self.message = message
            chained_request.logger.error('Chained request %s %s.' % (self.name, self.message))

        def __str__(self):
            return 'Chained request %s %s.' % (self.name, self.message)

    class NotApprovedException(Exception):
        def __init__(self, oname, alevel, allowed):
            self.name = str(oname)
            self.level = str(alevel)
            self.allowed = ' or '.join(map(lambda s: '"%s"' % s, allowed))
            chained_request.logger.error(
                '%s has not been approved for any of %s levels : "%s"' % (self.name, self.allowed, self.level))

        def __str__(self):
            return 'Error: ' + self.name + ' is "' + self.level + '" approved. requires ' + self.allowed

    class NotInProperStateException(Exception):
        def __init__(self, oname, alevel, allowed):
            self.name = str(oname)
            self.level = str(alevel)
            self.allowed = ' or '.join(map(lambda s: '"%s"' % s, allowed))
            chained_request.logger.error('%s has not reached status %s : "%s"' % (self.name, self.allowed, self.level))

        def __str__(self):
            return 'Error: ' + self.name + ' is in"' + self.level + '" status. requires ' + self.allowed

    class CampaignStoppedException(NotApprovedException):
        def __init__(self, oname):
            self.name = str(oname)
            chained_request.logger.error('Campaign %s is stopped' % self.name)

        def __str__(self):
            return 'Error: ' + self.name + ' is stopped.'

    _json_base__approvalsteps = ['none', 'flow', 'submit']

    _json_base__status = ['new', 'processing', 'done', 'force_done']

    _json_base__schema = {
        '_id': '',
        'chain': [],
        'approval': str(''),
        'step': 0,
        'analysis_id': [],
        'pwg': '',
        'prepid': '',
        'dataset_name': '',
        'history': [],
        'member_of_campaign': '',
        'last_status': 'new',
        'status': '',
        'chain_type': 'TaskChain',
        'validate': 0,  # indicates whether the chain should be submitted to validation
        'action_parameters': {
            'block_number': 0,
            'staged': 0,
            'threshold': 0,
            'flag': True
        }
    }

    def __init__(self, json_input=None):

        json_input = json_input if json_input else {}

        # create all chained request in flow
        self._json_base__schema['approval'] = self.get_approval_steps()[1]
        self._json_base__schema['status'] = self.get_status_steps()[0]

        # update self according to json_input
        self.setup()
        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()

    def get_actors(self, N=-1, what='author_username', Nchild=-1):
        rdb = database('requests')
        last_r = request(rdb.get(self.get_attribute('chain')[-1]))
        return last_r.get_actors(N, what, Nchild)

    def get_list_of_superflows(self):
        """
        get a list of 2 or more consequitive campaigns
        where flow approval==tasksubmit
        """

        cDB = database("chained_campaigns")
        flowDB = database("flows")

        __curr_step = self.get_attribute("step")
        __cc = cDB.get(self.get_attribute("member_of_campaign"))
        __list_of_campaigns = []
        FLOW_APPRVAL_FOR_TASKCHAIN = "tasksubmit"
        # we work only starting from current step
        # +1 so we dont want to take current campaign
        for chain in __cc["campaigns"][__curr_step + 1:]:
            __ongoing_flow = flowDB.get(chain[1])
            if __ongoing_flow:
                # check in case flow doesnt exists
                if __ongoing_flow["approval"] == FLOW_APPRVAL_FOR_TASKCHAIN:
                    # do we need a list? we could save only last campaign's prepid
                    __list_of_campaigns.append(chain[0])
                elif len(__list_of_campaigns) >= 2:
                    # we case previously we had 2 or more consequitive superflows
                    # and 3rd was normal flow we return only the previous superflows
                    return __list_of_campaigns
                else:
                    # in case superflow->flow we return nothing as its a normal flow
                    return []

        return __list_of_campaigns

    def flow_trial(self, input_dataset='', block_black_list=None, block_white_list=None, check_stats=True, reserve=False, super_flow=False):
        if not block_black_list:
            block_black_list = []
        if not block_white_list:
            block_white_list = []

        reqDB = database("requests")

        __curr_step = self.get_attribute("step")
        __list_of_campaigns = []

        chainid = self.get_attribute('prepid')

        __list_of_campaigns = self.get_list_of_superflows()
        super_flow = len(__list_of_campaigns) >= 2

        try:
            if not super_flow:
                self.logger.info("we are defaulting to normal flow for: %s" % (self.get_attribute('prepid')))

                # we do original flowing
                # and toggle last request
                if self.flow(check_stats=check_stats):
                    db = database('chained_requests')
                    db.update(self.json())
                    # toggle the last request forward
                    __ret = self.toggle_last_request()
                    self.remove_from_nonflowing_list()
                    return {"prepid": chainid, "results": True}
            else:
                # we have FLOW_APPRVAL_FOR_TASKCHAIN and need to:
                # 1) reserve requests to FLOW_APPRVAL_FOR_TASKCHAIN's end
                # 2) flow chained_req to next_step
                # 3) approve just reserved requests
                # 4) approve 1st request to trigger submission as TaskChain
                self.logger.info("SUPERFLOW which flows we want to do: %s" % (__list_of_campaigns))

                __submit_step = 1

                ret_flow = self.flow_to_next_step(input_dataset, block_black_list, block_white_list, check_stats=check_stats)['result']

                if ret_flow:
                    # force updating the chain_request document in DB and here
                    self.reload()
                else:
                    return {"results": False, "message": "Failed to flow"}
                generated_requests = []
                for el in __list_of_campaigns:
                    reservation_res = self.reserve(limit=el)
                    if not reservation_res["results"]:
                        return {
                            "results": False,
                            "prepid": chainid,
                            "message": "error while reserving request"
                        }
                    elif 'generated_requests' in reservation_res:
                        generated_requests = generated_requests + reservation_res['generated_requests']
                        reservation_res.pop('generated_requests')
                    # we should check the last_status here
                    # in case request is beying reused and not done - we stop.
                    if self.get_attribute('last_status') != "new" and self.get_attribute('last_status') != "done":
                        # TO-DO make page reload info on failure or show message even if its OK
                        self.save_requests(generated_requests)
                        return {"results": True,
                                "prepid": chainid,
                                "message": "we cannot move further with last_status not done"}
                self.save_requests(generated_requests)
                if reservation_res["results"]:
                    # for now +1 because current_step was saved before actual flowing
                    for elem in self.get_attribute("chain")[__curr_step + 1:]:
                        if not reqDB.document_exists(elem):
                            return {"results": False, "message": "Reuest not found in DB"}
                        next_req = request(reqDB.get(elem))
                        if next_req.get_attribute('approval') == 'submit':
                            # in case we assign already existing request which completed in other chain
                            # We have to flow chain to get its step to overpass the done request
                            __ret = self.flow(check_stats=check_stats)
                            if __ret:
                                self.reload()
                                # we don't want to submit the 1st request which is already done.
                                __submit_step += 1
                            # else should we explicitly crash flow or will it fail on 1st approval?
                            continue

                        with locker.lock('{0}-wait-for-approval'.format(elem)):
                            next_req.approve()
                            saved = reqDB.save(next_req.json())
                        if not saved:
                            self.logger.info("Could not save request %s to DB after approval" % (elem))
                            return {"results": False,
                                    "message": "Could not save request after approval"}

                    to_submit_req = self.get_attribute("chain")[__curr_step + __submit_step]

                    # if we reached up to here there is no point to check if request exists
                    __sub_req = request(reqDB.get(to_submit_req))
                    with locker.lock('{0}-wait-for-approval'.format(to_submit_req)):
                        __sub_req.approve()
                        saved2 = reqDB.save(__sub_req.json())
                        self.logger.debug("SUPERFLOW to_submit_req current status: %s aprroval: %s saved2: %s" % (
                            __sub_req.get_attribute("status"),
                            __sub_req.get_attribute("approval"), saved2)
                        )

                    return {
                        "results": True,
                        "message": "SUPERFLOW finished successfully",
                        "prepid": chainid}

                else:
                    return {
                        "results": False,
                        "message": "Reservation failed",
                        "prepid": chainid}

                return {
                    "prepid": chainid,
                    "results": False,
                    "message": "We are failing superflow for now...."}

        except Exception as ex:
            self.logger.info("Error in chained_request flow: %s" % (str(ex)))
            return {"prepid": chainid, "results": False, "message": str(ex)}

    def request_join(self, req):
        with locker.lock(req.get_attribute('prepid')):
            chain = req.get_attribute("member_of_chain")
            if self.get_attribute('_id') not in chain:
                chain.append(self.get_attribute('_id'))
                self.logger.debug("Adding chain_req member_of_chain: %s to request: %s" % (self.get_attribute("prepid"), req.get_attribute('prepid')))
            else:
                return False

            req.set_attribute("member_of_chain", chain)

        req.update_history({'action': 'join chain', 'step': self.get_attribute('_id')})
        if not req.get_attribute('prepid') in self.get_attribute('chain'):
            chain = self.get_attribute('chain')
            chain.append(req.get_attribute('prepid'))
            self.set_attribute("chain", chain)
            self.update_history({'action': 'add request', 'step': req.get_attribute('prepid')})

    def reserve(self, limit=None, save_requests=True):
        steps = 0
        count_limit = None
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

    def flow(self, input_dataset='', block_black_list=None, block_white_list=None, check_stats=True):
        if not block_black_list:
            block_black_list = []
        if not block_white_list:
            block_white_list = []
        return self.flow_to_next_step(input_dataset, block_black_list, block_white_list, check_stats)['result']


    def test_output_ds(self):
        req_db = database("requests")
        ret = ""
        res = ""
        output_ds = None
        for req_id in self.get_attribute("chain"):
            req = request(req_db.get(req_id))
            if output_ds is not None:
                self.logger.info("Working for request: %s, sequence: %s" % (req.get_attribute("prepid"), req.get_attribute("sequences")))
                ret = self.get_ds_input(output_ds, req.get_attribute("sequences"))
                res += "%s input DS: %s\n" % (req_id, ret)
            else:
                res += "%s input DS: %s\n" % (req_id, ret)
            # for test purposes to migrate DS selection
            if req.get_attribute("input_dataset") != ret:
                res += "input DS differs!\nis:%s\nto-be:%s\n" % (req.get_attribute("input_dataset"), ret)
                self.logger.info("chain %s request:%s" % (self.get_attribute("prepid"), req_id))
                self.logger.info("input DS differs!\n is:%s\nto-be:%s\n" % (req.get_attribute("input_dataset"), ret))
            output_ds = req.get_attribute("output_dataset")
        return res

    def flow_to_next_step(self, input_dataset='', block_black_list=None, block_white_list=None, check_stats=True, reserve=False, stop_at_campaign=None):
        if not block_white_list:
            block_white_list = []
        if not block_black_list:
            block_black_list = []
        self.logger.info('Flowing chained_request %s to next step...' % (self.get_attribute('_id')))
        if not self.get_attribute('chain'):
            self.add_to_nonflowing_list('Chained request has no root')
            raise self.ChainedRequestCannotFlowException(
                self.get_attribute('_id'),
                'chained_request %s has got no root' % (self.get_attribute('_id')))

        # check on the approval of the chained request before all
        # let it be flowing regardless
        # if self.get_attribute('approval') == 'none':
        #    raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
        #    'The approval of the chained request is none, and therefore flow cannot happen')

        # this operation requires to access all sorts of objects
        rdb = database('requests')
        cdb = database('campaigns')
        ccdb = database('chained_campaigns')
        crdb = database('chained_requests')
        fdb = database('flows')
        sdb = database('settings')
        ldb = database('lists')

        l_type = locator()

        current_step = len(self.get_attribute('chain')) - 1 if reserve else self.get_attribute('step')
        current_id = self.get_attribute('chain')[current_step]
        next_step = current_step + 1

        if not rdb.document_exists(current_id):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'the request %s does not exist' % current_id)

        current_request = request(rdb.get(current_id))
        current_campaign = campaign(cdb.get(current_request.get_attribute('member_of_campaign')))

        if not ccdb.document_exists(self.get_attribute('member_of_campaign')):
            self.add_to_nonflowing_list('Chained request is a member of campaign %s that does not exist' % (self.get_attribute('member_of_campaign')))
            raise self.ChainedRequestCannotFlowException(
                self.get_attribute('_id'),
                'the chain request %s is member of %s that does not exist' % (
                    self.get_attribute('_id'),
                    self.get_attribute('member_of_campaign')
                )
            )
        if reserve and stop_at_campaign and stop_at_campaign == current_campaign.get_attribute('prepid'):
            return {'result': False}

        mcm_cc = ccdb.get(self.get_attribute('member_of_campaign'))
        if next_step >= len(mcm_cc['campaigns']):
            if reserve:
                return {'result': False}
            raise self.ChainedRequestCannotFlowException(
                self.get_attribute('_id'),
                'chained_campaign %s does not allow any further flowing.' % (self.get_attribute('member_of_campaign')))

        if not reserve:
            # is the current request in the proper approval
            allowed_request_approvals = ['submit']
            if current_request.get_attribute('approval') not in allowed_request_approvals:
                raise self.NotApprovedException(
                    current_request.get_attribute('prepid'),
                    current_request.get_attribute('approval'),
                    allowed_request_approvals)
            # is the current request in the proper status
            allowed_request_statuses = ['submitted', 'done']
            if current_request.get_attribute('status') not in allowed_request_statuses:
                raise self.NotInProperStateException(
                    current_request.get_attribute('prepid'),
                    current_request.get_attribute('status'),
                    allowed_request_statuses)

        root_request_id = self.get_attribute('chain')[0]

        action_parameters = self.get_attribute('action_parameters')

        # what is the campaign to go to next and with which flow
        (next_campaign_id, flow_name) = mcm_cc['campaigns'][next_step]
        if not fdb.document_exists(flow_name):
            self.add_to_nonflowing_list('The flow %s does not exist' % (flow_name))
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'The flow %s does not exist' % flow_name)
        mcm_f = flow(fdb.get(flow_name))
        if 'sequences' not in mcm_f.get_attribute('request_parameters'):
            self.add_to_nonflowing_list('The flow %s does not contain sequences information' % (flow_name))
            raise self.ChainedRequestCannotFlowException(
                self.get_attribute('_id'),
                'The flow %s does not contain sequences information.' % (flow_name))
        other_bad_characters = [' ', '-']
        if "process_string" in mcm_f.get_attribute('request_parameters') and mcm_f.get_attribute("request_parameters")["process_string"] and any(map(lambda char: char in mcm_f.get_attribute("request_parameters")["process_string"], other_bad_characters)):
            self.add_to_nonflowing_list('The flow process string (%s) contains a bad character %s' % (mcm_f.get_attribute("request_parameters")["process_string"], ','.join(other_bad_characters)))
            raise self.ChainedRequestCannotFlowException(
                self.get_attribute('_id'),
                'The flow process string (%s) contains a bad character %s' % (
                    mcm_f.get_attribute("request_parameters")["process_string"],
                    ','.join(other_bad_characters)))

        if not cdb.document_exists(next_campaign_id):
            self.add_to_nonflowing_list('The next campaign %s does not exist' % (next_campaign_id))
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'The next campaign %s does not exist' % next_campaign_id)

        next_campaign = campaign(cdb.get(next_campaign_id))
        if len(next_campaign.get_attribute('sequences')) != len(mcm_f.get_attribute('request_parameters')['sequences']):
            self.add_to_nonflowing_list('Sequences changes in flow %s are not consistent with the next campaign %s' % (flow_name, next_campaign_id))
            raise self.ChainedRequestCannotFlowException(
                self.get_attribute('_id'),
                'the sequences changes in flow %s are not consistent with the next campaign %s' % (flow_name, next_campaign_id))

        if next_campaign.get_attribute('energy') != current_campaign.get_attribute('energy'):
            self.add_to_nonflowing_list('Request %s has inconsistent energy.' % (next_campaign.get_attribute('prepid')))
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'cannot flow any further. Request {0} has inconsistent energy.'.format(next_campaign.get_attribute("prepid")))

        if not mcm_cc.get('do_not_check_cmssw_versions', False) and not next_campaign.is_release_greater_or_equal_to(current_campaign.get_attribute('cmssw_release')):
            self.add_to_nonflowing_list('Request %s has lower release version.' % (next_campaign.get_attribute('prepid')))
            raise self.ChainedRequestCannotFlowException(self.get_attribute("_id"), 'cannot flow any further. Request {0} has lower release version.'.format(next_campaign.get_attribute("prepid")))

        if next_campaign.get_attribute('type') == 'MCReproc' and ('time_event' not in mcm_f.get_attribute('request_parameters')):
            self.add_to_nonflowing_list('Flow is getting into a MCReproc campaign but not time per event is specified')
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'the flow is getting into a MCReproc campaign but not time per event is specified')

        if next_campaign.get_attribute('type') == 'MCReproc' and ('size_event' not in mcm_f.get_attribute('request_parameters')):
            self.add_to_nonflowing_list('Flow is getting into a MCReproc campaign but not size per event is specified')
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'the flow is getting into a MCReproc campaign but not size per event is specified')

        # check that it is allowed to flow
        allowed_flow_approvals = ['flow', 'submit', "tasksubmit"]
        # cascade of checks

        if not mcm_f.get_attribute('approval') in allowed_flow_approvals:
            if reserve or not self.get_attribute('approval') in allowed_flow_approvals:
                raise self.ChainedRequestCannotFlowException(
                    self.get_attribute('_id'),
                    'Neither the flow (%s) nor the chained request (%s) approvals allow for flowing' % (
                        mcm_f.get_attribute('approval'),
                        self.get_attribute('approval')))

        if next_campaign.get_attribute('status') == 'stopped':
            raise self.CampaignStoppedException(next_campaign_id)

        # what is going to be the required number of events for the next request
        # update the stats to its best
        # used for normal flowing
        if not reserve:
            current_request.get_stats()
            next_total_events = current_request.get_attribute('completed_events')
            # get the original expected events and allow a margin of 5% less statistics
            statistics_fraction = settings.get_value('statistics_fraction')
            current_eff_error = 1. - current_request.get_efficiency_error()
            statistics_fraction = min(statistics_fraction, current_eff_error)
            completed_events_to_pass = int(current_request.get_attribute('total_events') * statistics_fraction)
            total_events_for_percentage = current_request.get_attribute('total_events')

            notify_on_fail = True  # to be tuned according to the specific cases
            if current_request.get_attribute('completed_events') <= 0 and current_request.get_attribute("keep_output").count(True) > 0:
                self.logger.debug("compl_evts: %s, prepid: %s" % (
                    current_request.get_attribute('completed_events'),
                    current_request.get_attribute('prepid')))

                self.add_to_nonflowing_list('The number of events completed is negative or null for %s' % (current_request.get_attribute('prepid')))
                raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'The number of events completed is negative or null for %s' % (current_request.get_attribute('prepid')))
            else:
                allowed_request_statuses = ['done']
                # determine if this is a root -> non-root transition to potentially apply staged number
                at_a_transition = (current_campaign.get_attribute('root') != 1 and next_campaign.get_attribute('root') == 1)
                if (action_parameters['staged'] != 0 or action_parameters['threshold'] != 0) and at_a_transition:
                    allowed_request_statuses.append('submitted')
                # check status
                if not current_request.get_attribute('status') in allowed_request_statuses:
                    raise self.NotInProperStateException(
                        current_request.get_attribute('prepid'),
                        current_request.get_attribute('status'),
                        allowed_request_statuses)
                # special check at transition that the statistics is good enough
                if at_a_transition:
                    self.logger.info("ChainedRequest is at transition. id: %s" % (self.get_attribute('prepid')))
                    # at a root -> non-root transition only does the staged/threshold functions !
                    if action_parameters['staged'] != 0:
                        next_total_events = int(action_parameters['staged'])
                        completed_events_to_pass = next_total_events
                    if action_parameters['threshold'] != 0:
                        next_total_events = int(current_request.get_attribute('total_events') * float(action_parameters['threshold'] / 100.))
                        completed_events_to_pass = next_total_events

            if check_stats and (current_request.get_attribute('completed_events') < completed_events_to_pass):
                if current_request.get_attribute("keep_output").count(True) > 0:
                    __percentage = 100 * float(current_request.get_attribute('completed_events')) / float(total_events_for_percentage)
                    if notify_on_fail:
                        message = 'For the request %s, the completed statistics %s (%.2f%%) is not enough to fullfill the requirement to the next level: need at least %s in chain %s \n\nPlease report to the operation HN or at the next MccM what action should be taken.\n\n%srequests?prepid=%s\n%schained_requests?contains=%s\n%schained_requests?prepid=%s ' % (
                            current_request.get_attribute('prepid'),
                            current_request.get_attribute('completed_events'),
                            __percentage,
                            completed_events_to_pass,
                            self.get_attribute('prepid'),
                            l_type.baseurl(),
                            current_request.get_attribute('prepid'),
                            l_type.baseurl(),
                            current_request.get_attribute('prepid'),
                            l_type.baseurl(),
                            self.get_attribute('prepid'))

                        subject = 'Flowing %s with not enough statistics' % (current_request.get_attribute('prepid'))

                        notification(
                            subject,
                            message,
                            [],
                            group=notification.CHAINED_REQUESTS,
                            action_objects=[self.get_attribute('prepid')],
                            object_type='chained_requests',
                            base_object=self)

                        current_request.notify(subject,
                                               message,
                                               accumulate=True)

                    self.add_to_nonflowing_list('The number of events completed %s (%.2f%%) is not enough for the requirement (%s)' % (current_request.get_attribute('completed_events'),
                                                                                                                                       __percentage,
                                                                                                                                       completed_events_to_pass))
                    raise self.ChainedRequestCannotFlowException(
                        self.get_attribute('_id'),
                        'The number of events completed %s (%.2f%%) is not enough for the requirement (%s)' % (current_request.get_attribute('completed_events'), __percentage, completed_events_to_pass))
                else:
                    self.logger.debug("we are flowing chain_req even if current request didn't kept output")

        # select what is to happened : [create, patch, use]
        next_id = None
        approach = None
        next_request = None
        if next_step != len(self.get_attribute('chain')):
            # not at the end
            next_id = self.get_attribute('chain')[next_step]
            if not rdb.document_exists(next_id):
                self.add_to_nonflowing_list('The next request (%s) according to the step (%s) does not exist' % (next_id,
                                                                                                                 next_step))
                raise self.ChainedRequestCannotFlowException(
                    self.get_attribute('_id'),
                    'The next request (%s) according to the step (%s) does not exist' % (next_id, next_step))
            next_request = request(rdb.get(next_id))
            if next_request.get_attribute('status') == 'new':
                # most likely a rewind + resub
                approach = 'patch'
            else:
                # this is always the case in chains reserved from existing things: so use the next request
                approach = 'use'
                # raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                # 'This should never happen. (%s) is next according to step (%s), but is not in new status (%s)' % (
                # next_id, next_step, next_request.get_attribute('status')))
        else:
            # look in *other* chained campaigns whether you can suck in an existing request
            # look up all chained requests that start from the same root request
            # remove <pwg>-chain_ and the -serial number, replacing _ with a .
            toMatch = '.'.join(self.get_attribute('prepid').split('_')[1:][0:next_step + 1]).split('-')[0]
            # make sure they get ordered by prepid
            __query = crdb.construct_lucene_query({'root_request': root_request_id})
            # do we really need to sort them?
            related_crs = sorted(crdb.full_text_search('search', __query, page=-1), key=lambda cr: cr['prepid'])

            vetoed_last = []
            for existing_cr in related_crs:
                # exclude itself
                if existing_cr['prepid'] == self.get_attribute('prepid'):
                    continue
                # prevent from using a request from within the same exact chained_campaigns
                if existing_cr['member_of_campaign'] == self.get_attribute('member_of_campaign'):
                    mcm_cr = chained_request(crdb.get(existing_cr['prepid']))
                    if len(mcm_cr.get_attribute('chain')) > next_step:
                        # one existing request in the very same chained campaign has already something used, make sure it is not going to be used
                        vetoed_last.append(mcm_cr.get_attribute('chain')[next_step])
                    continue
                else:
                    continue
            for existing_cr in related_crs:
                # exclude itself
                if existing_cr['prepid'] == self.get_attribute('prepid'):
                    continue
                # prevent from using a request from within the same exact chained_campaigns
                if existing_cr['member_of_campaign'] == self.get_attribute('member_of_campaign'):
                    continue
                truncated = '.'.join(existing_cr['prepid'].split('_')[1:][0:next_step + 1]).split('-')[0]
                self.logger.info('to match : %s , this one %s' % (toMatch, truncated))
                if truncated == toMatch:
                    # we found a chained request that starts with all same steps
                    mcm_cr = chained_request(crdb.get(existing_cr['prepid']))
                    if len(mcm_cr.get_attribute('chain')) <= next_step:
                        # found one, but it has not enough content either
                        continue
                    if mcm_cr.get_attribute('chain')[next_step] in vetoed_last:
                        continue
                    next_id = mcm_cr.get_attribute('chain')[next_step]
                    break
            if next_id:
                approach = 'use'
            else:
                approach = 'create'

        if approach == 'create':
            from rest_api.RequestPrepId import RequestPrepId

            next_id = RequestPrepId().next_prepid(current_request.get_attribute('pwg'), next_campaign_id)
            self.logger.debug("creating new request in reservation: %s" % (next_id))
            next_request = request(rdb.get(next_id))
            request.transfer(current_request, next_request)
            # set total_events accordingly to current request.
            next_total_evts = current_request.get_attribute("completed_events") if current_request.get_attribute("completed_events") > 0 else current_request.get_attribute("total_events")

            # if case we have action parameters they overwrite the total_events
            if action_parameters['staged'] != 0:
                next_total_evts = int(action_parameters['staged'])
            if action_parameters['threshold'] != 0:
                next_total_evts = int(current_request.get_attribute('total_events') * float(action_parameters['threshold'] / 100.))
            next_request.set_attribute("total_events", next_total_evts)
            next_request.set_attribute("interested_pwg", [current_request.get_attribute('pwg')])
            self.request_join(next_request)

        elif approach == 'use':
            self.logger.debug("using existing request in reservation: %s" % (next_id))
            # there exists a request in another chained campaign that can be re-used here.
            # take this one. advance and go on
            next_request = request(rdb.get(next_id))
            if not reserve:
                self.set_attribute('step', next_step)
                self.set_attribute('last_status', next_request.get_attribute('status'))
                self.update_history({'action': 'flow', 'step': str(next_id)})
                self.set_attribute('status', 'processing')

            if not self.get_attribute("prepid") in next_request.get_attribute("member_of_chain"):
                # register the chain to the next request
                self.request_join(next_request)
                saved = rdb.update(next_request.json())
                if not saved:
                    raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'Unable to save %s with updated member_of_chains' % next_id)
                forceflow_list = ldb.get("list_of_forceflow")
                if self.get_attribute("prepid") in forceflow_list["value"]:
                    forceflow_list["value"].remove(self.get_attribute("prepid"))
                    ldb.update(forceflow_list)
            return {'result': True}
        elif approach == 'patch':
            self.logger.debug("patching request in reservation: %s" % (next_id))
            # there exists already a request in the chain (step!=last) and it is usable for the next stage
            next_request = request(next_campaign.add_request(rdb.get(next_id)))
            # propagate again some of the fields of the previous request.
            request.transfer(current_request, next_request)
            # set total_events accordingly to current request.
            next_total_evts = current_request.get_attribute("completed_events") if current_request.get_attribute("completed_events") > 0 else current_request.get_attribute("total_events")

            # if case we have action parameters they overwrite the total_events
            if action_parameters['staged'] != 0:
                next_total_evts = int(action_parameters['staged'])
            if action_parameters['threshold'] != 0:
                next_total_evts = int(current_request.get_attribute('total_events') * float(action_parameters['threshold'] / 100.))
            next_request.set_attribute("total_events", next_total_evts)
            self.request_join(next_request)
        else:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'Unrecognized approach %s' % approach)

        # set blocks restriction if any
        if block_black_list:
            next_request.set_attribute('block_black_list', block_black_list)
        if block_white_list:
            next_request.set_attribute('block_white_list', block_white_list)

        # register the flow to the request
        next_request.set_attribute('flown_with', flow_name)

        # assemble the campaign+flow => request
        request.put_together(next_campaign, mcm_f, next_request)

        # determine whether we have an input dataset for the next request
        if len(current_request.get_attribute('output_dataset')):
            # here we should determine the input dataset from DB dict based on
            # current_request's 1st step in sequence
            input_dataset = self.get_ds_input(
                current_request.get_attribute('output_dataset'),
                next_request.get_attribute("sequences"))
        elif len(current_request.get_attribute('reqmgr_name')) and current_request.get_attribute("keep_output").count(True) > 0:
            self.logger.debug("input_ds based by request_manager....")
            last_wma = current_request.get_attribute('reqmgr_name')[-1]
            if 'content' in last_wma and 'pdmv_dataset_name' in last_wma['content']:
                self.logger.debug("\tget from rqmngr")
                input_dataset = self.get_ds_input(
                    last_wma['content']['pdmv_dataset_list'],
                    next_request.get_attribute("sequences"))
            else:
                self.logger.debug("\tget from stats")
                statsDB = database('stats', url='http://vocms074.cern.ch:5984/')
                if statsDB.document_exists(last_wma['name']):
                    latestStatus = statsDB.get(last_wma['name'])
                    input_dataset = self.get_ds_input(
                        latestStatus['pdmv_dataset_list'],
                        next_request.get_attribute("sequences"))

        if input_dataset:
            self.logger.info("%s setting input_ds to: %s" % (next_request.get_attribute("prepid"), input_dataset))
            next_request.set_attribute('input_dataset', input_dataset)

        if not reserve:
            # already taking stage and threshold into account
            next_request.set_attribute('total_events', next_total_events)
            next_request.update_history({'action': 'flow', 'step': self.get_attribute('prepid')})

        if mcm_f.get_attribute('approval') == "tasksubmit" and next_request.get_attribute("total_events") == -1:
            # in case we reserve multiple steps and they are injected as TaskChain
            next_request.set_attribute("total_events", current_request.get_attribute("total_events"))
        request_saved = rdb.save(next_request.json())
        if not request_saved:
            raise self.ChainedRequestCannotFlowException(
                self.get_attribute('_id'),
                'Could not save the new request %s' % (next_request.get_attribute('prepid')))

        # inspect priority Do we want to override priority of a request when we flow to next step?
        self.set_priority(action_parameters['block_number'])
        if not reserve:
            # sync last status
            self.set_attribute('last_status', next_request.get_attribute('status'))
            # we can only be processing at this point
            self.set_attribute('status', 'processing')
            # set to next step
            self.set_attribute('step', next_step)

            if not check_stats:
                action = "force flow"
            else:
                action = "flow"

            self.update_history({'action': action, 'step': next_request.get_attribute('prepid')})

        # we remove the chain_req id from force_flow list if it's in there
        forceflow_list = ldb.get("list_of_forceflow")
        if self.get_attribute("prepid") in forceflow_list["value"]:
            forceflow_list["value"].remove(self.get_attribute("prepid"))
            ldb.update(forceflow_list)

        # It's flown, remove it from list_of_nonflowing_chains
        self.remove_from_nonflowing_list()

        return {
            'result': True,
            'generated_request': next_request.get_attribute('prepid')
        }

    def toggle_last_request(self):

        # let it toggle the last request to a given approval only if the chained request allows it
        if self.get_attribute('approval') == 'none':
            return

        ccdb = database('chained_campaigns')
        mcm_cc = ccdb.get(self.get_attribute('member_of_campaign'))
        (next_campaign_id, flow_name) = mcm_cc['campaigns'][self.get_attribute('step')]
        fdb = database('flows')
        mcm_f = flow(fdb.get(flow_name))
        # check whether we have to do something even more subtle with the request
        if mcm_f.get_attribute('approval') in ['submit', 'tasksubmit'] or self.get_attribute('approval') == 'submit':
            rdb = database('requests')
            next_request = request(rdb.get(self.get_attribute('chain')[self.get_attribute('step')]))

            current_r_approval = next_request.get_attribute('approval')
            time_out = 0

            while current_r_approval != 'submit' and time_out <= 10:
                time_out += 1
                # get it back from db to avoid _red issues
                next_request = request(rdb.get(next_request.get_attribute('prepid')))
                with locker.lock('{0}-wait-for-approval'.format(next_request.get_attribute('prepid'))):
                    next_request.approve()
                    request_saved = rdb.save(next_request.json())
                    if not request_saved:
                        raise self.ChainedRequestCannotFlowException(
                            self.get_attribute('_id'),
                            'Could not save the new request %s while trying to move to submit approval' % (next_request.get_attribute('prepid')))
                current_r_approval = next_request.get_attribute('approval')
                pass

        return True

    def set_last_status(self, status=None):
        if not status:
            rdb = database('requests')
            step_r = rdb.get(self.get_attribute('chain')[self.get_attribute('step')])
            new_last_status = step_r['status']
        else:
            new_last_status = status
        if new_last_status != self.get_attribute('last_status'):
            self.update_history({'action': 'set last status', 'step': new_last_status})
            self.set_attribute('last_status', new_last_status)
            return True
        else:
            return False

    def set_processing_status(self, pid=None, status=None):
        if not pid or not status:
            rdb = database('requests')
            step_r = rdb.get(self.get_attribute('chain')[self.get_attribute('step')])
            pid = step_r['prepid']
            status = step_r['status']

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

    def set_priority(self, level):
        rdb = database('requests')
        okay = True
        for r in self.get_attribute('chain'):
            req = request(rdb.get(r))
            # only those that can still be changed
            # set to the maximum priority
            if not req.change_priority(priority().priority(level)):
                self.logger.info('Could not save updated priority for %s' % r)
                okay = False
        return okay

    def timer(method):
        def timed(*args, **kw):
            t0 = time.time()
            result = method(*args, **kw)
            t1 = time.time()
            # if t1-t0 > 100:
            json_base.logger.info("%s ####method took: %s" % (method.__name__, t1 - t0))
            return result
        return timed

    @timer
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

    def get_timeout_memory_threads(self):
        req_ids = self.get_attribute('chain')[self.get_attribute('step'):]
        rdb = database('requests')
        t = 0
        requests_to_validate = 0
        max_memory = 0
        max_threads = 1
        for (index, req_id) in enumerate(req_ids):
            mcm_r = request(rdb.get(req_id))
            if not mcm_r.is_root and 'validation' not in mcm_r._json_base__status:  # do it only for root or possible root request
                break
            requests_to_validate += 1
            onet = mcm_r.get_timeout()
            if onet > t:
                t = onet
            current_memory = mcm_r.get_attribute("memory")
            if current_memory > max_memory:
                max_memory = current_memory
            threads = mcm_r.get_core_num()
            if threads > max_threads:
                max_threads = threads
        # get the max and apply to all as a conservative estimation
        # this should probably be a bit more subtle
        return t * requests_to_validate, max_memory, max_threads

    def get_setup(self, directory='', events=None, run=False, validation=False, scratch=False, for_validation=False):
        if scratch:
            req_ids = self.get_attribute('chain')
        else:
            req_ids = self.get_attribute('chain')[self.get_attribute('step'):]
        rdb = database('requests')
        rdb = database('requests')
        setup_file = ''
        for (index, req_id) in enumerate(req_ids):
            req = request(rdb.get(req_id))
            if not req.is_root and 'validation' not in req._json_base__status:  # do it only for root or possible root request
                break
            setup_file += req.get_setup_file(directory=directory, events=events, run=run, do_valid=validation, for_validation=for_validation)
            if run and validation:
                req.reload()
        return setup_file

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
                notification(
                    subject,
                    message,
                    [],
                    group=notification.CHAINED_REQUESTS,
                    action_objects=[self.get_attribute('prepid')],
                    object_type='chained_requests',
                    base_object=self)
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
            notification(
                subject,
                message,
                [],
                group=notification.CHAINED_REQUESTS,
                action_objects=[self.get_attribute('prepid')],
                object_type='chained_requests',
                base_object=self)
            self.notify(subject, message)

    def add_to_nonflowing_list(self, reason):
        chain_prepid = self.get_attribute('prepid')
        with locker.lock('%s-nonflowing-list' % (chain_prepid)):
            ldb = database('lists')
            list_of_nonflowing_chains = ldb.get('list_of_nonflowing_chains')
            for stalled_entry in list_of_nonflowing_chains['value']:
                if stalled_entry['chain'] == chain_prepid:
                    break
            else:
                # Else will be executed only if no break happened before
                # Check if it's not the last request in the chain
                requests_in_chain = self.get_attribute('chain')
                current_step_prepid = requests_in_chain[self.get_attribute('step')]
                rdb = database('requests')
                set_status_date = int(time.time())
                current_request = rdb.get(current_step_prepid)
                for history_entry in reversed(current_request.get('history', [])):
                    if history_entry.get('action') == 'set status':
                        set_status_date = history_entry['updater']['submission_date']
                        set_status_date = int(time.mktime(time.strptime(set_status_date, '%Y-%m-%d-%H-%M')))
                        break

                list_of_nonflowing_chains['value'].append({'reason': reason,
                                                           'chain': chain_prepid,
                                                           'nonflowing_since': set_status_date})
                ldb.update(list_of_nonflowing_chains)

    def remove_from_nonflowing_list(self):
        # Remove from nonflowing list
        chain_prepid = self.get_attribute('prepid')
        with locker.lock('%s-nonflowing-list' % (chain_prepid)):
            ldb = database('lists')
            list_of_nonflowing_chains = ldb.get('list_of_nonflowing_chains')
            new_list_of_nonflowing_chains = [x for x in list_of_nonflowing_chains['value'] if x['chain'] != chain_prepid]
            if len(new_list_of_nonflowing_chains) != len(list_of_nonflowing_chains['value']):
                list_of_nonflowing_chains['value'] = new_list_of_nonflowing_chains
                ldb.update(list_of_nonflowing_chains)
