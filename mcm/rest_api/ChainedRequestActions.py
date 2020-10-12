#!/usr/bin/env python

import flask

from json import dumps, loads
from couchdb_layer.mcm_database import database
from rest_api.RestAPIMethod import RESTResource
from json_layer.chained_request import chained_request
from json_layer.request import request
from json_layer.mccm import mccm
from tools.user_management import access_rights
from flask_restful import reqparse
from tools.locker import locker
from ChainedRequestPrepId import ChainedRequestPrepId


class CreateChainedRequest(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.db_name = 'chained_requests'
        self.before_request()
        self.count_call()

    def put(self):
        """
        Create a chained request from the provided json content
        """
        return self.import_request(flask.request.data.strip())

    def import_request(self, data):
        db = database(self.db_name)
        json_input = loads(data)
        if 'pwg' not in json_input or 'member_of_campaign' not in json_input:
            self.logger.error('Now pwg or member of campaign attribute for new chained request')
            return {"results": False}

        if 'prepid' in json_input:
            req = chained_request(json_input)
            cr_id = req.get_attribute('prepid')
        else:
            cr_id = ChainedRequestPrepId().next_id(json_input['pwg'], json_input['member_of_campaign'])
            if not cr_id:
                return {"results": False}

            req = chained_request(db.get(cr_id))
        for key in json_input:
            if key not in ['prepid', '_id', '_rev', 'history']:
                req.set_attribute(key, json_input[key])
        if not req.get_attribute('prepid'):
            self.logger.error('prepid returned was None')
            raise ValueError('Prepid returned was None')

        if 'chain_type' in json_input:
            chain_type = json_input['chain_type']
        else:
            ccdb = database('chained_campaigns')
            chain_type = ccdb.get(json_input['member_of_campaign']).get('chain_type', 'TaskChain')

        req.set_attribute('chain_type', chain_type)
        self.logger.info('Created new chained_request %s' % cr_id)
        # update history with the submission details
        req.update_history({'action': 'created'})
        return self.save_request(db, req)

    def save_request(self, db, req):
        if not db.document_exists(req.get_attribute('_id')):
            if db.save(req.json()):
                self.logger.info('new chained_request successfully saved.')
                return {"results": True, "prepid": req.get_attribute('prepid')}
            else:
                self.logger.error('Could not save new chained_request to database')
                return {"results": False}
        else:
            if db.update(req.json()):
                self.logger.info('new chained_request successfully saved.')
                return {"results": True, "prepid": req.get_attribute('prepid')}
            else:
                self.logger.error('Could not save new chained_request to database')
                return {"results": False}


class UpdateChainedRequest(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.db_name = 'chained_requests'
        self.before_request()
        self.count_call()

    def put(self):
        """
        Update a chained request from the provided json content
        """
        return self.update_request(flask.request.data)

    def update_request(self, data):
        if '_rev' not in data:
            return {"results": False, 'message': 'There is no previous revision provided'}

        try:
            chained_req = chained_request(json_input=loads(data))
        except chained_request.IllegalAttributeName:
            return {"results": False}

        prepid = chained_req.get_attribute('prepid')
        if not prepid and not chained_req.get_attribute('_id'):
            raise ValueError('Prepid returned was None')

        db = database(self.db_name)
        previous_version = chained_request(json_input=db.get(prepid))
        self.logger.info('Updating chained_request %s', prepid)
        new_priority = chained_req.get_attribute('action_parameters')['block_number']
        chained_req.set_priority(new_priority)
        # update history
        difference = self.get_obj_diff(previous_version.json(),
                                       chained_req.json(),
                                       ('history', '_rev'))
        difference = ', '.join(difference)
        chained_req.update_history({'action': 'update', 'step': difference})
        return {"results": db.update(chained_req.json())}


class DeleteChainedRequest(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def delete(self, chained_request_id):
        """
        Simply delete a chained requests
        """
        return self.delete_request(chained_request_id)

    def delete_request(self, crid):

        crdb = database('chained_requests')
        rdb = database('requests')
        mcm_cr = chained_request(crdb.get(crid))
        # get all objects
        mcm_r_s = []
        for (i, rid) in enumerate(mcm_cr.get_attribute('chain')):
            mcm_r = request(rdb.get(rid))
            # this is not a valid check as it is allowed to remove a chain around already running requests
            #    if mcm_r.get_attribute('status') != 'new':
            #        return {"results":False,"message" : "the request %s part of the chain %s for action %s is not in new status"%( mcm_r.get_attribute('prepid'),
            #                                                                                                                             crid,
            #                                                                                                                             mcm_a.get_attribute('prepid'))}
            in_chains = mcm_r.get_attribute('member_of_chain')
            if crid in in_chains:
                in_chains.remove(crid)
                self.logger.debug("Removing ChainAction member_of_chain: %s to request: %s" % (
                        mcm_cr.get_attribute("prepid"), mcm_r.get_attribute('prepid')))

                mcm_r.set_attribute('member_of_chain', in_chains)

            if i == 0:
                if len(in_chains) == 0 and mcm_r.get_attribute('status') != 'new':
                    return {"results": False, "message": "the request %s, not in status new, at the root of the chain will not be chained anymore" % rid}
            else:
                if len(in_chains) == 0:
                    return {"results": False, "message": "the request %s, not at the root of the chain will not be chained anymore" % rid}

            mcm_r.update_history({'action': 'leave', 'step': crid})
            mcm_r_s.append(mcm_r)
        if mcm_cr.get_attribute('action_parameters')['flag']:
            return {
                "results": False,
                "message": "the action for %s is not disabled" % (crid)
            }
        # then save all changes
        for mcm_r in mcm_r_s:
            if not rdb.update(mcm_r.json()):
                return {"results": False, "message": "Could not save request " + mcm_r.get_attribute('prepid')}

        return {"results": crdb.delete(crid)}


class GetChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'
        self.before_request()
        self.count_call()

    def get(self, chained_request_id):
        """
        Retrieve the content of a chained request id
        """
        return self.get_request(chained_request_id)

    def get_request(self, data):
        db = database(self.db_name)
        if ',' in data:
            rlist = data.rsplit(',')
            res = []
            for rid in rlist:
                tmp_data = db.get(prepid=rid)
                if len(tmp_data) > 0:
                    res.append(tmp_data)
            return {"results": res}
        else:
            return {"results": db.get(prepid=data)}


# REST method that makes the chained request flow to the next
# step of the chain
class FlowToNextStep(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Allows to flow a chained request with the dataset and blocks provided in the json
        """
        return self.flow2(loads(flask.request.data))

    def get(self, chained_request_id, action='', reserve_campaign=''):
        """
        Allow to flow a chained request with internal information
        """
        check_stats = True
        reserve = False
        if action != '':
            check_stats = (action != 'force')
            reserve = (action == 'reserve')
            if reserve_campaign != '':
                reserve = reserve_campaign

        return self.multiple_flow(chained_request_id, check_stats, reserve)

    def multiple_flow(self, rid, check_stats=True, reserve=False):
        if ',' in rid:
            chain_id_list = rid.rsplit(',')
        else:
            chain_id_list = [rid]
        res = []
        chains_requests_dict = {}
        for chain_id in chain_id_list:
            flow_results = self.flow(chain_id, check_stats=check_stats, reserve=reserve)
            if flow_results['results'] and 'generated_requests' in flow_results:
                chains_requests_dict[chain_id] = flow_results['generated_requests']
                flow_results.pop('generated_requests')
            res.append(flow_results)
        if len(chains_requests_dict):
            chain_id = chains_requests_dict.iterkeys().next()
            mccm_ticket = mccm.get_mccm_by_generated_chain(chain_id)
            if mccm_ticket is not None:
                mccm_ticket.update_mccm_generated_chains(chains_requests_dict)
        if len(res) == 1:
            return res[0]
        return res

    def flow2(self, data):
        db = database('chained_requests')
        chain_id = data['prepid']
        try:
            creq = chained_request(json_input=db.get(chain_id))
        except Exception as ex:
            self.logger.error('Could not initialize chained_request object. Reason: %s' % (ex))
            return {"results": str(ex)}

        self.logger.info('Attempting to flow to next step for chained_request %s' % (
                creq.get_attribute('_id')))

        # if the chained_request can flow, do it
        inputds = ''
        inblack = []
        inwhite = []
        if 'input_dataset' in data:
            inputds = data['input_dataset']
        if 'block_black_list' in data:
            inblack = data['block_black_list']
        if 'block_white_list' in data:
            inwhite = data['block_white_list']
        if 'force' in data:
            check_stats = data['force'] != 'force'
        if 'reserve' in data and data["reserve"]:
            reserve = data["reserve"]
            return creq.reserve(limit=reserve)
        return creq.flow_trial(inputds, inblack, inwhite, check_stats)

    def flow(self, chainid, check_stats=True, reserve=False):
        try:
            db = database('chained_requests')
            creq = chained_request(json_input=db.get(chainid))
        except Exception as ex:
            self.logger.error('Could not initialize chained_request object. Reason: %s' % (ex))
            return {"results": str(ex)}

        # TO-DO check if chained_request is in settings forceflow_list and remove it!
        # if the chained_request can flow, do it
        if reserve:
            self.logger.info('Attempting to reserve to next step for chained_request %s' % (
                    creq.get_attribute('_id')))
            return creq.reserve( limit = reserve, save_requests=False)

        self.logger.info('Attempting to flow to next step for chained_request %s' % (
                creq.get_attribute('_id')))
        return creq.flow_trial(check_stats=check_stats)


class RewindToPreviousStep(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, chained_request_ids):
        """
        Rewind the provided coma separated chained requests of one step.
        """
        res = []
        crids = chained_request_ids.split(",")
        for crid in crids:
            res.append(self.rewind_one(crid))

        if len(res) != 1:
            return res
        else:
            return res[0]

    def rewind_one(self, crid):
        crdb = database('chained_requests')
        rdb = database('requests')
        if not crdb.document_exists(crid):
            return {"results": False, "message": "does not exist", "prepid": crid}
        mcm_cr = chained_request(crdb.get(crid))
        current_step = mcm_cr.get_attribute('step')
        if current_step == 0:
            # or should it be possible to cancel the initial requests of a chained request
            return {"results": False, "message": "already at the root", "prepid": crid}

        # supposedly all the other requests were already reset!
        for next in mcm_cr.get_attribute('chain')[current_step + 1:]:
            # what if that next one is not in the db
            if not rdb.document_exists(next):
                self.logger.error('%s is part of %s but does not exist' % (next, crid))
                continue
            mcm_r = request(rdb.get(next))
            if mcm_r.get_attribute('status') != 'new':
                # this cannot be right!
                self.logger.error('%s is after the current request and is not new: %s' % (next, mcm_r.get_attribute('status')))
                return {"results": False, "message": "%s is not new" % (next), "prepid": crid}

        # get the one to be reset
        current_id = mcm_cr.get_attribute('chain')[current_step]
        mcm_r = request(rdb.get(current_id))
        mcm_r.reset()
        saved = rdb.update(mcm_r.json())
        if not saved:
            {"results": False, "message": "could not save the last request of the chain", "prepid": crid}
        # the current chained request has very likely been updated :
        # reload it as you have not changed anything to it yet
        mcm_cr = chained_request(crdb.get(crid))
        mcm_cr.set_attribute('step', current_step - 1)
        # set status, last status
        mcm_cr.set_last_status()
        mcm_cr.set_attribute('status', 'processing')
        saved = crdb.update(mcm_cr.json())
        if saved:
            return {"results": True, "prepid": crid}
        else:
            return {
                "results": False,
                "message": "could not save chained requests. the DB is going to be inconsistent !",
                "prepid": crid}


class RewindToRoot(RewindToPreviousStep):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, chained_request_ids):
        """
        Rewind the provided coma separated chained requests to the root request
        """
        res = []
        crdb = database('chained_requests')
        crids = chained_request_ids.split(",")
        for crid in crids:
            ch_request = chained_request(crdb.get(crid))
            if not ch_request:
                res.append({"results": False, "message": "does not exist", "prepid": crid})
                continue

            step = ch_request.get_attribute('step')
            for i in range(0, step):
                res_one = self.rewind_one(crid)
                if not res_one['results']:
                    res.append(res_one)
                    break
            else:
                res.append({'results': True, 'prepid': crid})

        if len(res) != 1:
            return res
        else:
            return res[0]


class ApproveChainedRequest(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, chained_request_id, step=-1):
        """
        move the chained request approval to the next step
        """
        return self.multiple_approve(chained_request_id, step)

    def multiple_approve(self, rid, val=-1):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.approve(r, val))
            return res
        else:
            return self.approve(rid, val)

    def approve(self, rid, val=-1):
        db = database('chained_requests')
        if not db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given chained_request id does not exist.'}
        creq = chained_request(json_input=db.get(rid))
        try:
            creq.approve(val)
        except Exception as ex:
            return {"prepid": rid, "results": False, 'message': str(ex)}

        saved = db.update(creq.json())
        if saved:
            return {"prepid": rid, "results": True}
        else:
            return {
                "prepid": rid,
                "results": False,
                'message': 'unable to save the updated chained request'}


class InspectChain(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, chained_request_id):
        """
        Inspect a chained request for next action
        """
        return self.multiple_inspect(chained_request_id)

    def multiple_inspect(self, crid):
        crlist = crid.rsplit(',')
        res = []
        crdb = database('chained_requests')
        for cr in crlist:
            if crdb.document_exists(cr):
                mcm_cr = chained_request(crdb.get(cr))
                res.append(mcm_cr.inspect())
            else:
                res.append({"prepid": cr, "results": False, 'message': '%s does not exist' % cr})

        if len(res) > 1:
            return res
        else:
            return res[0]


class SearchableChainedRequest(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, action=''):
        """
        Return a document containing several usable values that can be searched and the value can be find. /do will trigger reloading of that document from all requests
        """
        rdb = database('chained_requests')
        if action == 'do':
            all_requests = rdb.get_all()
            searchable = {}
            for request in all_requests:
                for key in ["prepid", "approval", "status", "pwg", "step",
                            "last_status", "member_of_campaign", "dataset_name"]:
                    if key not in searchable:
                        searchable[key] = set([])
                    if not key in request:
                        # that should make things break down, and due to schema evolution missed-migration
                        continue
                    if type(request[key]) == list:
                        for item in request[key]:
                            searchable[key].add(str(item))
                    else:
                        searchable[key].add(str(request[key]))

            # unique it
            for key in searchable:
                searchable[key] = list(searchable[key])
                searchable[key].sort()

            # store that value
            search = database('searchable')
            if search.document_exists('chained_requests'):
                search.delete('chained_requests')
            searchable.update({'_id': 'chained_requests'})
            search.save(searchable)
            searchable.pop('_id')
            return searchable
        else:
            # just retrieve that value
            search = database('searchable')
            searchable = search.get('chained_requests')
            searchable.pop('_id')
            searchable.pop('_rev')
            return searchable


class TestChainedRequest(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

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
                mcm_r.reset_validations_counter()
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
        if not crdb.update(mcm_cr.json()):
            return {
                "results": False,
                "message": "Failed while trying to update the document in DB",
                "prepid": chained_request_id}
        return {
            "results": True,
            "message": "run test will start soon",
            "prepid": chained_request_id}


class SoftResetChainedRequest(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self, mode='show'):
        self.before_request()
        self.count_call()

    def get(self, chained_request_id):
        """
        Does a soft reset to all relevant request in the chain
        """
        crdb = database('chained_requests')
        rdb = database('requests')

        mcm_cr = chained_request(crdb.get(chained_request_id))
        for rid in reversed(mcm_cr.get_attribute('chain')[:mcm_cr.get_attribute('step') + 1]):
            # from the current one to the first one REVERSED
            mcm_r = request(rdb.get(rid))
            try:
                mcm_r.reset(hard=False)
            except Exception as e:
                return {'prepid': chained_request_id, 'results': False, 'message': str(e)}

            mcm_r.reload()
            mcm_cr = chained_request(crdb.get(chained_request_id))
            mcm_cr.set_attribute('step', max(0, mcm_cr.get_attribute('chain').index(rid) - 1))
            mcm_cr.reload()

        return {'prepid': chained_request_id, 'results': True}


class InjectChainedRequest(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()
        self.mode = 'show' if 'get_inject' in flask.request.path else 'inject'

    def get(self, chained_request_id):
        """
        Provides the injection command and does the injection.
        """
        from tools.handlers import ChainRequestInjector, submit_pool

        _q_lock = locker.thread_lock(chained_request_id)
        if not locker.thread_acquire(chained_request_id, blocking=False):
            return {"prepid": chained_request_id, "results": False,
                    "message": "The request {0} request is being handled already".format(
                        chained_request_id)}

        thread = ChainRequestInjector(prepid=chained_request_id, lock=locker.lock(chained_request_id), queue_lock=_q_lock,
                check_approval=False)
        if self.mode == 'show':
            self.representations = {'text/plain': self.output_text}
            return thread.make_command()
        else:
            submit_pool.add_task(thread.internal_run)
            return {
                "results": True,
                "message": "chain submission for %s will be forked unless same request is being handled already" % chained_request_id,
                "prepid": chained_request_id}


class ChainsFromTicket(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('ticket', type=str, required=True)
        self.parser.add_argument('page', type=int, default=0)
        self.parser.add_argument('limit', type=int, default=20)

    def get(self):
        """
        Get all the generated chains from a ticket
        """
        kwargs = self.parser.parse_args()
        page = kwargs['page']
        limit = kwargs['limit']
        if page < 0:
            page = 0
            limit = 999999

        ticket_prepid = kwargs['ticket']
        chained_requests_db = database('chained_requests')
        mccms_db = database('mccms')
        mccm_query = mccms_db.construct_lucene_query({'prepid': ticket_prepid})
        result = mccms_db.full_text_search("search", mccm_query, page=-1)
        if len(result) == 0:
            self.logger.warning("Mccm prepid %s doesn't exit in db" % ticket_prepid)
            return {}
        self.logger.info("Getting generated chains from ticket %s" % ticket_prepid)
        generated_chains = list(result[0]['generated_chains'].iterkeys())
        generated_chains.sort()
        start = page * limit
        if start > len(generated_chains):
            return []
        end = start + limit
        end = end if end <= len(generated_chains) else len(generated_chains)
        chained_request_list = []
        while start < end:
            fetch_till = start + 20
            fetch_till = end if fetch_till > end else fetch_till
            chained_request_query = chained_requests_db.construct_lucene_query({'prepid': generated_chains[start:fetch_till]}, boolean_operator="OR")
            chained_request_list += chained_requests_db.full_text_search("search", chained_request_query)
            start += 20
        return chained_request_list


class TaskChainDict(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('scratch', type=str)
        self.parser.add_argument('upto', type=int)
        self.representations = {'text/plain': self.output_text}

    def get(self, chained_request_id):
        """
        Provide the taskchain dictionnary for uploading to request manager
        """
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
            # mcm_crs = crdb.query(query="root_request==%s"% chained_request_id) ## not only when its the root of
            mcm_crs = crdb.query(query="contains==%s" % chained_request_id)
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
                __total_time_evt += mcm_r.get_sum_time_events()
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

    access_limit = access_rights.user

    def __init__(self):
        path = flask.request.path
        if 'setup' in path:
            self.opt = 'setup'
        elif 'test' in path:
            self.opt = 'test'
        else:
            self.opt = 'valid'
            access_limit = access_rights.administrator
        self.before_request()
        self.count_call()
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('events', type=int)
        self.parser.add_argument('scratch', type=str, default='')
        self.parser.add_argument('directory', type=str, default='')
        self.representations = {'text/plain': self.output_text}

    def get(self, chained_request_id):
        kwargs = self.parser.parse_args()
        crdb = database('chained_requests')
        if not crdb.document_exists(chained_request_id):
            return {"results": False,
                    "message": "Chained request with prepid {0} does not exist".format(chained_request_id)}
        cr = chained_request(crdb.get(chained_request_id))
        events = None
        run = False
        valid = False
        directory = ''
        __scratch = kwargs["scratch"].lower() == 'true'
        if self.opt == 'test' or self.opt == 'valid':
            run = True
        if self.opt == 'valid':
            valid = True
        return cr.get_setup(directory=kwargs['directory'], run=run, events=kwargs['events'],
                validation=valid, scratch=__scratch, gen_script=run)


class ForceChainReqToDone(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.crdb = database('chained_requests')
        self.ldb = database('lists')
        self.before_request()
        self.count_call()
        self.representations = {'text/plain': self.output_text}

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

    access_limit = access_rights.production_manager

    def __init__(self):
        self.crdb = database('chained_requests')
        self.before_request()
        self.count_call()
        self.representations = {'text/plain': self.output_text}

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


class ToForceFlowList(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.ldb = database('lists')
        self.cdb = database('chained_requests')
        self.before_request()
        self.count_call()

    def get(self, chained_request_ids):
        """
        Add selected prepid's to global force complete list for later action
        """
        if ',' in chained_request_ids:
            rlist = chained_request_ids.rsplit(',')
        else:
            rlist = [chained_request_ids]
        res = []
        __updated = False

        forceflow_list = self.ldb.get("list_of_forceflow")
        # TO-DO check if prepid exists!
        # TO-DO check the status of chain_req!
        for el in rlist:
            if el not in forceflow_list["value"]:
                forceflow_list["value"].append(el)
                chain_req = chained_request(self.cdb.get(el))
                chain_req.update_history({'action': 'add_to_forceflow'})
                self.cdb.save(chain_req.json())
                res.append({"prepid": el, 'results': True, 'message': 'OK'})
                __updated = True
            else:
                res.append({"prepid": el, 'results': False, 'message': 'Chained request already in forceflow list'})

        # TO-DO check the update return value
        if __updated:
            self.ldb.update(forceflow_list)

        return res


class ChainedRequestsPriorityChange(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.chained_requests_db = database("chained_requests")
        self.before_request()
        self.count_call()

    def post(self):
        fails = []
        for chain in loads(flask.request.data):
            chain_prepid = chain['prepid']
            mcm_chained_request = chained_request(self.chained_requests_db.get(chain_prepid))
            action_parameters = chain['action_parameters']
            if not mcm_chained_request.set_priority(action_parameters['block_number']):
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


class RemoveFromForceFlowList(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.ldb = database('lists')
        self.before_request()
        self.count_call()

    def delete(self, chained_request_ids):
        """
        Remove selected prepid's from global force_complete list
        """
        if ',' in chained_request_ids:
            rlist = chained_request_ids.rsplit(',')
        else:
            rlist = [chained_request_ids]
        res = []

        forceflow_list = self.ldb.get("list_of_forceflow")
        for el in rlist:
            if el not in forceflow_list["value"]:
                res.append({"prepid": el, 'results': False, 'message': 'Not in forceflow list'})
            else:
                forceflow_list["value"].remove(el)
                res.append({"prepid": el, 'results': True, 'message': 'OK'})

        # TO-DO check the update return value
        ret = self.ldb.update(forceflow_list)

        return res


class GetUniqueChainedRequestValues(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, field_name):
        """
        Get unique values for navigation by field_name
        """
        return self.get_unique_values(field_name)

    def get_unique_values(self, field_name):
        kwargs = flask.request.args.to_dict()
        db = database('chained_requests')
        if 'limit' in kwargs:
            kwargs['limit'] = int(kwargs['limit'])
        kwargs['group'] = True
        return db.raw_view_query_uniques(view_name=field_name, options=kwargs, cache='startkey' not in kwargs)
