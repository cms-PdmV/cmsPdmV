#!/usr/bin/env python
from copy import deepcopy
import flask
import traceback
import time

from flask import app
from flask.globals import request
import json
from collections import defaultdict
import re

from couchdb_layer.mcm_database import database as Database
from RestAPIMethod import RESTResource
from json_layer.request import request as Request
from json_layer.chained_request import chained_request as ChainedRequest
from json_layer.sequence import sequence as Sequence
from json_layer.campaign import campaign as Campaign
from json_layer.user import user
from tools.locator import locator
from tools.communicator import communicator
from tools.locker import locker
import tools.settings as settings
from tools.handlers import RequestInjector, submit_pool
from tools.user_management import access_rights
from tools.priority import priority
from flask_restful import reqparse
from tools.user_management import user_pack as UserPack


class RequestRESTResource(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.db_name = 'requests'
        self.with_trace = True

    def import_request(self, request_json, cloned_from=None):
        request_db = Database('requests')
        campaign_db = Database('campaigns')
        campaign_name = request_json['member_of_campaign']
        campaign_json = campaign_db.get(campaign_name)
        if not campaign_json:
            return {"results": False,
                    "message": 'Campaign %s could not be found' % (campaign_name)}

        if campaign_json.get('status') != 'started':
            return {"results": False,
                    "message": "Cannot create a request in a campaign that is not started"
                               "%s is %s" % (campaign_name, campaign_json.get('status'))}

        if 'prepid' in request_json or '_id' in request_json:
            return {"results": False,
                    "message": '"prepid" and "_id" should not exist in new request data'}

        pwg = request_json['pwg']
        self.logger.info('Building new request for %s in %s', pwg, campaign_name)
        request = Request(json_input=request_json)
        request.reset_options()
        request.set_attribute('history', [])
        if cloned_from:
            request.update_history({'action': 'clone', 'step': cloned_from})
        else:
            request.update_history({'action': 'created'})

        # Add PWG as interested one
        if pwg not in request.get_attribute('interested_pwg'):
            request.set_attribute('interested_pwg', request.get_attribute('interested_pwg') + [pwg])

        # put a generator info by default in case of possible root request
        # TODO: Review this
        if campaign_json.get('root') <= 0:
            request.update_generator_parameters()

        prepid = '%s-%s' % (pwg, campaign_name)
        with locker.lock('create-request-%s' % (prepid)):
            self.logger.info('Will try to find new prepid for request %s-*', prepid)
            raise NotImplemented('GENERATING PREPID FOR REQUEST')

        return {'results': True,
                'prepid': prepid}


class CloneRequest(RequestRESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Make a clone with specific requirements
        """
        data = json.loads(flask.request.data)
        prepid = data.get('prepid', '').strip()
        if not prepid:
            return {'results': False,
                    'message': 'Missing prepid'}

        pwg = data.get('pwg', '').strip().upper()
        if not prepid:
            return {'results': False,
                    'message': 'Missing PWG'}

        new_campaign = data.get('member_of_campaign', '').strip()
        if not prepid:
            return {'results': False,
                    'message': 'Missing campaign'}

        request_db = Database('requests')
        request_json = request_db.get(prepid)
        if not request_json:
            return {'results': False,
                    'message': 'Cannot clone from "%s" because it does not exist' % (prepid)}

        if request_json.get('flown_with'):
            return {"results": False,
                    "message": "Cannot clone a request that has been flown, can clone only root"}

        old_campaign = request_json['member_of_campaign']
        # Attributes to move over to new request
        to_move = ['input_dataset', 'dataset_name', 'pileup_dataset_name', 'process_string',
                   'fragment_tag', 'mcdb_id', 'notes', 'total_events', 'name_of_fragment',
                   'fragment', 'type', 'interested_pwg', 'events_per_lumi', 'generators']

        if old_campaign == new_campaign:
            to_move.extend(['time_event', 'size_event', 'generator_parameters'])

        new_request = {attribute: request_json[attribute] for attribute in to_move}
        new_request['member_of_campaign'] = new_campaign
        new_request['pwg'] = pwg
        return self.import_request(new_request, cloned_from=prepid)


class ImportRequest(RequestRESTResource):

    #access_limit = access_rights.generator_contact ## maybe that is wrong

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Saving a new request from a given dictionnary
        """
        data = json.loads(flask.request.data)
        return self.import_request(data)


class UpdateRequest(RequestRESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Updating an existing request with an updated dictionary
        """
        data = json.loads(flask.request.data)
        rev = data.get('_rev')
        if not rev:
            return {'results': False,
                    'message': 'Missing revision ("_rev") in submitted data'}

        prepid = data.get('prepid', data.get('_id'))
        if not prepid:
            return {'results': False,
                    'message': 'Missing prepid ("prepid") in submitted data'}

        data['prepid'] = prepid
        data['_id'] = prepid
        request_db = Database('requests')
        with locker.lock('create-request-%s' % (prepid)):
            request_json = request_db.get(prepid)
            if not request_json:
                return {"results": False,
                        'message': 'Request "%s" does not exist' % (prepid)}

            if rev != request_json['_rev']:
                    return {'results': False,
                            'message': 'Provided revision does not match revision in database'}

            old_request = Request(request_json)
            # Create new request data
            request_json = deepcopy(request_json)
            for to_pop in ('prepid', '_id', 'history'):
                data.pop(to_pop, None)

            request_json.update(data)
            new_request = Request(request_json)
            # Check edited values
            editing_info = old_request.get_editable()
            for (key, editable) in editing_info.items():
                if editable or key == 'sequences':
                    # Do not check attributes that can be edited
                    continue

                old_value = old_request.get_attribute(key)
                new_value = new_request.get_attribute(key)
                if old_value != new_value:
                    self.logger.error('Editing "%s" of %s is not allowed: %s -> %s',
                                      key, prepid, old_value, new_value)
                    return {"results": False,
                            'message': 'Editing "%s" of %s is not allowed' % (key, prepid)}

            # Special check for validation multiplier
            new_multiplier = old_request.get_attribute('validation').get('time_multiplier', 1)
            old_multiplier = new_request.get_attribute('validation').get('time_multiplier', 1)
            if new_multiplier != old_multiplier and new_multiplier > 2:
                if new_request.current_user_level < access_rights.generator_convener:
                    return {"results": False,
                            'message': 'You need to be at least GEN convener to set validation to >16h'}

            self.logger.info('Updating request %s' % (prepid))
            difference = self.get_obj_diff(old_request.json(),
                                           new_request.json(),
                                           ('history', '_rev'))
            if not difference:
                return {'results': True}

            new_request.update_history({'action': 'update', 'step': ', '.join(difference)})
            if not request_db.update(new_request.json()):
                self.logger.error('Could not save %s to database', prepid)
                return {'results': False,
                        'message': 'Could not save %s to database' % (prepid)}

        return {"results": True}


class GetRequest(RESTResource):

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_id):
        """
        Retreive the dictionnary for a given request
        """
        request_db = Database('requests')
        request_id = request_id.strip()
        request_json = request_db.get(request_id)
        return {"results": request_json}


class DeleteRequest(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def delete(self, request_id):
        """
        Simply delete a request
        """
        request_db = Database('requests')
        request_json = request_db.get(request_id)
        approval = request_json['approval']
        status = request_json['status']
        if approval != 'none' or status != 'new':
            return {'results': False,
                    'prepid': request_id,
                    'message': 'Cannot delete "%s-%s" request, must be "none-new"' % (approval,
                                                                                      status)}

        chained_request_ids = request_json['member_of_chain']
        if chained_request_ids:
            # If request is a member of chain, only prod managers can delete it
            user = UserPack(db=True)
            user_role = user.user_dict.get('role')
            self.logger.info('User %s (%s) is trying to delete %s',
                            user.get_username(),
                            user_role,
                            request_id)
            if user_role not in {'production_manager', 'administrator'}:
                return {"results": False,
                        "prepid": request_id,
                        "message": 'Only production managers and administrators can delete '
                                   'requests that are member of chained requests'}

        chained_request_db = Database('chained_requests')
        chained_requests = chained_request_db.db.bulk_get(chained_request_ids)
        chained_requests_with_request = []
        chained_requests_to_delete = []
        for chained_request in chained_requests:
            if not chained_request:
                # Don't care about this in deletion
                continue

            chain = chained_request['chain']
            if request_id not in chain:
                # Don't care about this in deletion
                continue

            chained_request_id = chained_request['prepid']
            if chained_request.get('action_parameters', {}).get('flag', False):
                return {'results': False,
                        'prepid': request_id,
                        'message': 'Request is a member of a valid chained request %s' % (chained_request_id)}

            if request_id != chain[-1]:
                return {'results': False,
                        'prepid': request_id,
                        'message': 'Request must be a last request in all its chained requests'}

            if chained_request['step'] >= chain.index(request_id):
                # Request is the current step in the chain
                return {'results': False,
                        'prepid': request_id,
                        'message': "Request is the current step of chained request %s" % (chained_request_id)}

            if request_id == chain[0]:
                # Request is root - delete it together with the chained request
                chained_requests_to_delete.append(chained_request_id)
            else:
                # Request is not root - just pop it off the chained request
                chained_requests_with_request.append(chained_request)

        for chained_request_json in chained_requests_with_request:
            # Chained requests that should have request at the end of the chain
            chained_request = ChainedRequest(chained_request_json)
            chain = chained_request.get_attribute('chain')
            chain.remove(request_id)
            chained_request.set_attribute('chain', chain)
            chained_request.update_history({'action': 'remove request', 'step': request_id})
            chained_request.reload()

        for chained_request_id in chained_requests_to_delete:
            chained_request_db.delete(chained_request_id)

        # Delete from DB
        if not request_db.delete(request_id):
            self.logger.error('Could not delete %s from database', request_id)
            return {'results': False,
                    'message': 'Could not delete %s from database' % (request_id)}

        return {'results': True}


class OptionResetForRequest(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_ids):
        """
        Reset the options for request
        """
        request_db = Database('requests')
        request_ids = [r.strip() for r in request_ids.split(',') if r.strip()]
        results = []
        requests = request_db.db.bulk_get(request_ids)
        for req_json in requests:
            if not req_json:
                continue

            prepid = req_json['prepid']
            if req_json['approval'] != 'none' or req_json['status'] != 'new':
                results.append({"results": False,
                                "prepid": prepid,
                                "message": "Cannot option reset %s because it is not none-new" % (prepid)})
                continue

            req = request(req_json)
            req.reset_options()
            results.append({"results": True,
                            "prepid": prepid})

        if len(results) == 1:
            return results[0]

        return results


class GetCmsDriverForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.json = {}
        self.before_request()
        self.count_call()

    def get(self, request_id):
        """
        Retrieve the cmsDriver commands for a given request
        """
        db = Database('requests')
        return self.get_cmsDriver(db.get(prepid=request_id))

    def get_cmsDriver(self, data):
        try:
            mcm_req = request(json_input=data)
        except request.IllegalAttributeName:
            return {"results": ''}

        return {"results": mcm_req.build_cmsDrivers()}


class GetFragmentForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.before_request()
        self.count_call()
        self.representations = {'text/plain': self.output_text}

    def get(self, request_id, version=None):
        """
        Retrieve the fragment as stored for a given request
        """
        db = Database(self.db_name)
        res = self.get_fragment(db.get(prepid=request_id))
        return dumps(res) if isinstance(res, dict) else res

    def get_fragment(self, data):
        try:
            mcm_req = request(json_input=data)
        except request.IllegalAttributeName:
            return {"results": ''}

        fragmentText = mcm_req.get_attribute('fragment')
        return fragmentText


class GetSetupForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
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
        self.representations = {'text/plain': self.output_text}

    def get(self, prepid, events=None):
        """
        Retrieve the script necessary to setup and test a given request
        get_setup - returns file for config generation for submission
        get_test - returns file for user validation
        get_valid - returns file for automatic validation
        """
        for_validation = self.opt in ('test', 'valid')
        automatic_validation = self.opt == 'valid'
        request_db = Database('requests')
        if request_db.document_exists(prepid):
            req = request(request_db.get(prepid))
            output_text = req.get_setup_file2(for_validation=for_validation, automatic_validation=automatic_validation, threads=1)
            return output_text
        else:
            return dumps({"results": False, "message": "%s does not exist" % prepid}, indent=4)


class GetRequestByDataset(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()
        self.representations = {'text/plain': self.output_text}

    def get(self, dataset):
        """
        retrieve the dictionnary of a request, based on the output dataset specified
        """
        datasetname = '/' + dataset.replace('*', '')
        rdb = Database('requests')
        r = rdb.search({'produce': datasetname}, page=-1)

        if len(r):
            return self.output_text({"results": r[0]},
                                    200,
                                    headers={'Content-Type': 'application/json'})
        else:
            return self.output_text({"results": {}},
                                    200,
                                    headers={'Content-Type': 'application/json'})


class GetRequestOutput(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.before_request()
        self.count_call()

    def get(self, prepid, is_chain=''):
        """
        Retrieve the list of datasets from a give request
        """
        # how to structure better the output ? using a dict ?
        res = {prepid: []}
        rdb = Database('requests')

        if is_chain == 'chain':
            collect = []
            crdb = Database('chained_requests')
            for cr in crdb.search({'contains': prepid}, page=-1):
                for r in reversed(cr['chain']):
                    if r not in collect:
                        collect.append(r)
        else:
            collect = [prepid]

        for rid in collect:
            mcm_r = rdb.get(rid)
            if len(mcm_r['reqmgr_name']):
                if 'pdmv_dataset_list' in mcm_r['reqmgr_name'][-1]['content']:
                    res[prepid].extend(mcm_r['reqmgr_name'][-1]['content']['pdmv_dataset_list'])
                else:
                    res[prepid].append(mcm_r['reqmgr_name'][-1]['content']['pdmv_dataset_name'])

        return res


class ApproveRequest(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def post(self):
        """
        Approve to next step. Ignore GET parameter, use list of prepids from POST data
        """
        data = json.loads(flask.request.data)
        prepids = data.get('prepid')
        if isinstance(prepids, (basestring, str)):
            prepids = prepids.split(',')
        elif not isinstance(prepids, list):
            return {'results': False,
                    'message': 'Expected a string or list of prepids'}

        return self.approve_many(prepids)

    def approve_many(self, prepids):
        self.allowed_to_approve_users = set(settings.get_value('allowed_to_approve'))
        self.allowed_to_approve_roles = {'administrator', 'generator_convener'}
        self.request_db = Database('requests')
        requests = self.request_db.db.bulk_get(prepids)
        results = []
        for prepid, request in zip(prepids, requests):
            if not request:
                results.append({"results": False,
                                "prepid": prepid,
                                'message': 'Request "%s" does not exist' % (prepid)})
                continue

            assert(prepid == request['prepid'])
            with locker.lock(prepid):
                results.append(self.approve(request))

        if len(results) == 1:
            return results[0]

        return results

    def approve(self, request_json):
        request = Request(request_json)
        prepid = request.get_attribute('prepid')
        self.logger.info('Approving request %s' % (prepid))
        if request.get_attribute('approval') == 'define' and request.get_attribute('status') == 'defined':
            username = self.user_dict.get('username', '')
            role = self.user_dict.get('role', 'user')
            if role not in self.allowed_to_approve_roles and username not in self.allowed_to_approve_users:
                self.logger.info('%s (%s) stopped from approving %s' % (username, role, prepid))
                return {'results': False,
                        'prepid': prepid,
                        'message': 'You are not allowed to approve requests'}

            self.logger.info('%s (%s) allowed to approve %s' % (username, role, prepid))

        approved, message = request.approve()
        if not approved:
            return {'results': False,
                    'prepid': prepid,
                    'message': message}

        if not self.request_db.update(request.json()):
            return {'results': False,
                    'prepid': prepid,
                    'message': 'Error saving "%s" to database' % (prepid)}

        return {'results': True, 'prepid': prepid}


class ResetRequestApproval(ApproveRequest):

    access_limit = access_rights.generator_contact

    def __init__(self):
        ApproveRequest.__init__(self)
        self.hard = 'soft_reset' not in flask.request.path
        self.before_request()
        self.count_call()

    def get(self, request_id):
        """
        Reste both approval and status to their initial state.
        """
        return self.multiple_approve(request_id, 0, self.hard)


class GetStatus(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_ids):
        """
        Get the status of the coma separated request id.
        """
        return self.multiple_status(request_ids)

    def multiple_status(self, rid):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.status(r))
            return res
        else:
            return self.status(rid)

    def status(self, rid):
        __retries = 3
        if rid == "":
            self.logger.info("someone is looking for empty request status")
            return {"results": "You shouldnt be looking for empty prepid"}

        db = Database('requests')
        if not db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given request id does not exist.'}

        mcm_r = db.get(rid)

        while 'status' not in mcm_r:
            if __retries == 0:
                return {"prepid": rid, "results": "Ran out of retries to query DB"}
            time.sleep(1)
            mcm_r = db.get(rid)
            __retries -= 1

        return {rid: mcm_r['status']}


class GetStatusAndApproval(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, prepid):
        """
        Get the status and approval of given prepid(s)
        """
        prepids = list(set(x.strip() for x in prepid.split(',') if x.strip()))
        if not prepids:
            return {'results': False,
                    'message': 'No prepids given'}

        request_db = Database('requests')
        results = [r for r in request_db.bulk_get(prepids) if r]
        return {req['prepid']: '%s-%s' % (req['approval'], req['status']) for req in results}


class InspectStatus(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_ids, force=""):
        """
        Triggers the internal inspection of the status of a request or coma separated list of request
        """
        return self.multiple_inspect(request_ids, force == "force")

    def multiple_inspect(self, rid, force_req):
        rlist = rid.rsplit(',')
        res = []
        db = Database('requests')
        crdb = Database('chained_requests')
        for r in rlist:
            if not db.document_exists(r):
                res.append({"prepid": r, "results": False, 'message': '%s does not exist' % r})
                continue
            mcm_r = request(db.get(r))
            if mcm_r:
                answer = mcm_r.inspect(force_req)
                res.append(answer)
                # trigger chained request inspection on "true" results from inspection
                if answer['results']:
                    crs = mcm_r.get_attribute('member_of_chain')
                    for cr in crs:
                        if crdb.document_exists(cr):
                            mcm_cr = chained_request(crdb.get(cr))
                            res.append(mcm_cr.inspect())
                        else:
                            res.append({"prepid": cr, "results": False, 'message': '%s does not exist' % cr})
            else:
                res.append({"prepid": r, "results": False, 'message': '%s does not exist' % r})


        if len(res) > 1:
            return res
        else:
            return res[0]


class UpdateStats(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_id, refresh=None, forced=None):
        """
        Triggers the forced update of the stats page for the given request id
        """
        refresh_stats = True
        if refresh == "no_refresh":
            refresh_stats = False

        # set forcing argument
        force = True if forced == "force" else False

        rdb = Database('requests')
        if not rdb.document_exists(request_id):
            return {"prepid": request_id, "results": False,
                    "message": '%s does not exist' % request_id}

        mcm_r = request(rdb.get(request_id))
        if mcm_r.get_stats(forced=force):
            mcm_r.reload()
            return {"prepid": request_id, "results": True}
        else:
            if force:
                mcm_r.reload()
                return {
                    "prepid": request_id,
                    "results": False,
                    "message": "no apparent changes, but request was foced to reload"}
            else:
                return {
                    "prepid": request_id,
                    "results": False,
                    "message": "no apparent changes"}

class UpdateEventsFromWorkflow(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, wf_id):
        """
        Update statistics for requests from specified workflow
        """

        rdb = Database('requests')
        # include only prepids for us
        res = rdb.search({"reqmgr_name": wf_id}, page=-1, include_fields='prepid')
        if len(res) == 0:
            return {"workflow": wf_id, "results": False,
                    "message": "No requests found produced by this workflow"}

        ret = []
        # iterate on all requests running in same workflow, then put stats_update
        # we do not trigger stats refresh as this api will be triggered by stats
        for req in res:
            mcm_r = request(rdb.get(req["prepid"]))
            if mcm_r.get_stats():
                mcm_r.reload()
                ret.append({"prepid": req["prepid"], "results": True})
            else:
                ret.append({
                    "prepid": req["prepid"],
                    "results": False,
                    "message": "no apparent changes"})

        return ret

class SetStatus(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_ids, step=-1):
        """
        Perform the change of status to the next (/ids) or to the specified index (/ids/index)
        """
        return self.multiple_status(request_ids, step)

    def multiple_status(self, rid, val=-1):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.status(r, val))
            return res
        else:
            return self.status(rid, val)

    def status(self, rid, step=-1):
        db = Database('requests')
        if not db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given request id does not exist.'}

        req = request(json_input=db.get(rid))

        try:
            # set the status with a notification if done via the rest api
            req.set_status(step, with_notification=True)
        except request.WrongStatusSequence as ex:
            return {"prepid": rid, "results": False, 'message': str(ex)}
        except Exception:
            return {"prepid": rid, "results": False, 'message': 'Unknown error' + traceback.format_exc()}

        return {"prepid": rid, "results": db.update(req.json())}


class GetEditable(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_id):
        """
        Retreive the fields that are currently editable for a given request id
        """
        request_db = Database('requests')
        request_json = request_db.get(request_id)
        request = Request(request_json)
        editable = request.get_editable()
        return {'results': editable}


class GetDefaultGenParams(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_id):
        """
        Get schema for the generator parameters object in request
        """
        from json_layer.generator_parameters import generator_parameters
        params = generator_parameters()
        return {"results": params.json()}


class NotifyUser(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Sends the prodived posted text to the user registered to a list of requests request
        """
        data = loads(flask.request.data.strip())
        # read a message from data
        message = data['message']
        l_type = locator()
        pids = data['prepids']
        results = []
        rdb = Database('requests')

        for pid in pids:
            if not rdb.document_exists(pid):
                results.append({"prepid": pid, "results": False,
                        "message": "%s does not exist" % pid})

                return results

            req = request(rdb.get(pid))
            # notify the actors of the request
            subject = 'Communication about request %s' % pid
            message = '%s \n\n %srequests?prepid=%s\n' % (message, l_type.baseurl(), pid)
            req.notify(subject, message, accumulate=True)

            # update history with "notification"
            req.update_history({'action': 'notify', 'step': message})
            if not rdb.save(req.json()):
                results.append({"prepid": pid, "results": False,
                        "message": "Could not save %s" % pid})

                return results

            results.append({"prepid": pid, "results": True, "message": "Notification send for %s" % pid})

        return results


class RegisterUser(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_ids):
        """
        Any person with cern credential can register to a request or a list of requests
        """
        return self.multiple_register(request_ids)

    def multiple_register(self, rid):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.register_user(r))
            return res
        else:
            return self.register_user(rid)

    def register_user(self, pid):
        rdb = Database('requests')
        udb = Database('users')
        request_in_db = request(rdb.get(pid))
        current_user = request_in_db.current_user
        if not current_user or not udb.document_exists(current_user):
            return {
                "prepid": pid,
                "results": False,
                'message': "You (%s) are not a registered user to McM, correct this first" % current_user}

        if current_user in request_in_db.get_actors():
            return {
                "prepid": pid,
                "results": False,
                'message': "%s already in the list of people for notification of %s" % (current_user, pid)}

        request_in_db.update_history({'action': 'register', 'step': current_user})
        rdb.save(request_in_db.json())
        return {"prepid": pid, "results": True, 'message': 'You (%s) are registered to %s' % (current_user, pid)}


class GetActors(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_id, what=None):
        """
        Provide the list of user registered and actors to a given request
        """
        return self.show_user(request_id, what)

    def show_user(self, pid, what=None):
        rdb = Database('requests')
        request_in_db = request(rdb.get(pid))
        if what:
            return request_in_db.get_actors(what=what)
        else:
            return request_in_db.get_actors()


class SearchableRequest(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        """
        Return a document containing several usable values that can be searched and the value can be find. /do will trigger reloading of that document from all requests
        """
        searchable = {}
        for key in ['energy', 'dataset_name', 'status', 'approval', 'extension', 'generators',
                             'member_of_chain', 'pwg', 'process_string', 'mcdb_id', 'prepid', 'flown_with',
                             'member_of_campaign', 'tags']:
            searchable[key] = []
        return searchable


class RequestLister():
    def __init__(self):
        pass

    def get_objects(self, all_ids, retrieve_db):
        all_objects = []
        if len(all_ids) and retrieve_db:
            for oid in all_ids:
                if retrieve_db.document_exists(oid):
                    all_objects.append(retrieve_db.get(oid))
        self.logger.info("Got %s ids identified" % (len(all_objects)))
        return {"results": all_objects}

    def identify_an_id(self, word, in_range_line, cdb, odb):
        all_campaigns = map(lambda x: x['id'], cdb.get_all())
        if word.count('-') == 2:
            (pwg, campaign, serial) = word.split('-')
            if len(pwg) != 3:
                return None
            if not serial.isdigit():
                return None
            if campaign not in all_campaigns:
                return None
            if odb.document_exists(word):
                return word
            elif in_range_line:
                return word
        return None

    def identify_a_dataset_name(self, word):
        if word.count('/') == 3:
            (junk, dsn, ps, tier) = word.split('/')
            if junk:
                return None
            return dsn

    def get_list_of_ids(self, odb, json_data=None):
        self.logger.info("Got a file from uploading")
        if json_data is not None:
            data = json_data
        else:
            data = loads(flask.request.data.strip())

        text = data['contents']

        all_ids = []
        all_dsn = {}
        # parse that file for prepids
        possible_campaign = None
        cdb = Database('campaigns')

        for line in text.split('\n'):
            in_the_line = []
            for word in line.split():
                if word.endswith(','):
                    word = word[0:-2]
                if word.startswith(','):
                    word = word[1:]

                if word.startswith('@-'):
                    possible_campaign = None
                elif word.startswith('@'):
                    possible_campaign = word[1:]
                    if possible_campaign not in all_dsn:
                        all_dsn[possible_campaign] = []

                # is that a prepid ?
                an_id = None
                a_dsn = None
                if possible_campaign is None:
                    an_id = self.identify_an_id(word, '->' in line, cdb, odb)

                if an_id:
                    all_ids.append(an_id)
                    in_the_line.append(an_id)
                elif possible_campaign:
                    a_dsn = self.identify_a_dataset_name(word)
                    if a_dsn:
                        all_dsn[possible_campaign].append(a_dsn)

                # the ley word for range
                if word == '->':
                    if len(in_the_line):
                        in_the_line = [in_the_line[-1]]

                # dealing with id range
                if len(in_the_line) == 2:
                    id_start = in_the_line[0]
                    id_end = in_the_line[1]
                    in_the_line = []
                    if id_start[0:4] == id_end[0:4]:
                        serial_start = int(id_start.split('-')[-1])
                        serial_end = int(id_end.split('-')[-1]) + 1
                        for serial in range(serial_start, serial_end):
                            all_ids.append('-'.join(id_start.split('-')[0: 2] + ['%05d' % serial]))

        for (possible_campaign, possible_dsn) in all_dsn.items():
            if not cdb.document_exists(possible_campaign):
                continue
                # get all requests
            all_requests = odb.search({'member_of_campaign': possible_campaign}, page=-1)
            for _request in all_requests:
                if _request['dataset_name'] in possible_dsn:
                    all_ids.append(_request['prepid'])
        all_ids = list(set(all_ids))
        all_ids.sort()
        return all_ids


class RequestsFromFile(RequestLister, RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        RequestLister.__init__(self)
        self.before_request()
        self.count_call()

    def put(self):
        """
        Parse the posted text document for request id and request ranges for display of requests
        """
        rdb = Database('requests')
        all_ids = self.get_list_of_ids(rdb)
        return self.get_objects(all_ids, rdb)


class StalledReminder(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, time_since=15, time_remaining=15, below_completed=100.0):
        """
        Collect the requests that have been running for too long (/since) or will run for too long (/since/remaining) and send a reminder, and below (/since/remaining/below) a certain percentage of completion
        """
        rdb = Database('requests')
        bdb = Database('batches')
        statsDB = Database('stats', url='http://vocms074.cern.ch:5984/')
        __query = rdb.make_query()
        today = time.mktime(time.gmtime())
        text = "The following requests appear to be not progressing since %s days or will require more than %s days to complete and are below %4.1f%% completed :\n\n" % (time_since, time_remaining, below_completed)
        reminded = 0
        by_batch = defaultdict(list)
        request_prepids = []
        page = 0
        rs = [{}]
        while len(rs) > 0:
            rs = rdb.search({'status': 'submitted'}, page=page, limit=100)
            self.logger.info('Found %d requests that are in status submitted in page %d' % (len(rs), page))
            page += 1
            for r in rs:
                date_s = filter(lambda h: 'step' in h and h['step'] == 'submitted', r['history'])[-1]['updater']['submission_date']
                date = time.mktime(time.strptime(date_s, "%Y-%m-%d-%H-%M"))
                elapsed_t = (today - date)
                elapsed = (today - date) / 60. / 60. / 24.  # in days
                remaining = float("inf")
                if r['completed_events']:
                    remaining_t = (elapsed_t * ((r['total_events'] / float(r['completed_events'])) - 1))
                    remaining = remaining_t / 60. / 60. / 24.
                    if remaining < 0:  # already over stats
                        remaining = 0.
                fraction = min(100., r['completed_events'] * 100. / r['total_events'])  # maxout to 100% completed
                if fraction > below_completed:
                    continue

                if (remaining > time_remaining and remaining != float('Inf')) or (elapsed > time_since and remaining != 0):
                    reminded += 1
                    bs = bdb.search({'contains': r['prepid'],
                                     'status': ['announced', 'hold']},
                                    page=-1)
                    # take the last one ?
                    in_batch = 'NoBatch'
                    if len(bs):
                        in_batch = bs[-1]['prepid']
                    wma_status = 'not-found'
                    if len(r['reqmgr_name']):
                        wma_name = r['reqmgr_name'][-1]['name']
                        stats = statsDB.get(wma_name)
                        if stats and 'pdmv_status_from_reqmngr' in stats:
                            wma_status = stats['pdmv_status_from_reqmngr']

                    line = "%30s: %4.1f days since submission: %8s = %5.1f%% completed, remains %6.1f days, status %s, priority %s \n" % (
                        r['prepid'],
                        elapsed,
                        r['completed_events'],
                        fraction,
                        remaining,
                        wma_status,
                        r['priority'])
                    by_batch[in_batch].append(line)
                    request_prepids.append(r['prepid'])

        l_type = locator()
        for (b, lines) in by_batch.items():
            text += "In batch %s:\n" % b
            text += '%sbatches?prepid=%s\n' % (l_type.baseurl(), b)
            for line in lines:
                text += line
            text += '\n'
        text += "\nAttention might be required\n"
        com = communicator()

        udb = Database('users')

        production_managers = udb.search({'role': 'production_manager'}, page=-1)
        gen_conveners = udb.search({'role': 'generator_convener'}, page=-1)
        people_list = production_managers + gen_conveners
        subject = "Gentle reminder of %d requests that appear stalled" % (reminded)
        if reminded != 0:
            com.sendMail(map(lambda u: u['email'], people_list) + [settings.get_value('service_account')], subject, text)


class RequestsReminder(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()
        self.representations = {'text/plain': self.output_text}

    def get(self, what=None, who=None):
        """
        Goes through all requests and send reminder to whom is concerned. /production_manager for things to be submitted. /generator_convener for things to be approved. /generator_contact for things to be looked at by /generator_contact/contact (if specified)
        """
        if what is not None:
            what = what.split(',')
            if 'all' in what:
                what = None
        if who is not None:
            who = who.split(',')

        udb = Database('users')
        rdb = Database('requests')
        crdb = Database('chained_requests')
        # a dictionary contact : { campaign : [ids] }
        ids_for_users = {}

        res = []
        # fill up the reminders
        def get_all_in_status(status, extracheck=None):
            campaigns_and_ids = {}
            for mcm_r in rdb.search({'status': status}, page=-1):
                # check whether it has a valid action before to add them in the reminder
                c = mcm_r['member_of_campaign']
                if c not in campaigns_and_ids:
                    campaigns_and_ids[c] = set()
                if extracheck is None or extracheck(mcm_r):
                    campaigns_and_ids[c].add(mcm_r['prepid'])

            # then remove the empty entries, and sort the others
            for c in campaigns_and_ids.keys():
                if not len(campaigns_and_ids[c]):
                    campaigns_and_ids.pop(c)
                else:
                    campaigns_and_ids[c] = sorted(campaigns_and_ids[c])

            return campaigns_and_ids

        com = communicator()
        l_type = locator()

        def count_entries(campaigns_and_ids):
            s = 0
            for (camp, ids) in campaigns_and_ids.items():
                s += len(ids)
            return s

        def prepare_text_for(campaigns_and_ids, status_for_link, username_for_link=None):
            message = ''
            for (camp, ids) in campaigns_and_ids.items():
                message += 'For campaign: %s \n' % camp
                if username_for_link:
                    message += '%srequests?page=-1&member_of_campaign=%s&status=%s&actor=%s \n' % (
                        l_type.baseurl(), camp, status_for_link, username_for_link)
                elif status_for_link:
                    message += '%srequests?page=-1&member_of_campaign=%s&status=%s \n' % (
                        l_type.baseurl(), camp, status_for_link)

                for rid in ids:
                    req = request(rdb.get(rid))
                    message += '\t%s (%s) (%d chains) (prio %s) \n' % (
                        rid,
                        req.get_attribute('dataset_name'),
                        len(req.get_attribute('member_of_chain')),
                        req.get_attribute('priority'))
                message += '\n'
            return message

        def is_in_chain(r):
            return len(r['member_of_chain']) != 0

        def streaming_function():
            if not what or 'production_manager' in what:
                # send the reminder to the production managers
                ids_for_production_managers = get_all_in_status('approved', extracheck=is_in_chain)
                for c in ids_for_production_managers:
                    res.extend(map(lambda i: {"results": True, "prepid": i}, ids_for_production_managers[c]))

                if len(ids_for_production_managers):
                    production_managers = udb.search({'role': 'production_manager'}, page=-1)
                    message = 'A few requests that needs to be submitted \n\n'
                    message += prepare_text_for(ids_for_production_managers, 'approved')
                    subject = 'Gentle reminder on %s requests to be submitted' % ( count_entries(ids_for_production_managers))
                    com.sendMail(map(lambda u: u['email'], production_managers) + [settings.get_value('service_account')], subject, message)

            if not what or 'gen_contact' in what or 'generator_contact' in what:
                all_ids = set()
                # remind the gen contact about requests that are:
                #   - in status new, and have been flown
                mcm_rs = []
                mcm_rs.extend(rdb.search({'status': 'validation'}, page=-1))
                for mcm_r in mcm_rs:
                    c = mcm_r['member_of_campaign']
                    request_id = mcm_r['prepid']
                    if 'flown_with' not in mcm_r:
                        continue  # just because in -dev it might be the case
                    # to get a remind only on request that are in a chain (including flown by construction)
                    if len(mcm_r['member_of_chain']) == 0:
                        continue
                    # to get a remind only on request that are being necessary to move forward : being the request being processed in at least a chain.
                    on_going = False
                    yield '.'
                    for in_chain in mcm_r['member_of_chain']:
                        mcm_chained_request = chained_request(crdb.get(in_chain))
                        try:
                            if mcm_chained_request.get_attribute('chain')[mcm_chained_request.get_attribute('step')] == request_id:
                                on_going = True
                                break
                        except Exception as e:
                            self.logger.error('Step not in chain: %s request: %s' % (mcm_chained_request.get_attribute('prepid'), request_id))
                            yield dumps(
                                {
                                    'error': 'step not in chain',
                                    'chain': mcm_chained_request.get_attribute('prepid'),
                                    'request': request_id},
                                indent=2)
                        time.sleep(0.5)  # we don't want to crash DB with a lot of single queries
                        yield '.'
                    if not on_going:
                        continue
                    try:
                        all_involved = request(mcm_r).get_actors()
                    except Exception:
                        yield dumps('request is not in db %s' % (mcm_r))
                    for contact in all_involved:
                        if contact not in ids_for_users:
                            ids_for_users[contact] = {}

                        if c not in ids_for_users[contact]:
                            ids_for_users[contact][c] = set()
                        ids_for_users[contact][c].add(request_id)
                        yield '.'

                # then remove the non generator
                gen_contacts = map(lambda u: u['username'], udb.search('search', {'role': 'generator_contact'}, page=-1))
                for contact in ids_for_users.keys():
                    if who and contact not in who:
                        ids_for_users.pop(contact)
                        continue
                    if contact not in gen_contacts:
                        # not a contact
                        ids_for_users.pop(contact)
                        continue
                    yield '.'
                    for c in ids_for_users[contact].keys():
                        if not len(ids_for_users[contact][c]):
                            ids_for_users[contact].pop(c)
                        else:
                            ids_for_users[contact][c] = sorted(ids_for_users[contact][c])
                        yield '.'
                        # for serialization only in dumps
                        # ids_for_users[contact][c] = list( ids_for_users[contact][c] )

                    # if there is nothing left. remove
                    if not len(ids_for_users[contact].keys()):
                        ids_for_users.pop(contact)
                        continue

                if len(ids_for_users):
                    for (contact, campaigns_and_ids) in ids_for_users.items():
                        for c in campaigns_and_ids:
                            all_ids.update(campaigns_and_ids[c])
                            yield dumps({'prepid': c}, indent=2)
                        mcm_u = udb.get(contact)
                        if len(campaigns_and_ids):
                            message = 'Few requests need your action \n\n'
                            message += prepare_text_for(campaigns_and_ids, '')
                            to_who = [settings.get_value('service_account')]
                            if l_type.isDev():
                                message += '\nto %s' % (mcm_u['email'])
                            else:
                                to_who.append(mcm_u['email'])
                            name = contact
                            if mcm_u['fullname']:
                                name = mcm_u['fullname']
                            subject = 'Gentle reminder on %s requests to be looked at by %s' % (count_entries(campaigns_and_ids), name)
                            com.sendMail(to_who, subject, message)
                            yield '.'

        return flask.Response(flask.stream_with_context(streaming_function()))


class UpdateMany(RequestRESTResource):
    def __init__(self):
        self.db_name = 'requests'
        RequestRESTResource.__init__(self)
        self.before_request()
        self.count_call()
        self.updateSingle = UpdateRequest()

    def put(self):
        """
        Updating an existing multiple requests with an updated dictionnary
        """
        return self.update_many(loads(flask.request.data.strip()))

    def update_many(self, data):
        list_of_prepids = data["prepids"]
        updated_values = data["updated_data"]
        return_info = []
        db = Database('requests')
        for elem in list_of_prepids:
            document = db.get(elem)
            for value in updated_values:
                if value in ('generator_parameters', 'sequences', 'keep_output', 'time_event', 'size_event', 'interested_pwg'):
                    document[value] = updated_values[value]
                elif isinstance(updated_values[value], list):
                    temp = updated_values[value]
                    temp.extend(document[value])
                    document[value] = list(set(temp))
                else:
                    document[value] = updated_values[value]
            try:
                return_info.append(self.updateSingle.update_request(dumps(document)))
            except Exception as e:
                return_info.append({"results": False, "message": str(e)})
        self.logger.info('updating requests: %s' % return_info)
        return {"results": return_info}


class ListRequestPrepids(RequestRESTResource):

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        """
        List all prepids for ticket editing page
        """
        args = flask.request.args.to_dict()
        limit = int(args.get('limit', 10))
        prepid = args.get('prepid', '').strip()
        campaign =args.get('campaign', '').strip()
        query = {}
        if prepid:
            query['prepid'] = '%s*' % (prepid)

        if campaign:
            query['member_of_campaign'] = campaign.split(',')

        if not query:
            return {'results': []}

        db = Database('requests')
        results = db.search(query, limit=limit, include_fields='prepid')
        self.logger.info(results)
        return {"results": [r['prepid'] for r in results]}


class GetUploadCommand(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()
        self.representations = {'text/plain': self.output_text}

    def get(self, request_id):
        """
        Get command used to upload configurations for given request.
        """
        db = Database('requests')
        if not db.document_exists(request_id):
            self.logger.error('GetUploadCommand: request with id {0} does not exist'.format(request_id))
            return {"results": False, 'message': 'Error: request with id {0} does not exist'.format(request_id)}
        req = request(db.get(request_id))

        return req.prepare_and_upload_config(execute=False)


class GetInjectCommand(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()
        self.representations = {'text/plain': self.output_text}

    def get(self, request_id):
        """
        Get command used to inject given request.
        """
        db = Database('requests')
        if not db.document_exists(request_id):
            self.logger.error('GetInjectCommand: request with id {0} does not exist'.format(request_id))
            return {"results": False, 'message': 'Error: request with id {0} does not exist'.format(request_id)}
        req = request(db.get(request_id))
        return RequestInjector(prepid=request_id).make_injection_command(req)


class GetUniqueValues(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, field_name):
        """
        Get unique values for navigation by field_name
        """
        args = flask.request.args.to_dict()
        db = Database('requests')
        return {'results': db.query_unique(field_name,
                                           args.get('key', ''),
                                           int(args.get('limit', 10)))}


class RequestsPriorityChange(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()
        self.requests_db = Database('requests')

    def post(self):
        fails = []
        try:
            requests = loads(flask.request.data.strip())
        except TypeError:
            return {"results": False, "message": "Couldn't read body of request"}
        for request_dict in requests:
            request_prepid = request_dict['prepid']
            mcm_request = request(self.requests_db.get(request_prepid))
            if 'priority_raw' in request_dict:
                new_priority = request_dict['priority_raw']
            else:
                new_priority = priority().priority(request_dict['priority'])

            if not mcm_request.change_priority(new_priority):
                message = 'Unable to set new priority in request %s' % request_prepid
                fails.append(message)
                self.logger.error(message)
        return {
            'results': True if len(fails) == 0 else False,
            'message': fails}


class Reserve_and_ApproveChain(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()
        self.cdb = Database("chained_requests")
        self.rdb = Database('requests')

    def get(self, chain_id):
        """
        Get chained_request object:
            1) reserve it to the end
            2) approve newly reserved requests
        """
        return self.reserve_and_approve(chain_id)

    def reserve_and_approve(self, chain_id):
        self.logger.debug("Trying to reverse and approve chain: %s" % (chain_id))
        creq = chained_request(self.cdb.get(chain_id))
        __current_step = creq.get_attribute("step")

        # Try to reserve needed chained_req to the end
        reserve_ret = creq.reserve(limit=True)
        if not reserve_ret["results"]:
            return reserve_ret

        try:
            return_list = []
            for re in creq.get_attribute("chain")[__current_step + 1:]:
                req = request(self.rdb.get(re))
                with locker.lock('{0}-wait-for-approval'.format(re)):
                    ret = req.approve()
                    save = self.rdb.save(req.json())
                    if not save:
                        return {"results": False,
                                "message": "Could not save request after approval"}

                return_list.append(ret)

            self.logger.debug("Approve returned: %s" % (return_list))
            return {"results": reserve_ret}

        except Exception as ex:
            self.logger.error("Failed to approve requests in ReserveAndApprove")
            return {"results": False,
                    "message": str(ex)}


class TaskChainRequestDict(RESTResource):
    """
    Provide the taskchain dictionnary for uploading to request manager
    """

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()
        self.representations = {'text/plain': self.output_text}

    def get(self, request_id):
        requests_db = Database('requests')
        mcm_request = request(requests_db.get(request_id))
        task_name = 'task_' + request_id
        request_type = mcm_request.get_wmagent_type()
        if request_type in ['MonteCarlo', 'LHEStepZero']:
            task_dicts = mcm_request.request_to_tasks(True, False)
        elif request_type in ['MonteCarloFromGEN', 'ReDigi']:
            task_dicts = mcm_request.request_to_tasks(False, False)

        wma = {
            "RequestType": "TaskChain",
            "Group": "ppd",
            "Requestor": "pdmvserv",
            "TaskChain": 0,
            "ProcessingVersion": 1,
            "RequestPriority": 0,
            # we default to 1 in multicore global
            "Multicore": 1}

        if not len(task_dicts):
            return dumps({})
        # Dict customization
        if mcm_request.get_attribute('priority') > wma['RequestPriority']:
            wma['RequestPriority'] = mcm_request.get_attribute('priority')

        if request_type in ['MonteCarloFromGEN', 'ReDigi']:
            wma['InputDataset'] = task_dicts[0]['InputDataset']

        task_counter = 1
        for task in task_dicts:
            if task.get('pilot_'):
                wma['SubRequestType'] = task['pilot_']

            for key in task.keys():
                if key.endswith('_'):
                    task.pop(key)
            wma['Task%d' % task_counter] = task
            task_counter += 1
        wma['TaskChain'] = task_counter - 1
        for item in ['CMSSWVersion', 'ScramArch', 'TimePerEvent', 'SizePerEvent', 'GlobalTag', 'Memory']:
            wma[item] = wma['Task%d' % wma['TaskChain']][item]
        wma['AcquisitionEra'] = wma['Task1']['AcquisitionEra']
        wma['ProcessingString'] = wma['Task1']['ProcessingString']
        wma['Campaign'] = wma['Task1']['Campaign']
        wma['PrepID'] = task_name
        wma['RequestString'] = wma['PrepID']
        return dumps(wma, indent=4)


class GENLogOutput(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_id):
        requests_db = Database('requests')
        mcm_request = request(requests_db.get(request_id))
        if not mcm_request:
            return {'results': False, 'message': 'Can\'t find request %s' % (request_id)}

        result = mcm_request.get_gen_script_output()
        code = 404 if 'Error getting checking script output' in result else 200
        return self.output_text(result, code, headers={'Content-Type': 'text/plain'})
