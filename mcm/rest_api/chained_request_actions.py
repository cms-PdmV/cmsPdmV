import flask
from json import dumps, loads
from model.user import Role
from rest_api.api_base import DeleteRESTResource, GetEditableRESTResource, GetRESTResource, RESTResource, UpdateRESTResource
from model.chained_request import ChainedRequest
from model.request import Request
from tools.exceptions import CouldNotSaveException, InvalidActionException
from tools.priority import block_to_priority


class UpdateChainedRequest(UpdateRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Update a chained request campaign with the provided content
        Required attributes - prepid and revision
        """
        return self.update_object(data, ChainedRequest)


class DeleteChainedRequest(DeleteRESTResource):

    def delete_check(self, obj):
        prepid = obj.get('prepid')
        if obj.get('enabled'):
            raise Exception('Chained request is not disabled')

        requests = []
        chain = obj.get('chain')
        for i, request_prepid in reversed(list(enumerate(chain))):
            request = Request.fetch(request_prepid)
            request_chains = request.get('member_of_chain')
            if prepid not in request_chains:
                raise Exception(f'Request {request_prepid} is not member of chained request')

            request_chains.remove(prepid)
            request.set('member_of_chain', request_chains)
            if not request_chains:
                # Last chain that had that request
                if i == 0:
                    approval = request.get('approval')
                    if approval == 'submit':
                        # Root request that is submitted or done, must be reset first
                        raise InvalidActionException(f'Request {request_prepid}, will not be chained anymore')
                else:
                    # Not root request can't exist without a chain
                    raise InvalidActionException(f'Request {request_prepid} will not be chained anymore')

            request.update_history('leave', prepid)
            requests.append(request)

        # Save all requests
        for request in requests:
            if not request.save():
                request_prepid = request.get('prepid')
                raise CouldNotSaveException(request_prepid)

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def delete(self, prepid):
        """
        Delete a chained request
        """
        return self.delete_object(prepid, ChainedRequest)


class GetChainedRequest(GetRESTResource):
    """
    Endpoing for retrieving a chained request
    """
    object_class = ChainedRequest


class GetEditableChainedRequest(GetEditableRESTResource):
    """
    Endpoing for retrieving a chained request and it's editing info
    """
    object_class = ChainedRequest


class UniqueChainsRESTResource(RESTResource):

    def get_unique_chained_requests(self, prepid):
        """
        If there are multiple chained requests that have the same request as
        current step, then only one needs to be flown or rewinded, others will
        be rewinded automatically
        """
        if isinstance(prepid, list):
            return prepid

        chained_requests = ChainedRequest.get_database().bulk_get(prepid)
        prepids = []
        current_requests = set()
        for chained_request in chained_requests:
            current_request = chained_request['chain'][chained_request['step']]
            if current_request not in current_requests:
                current_requests.add(current_request)
                prepids.append(chained_request['prepid'])

        return prepids


class ToggleChainedRequestEnabled(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Toggle the given chained requests to enabled or disabled
        """
        def toggle(chained_request):
            chained_request.toggle_enabled()

        return self.do_multiple_items(data['prepid'], ChainedRequest, toggle)


class ChainedRequestFlow(UniqueChainsRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Flow chained requests
        """
        def flow(chained_request):
            chained_request.flow()

        prepid = self.get_unique_chained_requests(data['prepid'])
        return self.do_multiple_items(prepid, ChainedRequest, flow)


class ChainedRequestRewind(UniqueChainsRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Rewind chained requests
        """
        def rewind(chained_request):
            chained_request.rewind()

        prepid = self.get_unique_chained_requests(data['prepid'])
        return self.do_multiple_items(prepid, ChainedRequest, rewind)


class ChainedRequestRewindToRoot(ChainedRequestRewind):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Rewind chained requests to root
        """
        def rewind_to_root(chained_request):
            for _ in range(chained_request.get('step')):
                chained_request.rewind()

        prepid = self.get_unique_chained_requests(data['prepid'])
        return self.do_multiple_items(prepid, ChainedRequest, rewind_to_root)


class SoftResetChainedRequest(UniqueChainsRESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Soft reset chained requests
        """
        def soft_reset(chained_request):
            step = chained_request.get('step')
            for request_id in reversed(chained_request[:step + 1]):
                request = Request.fetch(request_id)
                if request.get_approval_status() != 'submit-approved':
                    break

                request.reset(soft=True)
                request.reload(save=True)
                chained_request.set('step', chained_request.get('step') - 1)

        prepid = self.get_unique_chained_requests(data['prepid'])
        return self.do_multiple_items(prepid, ChainedRequest, soft_reset)


class InspectChainedRequest(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Inspect reset chained requests
        """
        def inspect(chained_request):
            chained_request.inspect()

        return self.do_multiple_items(data['prepid'], ChainedRequest, inspect)


class TestChainedRequest(RESTResource):

    @RESTResource.ensure_role(Role.MC_CONTACT)
    def get(self, chained_request_id):
        """
        Perform test for chained requests
        """
        crdb = database('chained_requests')
        rdb = database('requests')
        settingsDB = database('settings')
        mcm_cr = chained_request(crdb.get(chained_request_id))
        if settingsDB.get('validation_stop')['value']:
            return {
                "results": False,
                'message': ('validation jobs are halted to allow forthcoming mcm ''restart - try again later'),
                "prepid": chained_request_id}
        requires_validation = False
        for rid in mcm_cr.get_attribute('chain')[mcm_cr.get_attribute('step'):]:
            mcm_r = request(rdb.get(rid))
            if not mcm_r.is_root and 'validation' not in mcm_r._json_base__status:  # We dont care about non root request because they are not being used on chain run test
                break
            requires_validation = True
            if mcm_r.get_attribute('status') != 'new' or mcm_r.get_attribute('approval') != 'none':
                return {
                    "results": False,
                    "prepid": chained_request_id,
                    "message": "request %s is in status %s, approval: %s" % (rid, mcm_r.get_attribute('status'), mcm_r.get_attribute('approval'))}
            try:
                mcm_r.ok_to_move_to_approval_validation(for_chain=True)
                mcm_r.update_history({'action': 'approve', 'step': 'validation'})
                mcm_r.set_attribute('approval', 'validation')
                mcm_r.reload()
                text = 'Within chain %s \n' % mcm_cr.get_attribute('prepid')
                text += mcm_r.textified()
                subject = 'Approval %s in chain %s for request %s' % ('validation', mcm_cr.get_attribute('prepid'), mcm_r.get_attribute('prepid'))
                mcm_r.notify(subject, text, accumulate=True)
            except Exception as e:
                mcm_cr.reset_requests(str(e), notify_one=rid)
                return {
                    "results": False,
                    "message": str(e),
                    "prepid": chained_request_id}
        if not requires_validation:
            return {
                "results": True,
                "message": "No validation required",
                "prepid": chained_request_id}
        mcm_cr.set_attribute('validate', 1)
        mcm_cr.update_history({'action': 'validate'})
        if not crdb.update(mcm_cr.json()):
            return {
                "results": False,
                "message": "Failed while trying to update the document in DB",
                "prepid": chained_request_id}
        return {
            "results": True,
            "message": "run test will start soon",
            "prepid": chained_request_id}


class TaskChainDict(RESTResource):

    @RESTResource.ensure_role(Role.USER)
    def get(self, chained_request_id):
        """
        Provide the taskchain dictionnary for uploading to request manager
        """
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('scratch', type=str)
        self.parser.add_argument('upto', type=int)
        self.representations = {'text/plain': self.output_text}
        kwargs = self.parser.parse_args()
        crdb = database('chained_requests')
        rdb = database('requests')
        settingsDB = database('settings')

        __DT_prio = settingsDB.get('datatier_input')["value"]

        def tranform_to_step_chain(wma_dict, total_time_evt, total_size_evt):
            # replace Task -> Step in inside dictionaries
            for task_num in range(wma_dict["TaskChain"]):
                for elem in wma_dict["Task%s" % (task_num + 1)]:
                    if "Task" in elem:
                        wma_dict["Task%s" % (task_num + 1)][elem.replace("Task", "Step")] = wma_dict["Task%s" % (task_num + 1)].pop(elem)

                # we later add the global fields
                del(wma_dict["Task%s" % (task_num + 1)]["TimePerEvent"])
                del(wma_dict["Task%s" % (task_num + 1)]["SizePerEvent"])

            # we do same replacement on top level
            for el in wma_dict:
                if wma_dict[el].__class__ == str and "task" in wma_dict[el]:
                    wma_dict[el] = wma_dict[el].replace("task", "step")

                if "Task" in el:
                    wma_dict[el.replace("Task", "Step")] = wma_dict.pop(el)

            wma_dict["RequestType"] = "StepChain"

            # as of 2017-05 StepChain needs these as sum of internal Tasks
            wma_dict["TimePerEvent"] = total_time_evt
            wma_dict["SizePerEvent"] = total_size_evt

            return wma_dict

        if not crdb.document_exists(chained_request_id):
            # it's a request actually, pick up all chains containing it
            mcm_r = rdb.get(chained_request_id)
            mcm_crs = crdb.query_view('contains', chained_request_id, page_num=-1)
            task_name = 'task_' + chained_request_id
        else:
            mcm_crs = [crdb.get(chained_request_id)]
            # here name should be task_chain's[curr_step] request_prepid
            # so it would be task_prepid-of-current-request same as in top
            __req_id = mcm_crs[0]['chain'][mcm_crs[0]['step']]
            task_name = 'task_' + __req_id

        if len(mcm_crs) == 0:
            return {}

        tasktree = {}
        ignore_status = False
        __total_time_evt = 0
        __total_size_evt = 0

        if kwargs['scratch'] is not None:
            ignore_status = True

        veto_point = None
        if kwargs['upto'] is not None:
            veto_point = kwargs['upto']

        __chains_type = []
        for mcm_cr in mcm_crs:
            __chains_type.append(mcm_cr["chain_type"])
            starting_point = mcm_cr['step']
            if ignore_status:
                starting_point = 0
            for (ir, r) in enumerate(mcm_cr['chain']):
                if (ir < starting_point):
                    continue  # ad no task for things before what is already done
                if veto_point and (ir > veto_point):
                    continue
                mcm_r = request(rdb.get(r))
                if mcm_r.get_attribute('status') == 'done' and not ignore_status:
                    continue

                if r not in tasktree:
                    tasktree[r] = {'next': [], 'dict': [], 'rank': ir}

                base = ir == 0 and mcm_r.get_wmagent_type() in ['MonteCarlo', 'LHEStepZero']
                depend = (ir > starting_point)  # all the ones later than the starting point depend on a previous task
                if ir < (len(mcm_cr['chain']) - 1):
                    tasktree[r]['next'].append(mcm_cr['chain'][ir + 1])

                tasktree[r]['dict'] = mcm_r.request_to_tasks(base, depend)
                # if request is added to tasktree, we save global sums for StepChains
                __total_time_evt += sum(mcm_r.get_attribute("time_event"))
                __total_size_evt += sum(mcm_r.get_attribute("size_event"))

        for (r, item) in tasktree.items():
            # here we should generate unique list of steps+output tiers
            # as we iterate over requests in tasktree
            __uniq_tiers = []
            for el in item['dict']:
                # map of tiers and taskID in order of steps
                __uniq_tiers.append((el['TaskName'], el['_output_tiers_']))

            item['unique_tiers_'] = __uniq_tiers
            for n in item['next']:
                # here we should take input from datatier selection;
                # have a map of tiers -> taskNames and select appropriate one
                __input_tier = tasktree[n]['dict'][0]['_first_step_']
                tModule = tName = ""
                if __input_tier in __DT_prio:
                    # in case there is a possible DataTier in global_dict
                    tModule, tName = request.do_datatier_selection(__DT_prio[__input_tier], __uniq_tiers)

                if tModule != "" and tName != "":
                    tasktree[n]['dict'][0].update({"InputFromOutputModule": tModule, "InputTask": tName})
                else:
                    # default & fallback solution
                    tasktree[n]['dict'][0].update({"InputFromOutputModule": item['dict'][-1]['output_'],
                        "InputTask": item['dict'][-1]['TaskName']})

        wma = {
            "RequestType": "TaskChain",
            "Group": "ppd",
            "Requestor": "pdmvserv",
            "TaskChain": 0,
            "ProcessingVersion": 1,
            "RequestPriority": 0,
            "SubRequestType": "MC",
            # we default to 1 in multicore global
            "Multicore": 1}

        task = 1
        pilot_string = None
        for (r, item) in sorted(tasktree.items(), key=lambda d: d[1]['rank']):
            for d in item['dict']:
                if d['priority_'] > wma['RequestPriority']:
                    wma['RequestPriority'] = d['priority_']
                if d['request_type_'] in ['ReDigi']:
                    wma['SubRequestType'] = 'ReDigi'

                if d.get('pilot_'):
                    pilot_string = d['pilot_']

                for k in d.keys():
                    if k.endswith('_'):
                        d.pop(k)
                wma['Task%d' % task] = d
                task += 1

        if pilot_string:
            wma['SubRequestType'] = pilot_string

        wma['TaskChain'] = task - 1
        if wma['TaskChain'] == 0:
            return dumps({})

        for item in ['CMSSWVersion', 'ScramArch', 'TimePerEvent', 'SizePerEvent', 'GlobalTag', 'Memory']:
            wma[item] = wma['Task%d' % wma['TaskChain']][item]

        # since 2016-11, processingString and AcquisitionEra is mandatory in global params
        wma['AcquisitionEra'] = wma['Task1']['AcquisitionEra']
        wma['ProcessingString'] = wma['Task1']['ProcessingString']
        wma['Campaign'] = wma['Task1']['Campaign']
        wma['PrepID'] = task_name
        wma['RequestString'] = wma['PrepID']
        if __chains_type.count("StepChain") == len(__chains_type):
            return dumps(tranform_to_step_chain(wma, __total_time_evt, __total_size_evt), indent=4)
        else:
            return dumps(wma, indent=4)


class GetSetupForChains(RESTResource):

    def __init__(self):
        path = flask.request.path
        if 'get_setup' in path:
            self.opt = 'setup'
        elif 'get_test' in path:
            self.opt = 'test'
        elif 'get_valid' in path:
            self.opt = 'valid'
            access_limit = access_rights.administrator
        else:
            raise Exception('Cannot create this resource with mode %s' % path)

        self.before_request()
        self.count_call()
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('scratch', type=str, default='')
        self.kwargs = self.parser.parse_args()
        self.representations = {'text/plain': self.output_text}

    @RESTResource.ensure_role(Role.ADMINISTRATOR)
    def get(self, chained_request_id):
        """
        Retrieve the script necessary to setup and test a given chained request
        get_setup - returns file for config generation for submission
        get_test - returns file for user validation
        get_valid - returns file for automatic validation
        """
        crdb = database('chained_requests')
        if not crdb.document_exists(chained_request_id):
            return {"results": False,
                    "message": "Chained request with prepid {0} does not exist".format(chained_request_id)}

        chained_req = chained_request(crdb.get(chained_request_id))
        from_scratch = self.kwargs.get('scratch', '').lower() == 'true'
        for_validation = self.opt in ('test', 'valid')
        automatic_validation = self.opt == 'valid'
        return chained_req.get_setup(for_validation=for_validation,
                                     automatic_validation=automatic_validation,
                                     scratch=from_scratch)


class ForceChainReqToDone(RESTResource):

    def __init__(self):
        self.crdb = database('chained_requests')
        self.ldb = database('lists')
        self.before_request()
        self.count_call()
        self.representations = {'text/plain': self.output_text}

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def get(self, chained_request_ids):
        """
        Force chained_request to set status to done
        """
        if ',' in chained_request_ids:
            rlist = chained_request_ids.rsplit(',')
            res = []
            success = True
            for r in rlist:
                result = self.force_status_done(r)
                success = success and result.get('results', False)
                res.append(result)
            return dumps({'results': success, 'message': res}, indent=4)
        else:
            return dumps(self.force_status_done(chained_request_ids), indent=4)

    def force_status_done(self, prepid):
        if not self.crdb.document_exists(prepid):
            return dumps({"results": False, "message": "Chained request with prepid {0} does not exist".format(prepid)}, indent=4)
        cr = chained_request(self.crdb.get(prepid))
        if not (cr.get_attribute("status") in ["done", "force_done"]):
            cr.set_status(to_status="force_done")
            cr.remove_from_nonflowing_list()
            self.logger.debug("forcing chain_req status to done. cr status:%s" % (cr.get_attribute("status")))
            ret = self.crdb.save(cr.json())
            return {'prepid': prepid, 'message': ret, 'results': True}
        else:
            ret = "Chained request already in status done"
            return {'prepid': prepid, 'message': ret, 'results': False}


class ForceStatusDoneToProcessing(RESTResource):

    def __init__(self):
        self.crdb = database('chained_requests')
        self.before_request()
        self.count_call()
        self.representations = {'text/plain': self.output_text}

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def get(self, chained_request_ids):
        """
        Move chained_request from force_done to processing
        """
        if ',' in chained_request_ids:
            rlist = chained_request_ids.rsplit(',')
            res = []
            success = True
            for r in rlist:
                result = self.force_status(r)
                success = success and result.get('results', False)
                res.append(result)
            return dumps({'results': success, 'message': res}, indent=4)
        else:
            return dumps(self.force_status(chained_request_ids), indent=4)

    def force_status(self, prepid):
        if not self.crdb.document_exists(prepid):
            return dumps({"results": False,
                "message": "Chained request with prepid {0} does not exist".format(prepid)})
        cr = chained_request(self.crdb.get(prepid))
        if cr.get_attribute("status") == "force_done":
            cr.set_status(to_status="processing")
            self.logger.debug("Moving chain_req back to satus 'processing'. cr status:%s" % (
                cr.get_attribute("status")))
            ret = self.crdb.save(cr.json())
            return {'prepid': prepid, 'message': ret, 'results': True}
        else:
            ret = "Chained request already in status done"
            return {'prepid': prepid, 'message': ret, 'results': False}


class ChainedRequestsPriorityChange(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def post(self):
        fails = []
        for chain in loads(flask.request.data):
            chain_prepid = chain['prepid']
            mcm_chained_request = chained_request(self.chained_requests_db.get(chain_prepid))
            action_parameters = chain['action_parameters']
            priority = block_to_priority(action_parameters['block_number'])
            if not mcm_chained_request.set_priority(priority):
                message = 'Unable to set new priority in request %s' % chain_prepid
                fails.append(message)
                self.logger.error(message)
            else:
                mcm_chained_request.set_attribute('action_parameters', action_parameters)
                if not mcm_chained_request.save():
                    message = 'Unable to save chained request %s' % chain_prepid
                    fails.append(message)
                    self.logger.error(message)
        return {
            'results': True if len(fails) == 0 else False,
            'message': fails}
