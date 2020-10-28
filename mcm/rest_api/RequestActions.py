#!/usr/bin/env python
import flask
import traceback
import time
import re
from json import dumps, loads
from collections import defaultdict

import tools.settings as settings
from couchdb_layer.mcm_database import database
from rest_api.RestAPIMethod import RESTResource
from rest_api.RequestPrepId import RequestPrepId
from json_layer.request import request
from json_layer.chained_request import chained_request
from json_layer.sequence import sequence
from json_layer.campaign import campaign
from json_layer.user import user
from tools.locator import locator
from tools.communicator import communicator
from tools.locker import locker
from tools.handlers import RequestInjector, submit_pool
from tools.user_management import access_rights
from tools.priority import priority
from flask_restful import reqparse


class RequestRESTResource(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.db_name = 'requests'
        self.with_trace = True

    def set_campaign(self, mcm_req):
        cdb = database('campaigns')
        # check that the campaign it belongs to exists
        camp = mcm_req.get_attribute('member_of_campaign')
        if not cdb.document_exists(camp):
            return None
            # get campaign
        camp = campaign(cdb.get(camp))
        mcm_req.set_attribute('energy', camp.get_attribute('energy'))
        if not mcm_req.get_attribute('cmssw_release'):
            mcm_req.set_options(can_save=False)

        return camp

    def import_request(self, data, db, label='created', step=None):

        if '_rev' in data:
            return {"results": False, 'message': 'could not save object with a revision number in the object'}

        try:
            # mcm_req = request(json_input=loads(data))
            mcm_req = request(json_input=data)
        except request.IllegalAttributeName as ex:
            return {"results": False, "message": str(ex)}
        camp = self.set_campaign(mcm_req)
        if not camp:
            return {"results": False, "message": 'Error: Campaign ' + mcm_req.get_attribute(
                'member_of_campaign') + ' does not exist.'}

        if camp.get_attribute('status') != 'started':
            return {"results": False, "message": "Cannot create a request in a campaign that is not started"}

        self.logger.info('Building new request...')

        # set '_id' and 'prepid' fields
        if mcm_req.get_attribute('_id'):
            mcm_req.set_attribute('prepid', mcm_req.get_attribute('_id'))
        elif mcm_req.get_attribute('prepid'):
            mcm_req.set_attribute('_id', mcm_req.get_attribute('prepid'))
        else:
            mcm_req.set_attribute('_id', '')
            mcm_req.set_attribute('prepid', '')

        # N.B (JR), '' is always an existing document
        existed = False
        if db.document_exists(mcm_req.get_attribute('_id')):
            existed = True
            self.logger.error('prepid %s already exists. Generating another...' % (mcm_req.get_attribute('_id')))

            prepid = RequestPrepId().next_prepid(mcm_req.get_attribute('pwg'),
                                                 mcm_req.get_attribute('member_of_campaign'))
            mcm_req = request(db.get(prepid))
            for key in data:
                if key not in ['prepid', '_id', 'history']:
                    mcm_req.set_attribute(key, data[key])

            if not mcm_req.get_attribute('prepid'):
                self.logger.error('prepid returned was None')
                return {"results": False, "message": "internal error and the request id is null"}

        self.logger.info('New prepid: %s' % (mcm_req.get_attribute('prepid')))

        number_of_sequences = len(camp.get_attribute('sequences'))
        if 'time_event' not in data:
            self.logger.info('No time_event in data, creating %s default values' % (number_of_sequences))
            mcm_req.set_attribute('time_event', [-1] * number_of_sequences)

        if 'size_event' not in data:
            self.logger.info('No size_event in data, creating %s default values' % (number_of_sequences))
            mcm_req.set_attribute('size_event', [-1] * number_of_sequences)


        member_of_campaign = mcm_req.get_attribute('member_of_campaign')
        all_ppd_tags = settings.get_value('ppd_tags')
        allowed_ppd_tags = set(all_ppd_tags.get('all',[])).union(set(all_ppd_tags.get(member_of_campaign,[])))
        for ppd_tag in mcm_req.get_attribute('ppd_tags'):
            if ppd_tag not in allowed_ppd_tags:
                self.logger.error('Illegal PPD Tag %s was found while importing %s' % (ppd_tag, mcm_req.get_attribute('prepid')))
                return {"results": False, "message": "PPD Tag %s is not allowed" % (ppd_tag)}

        # put a generator info by default in case of possible root request
        if camp.get_attribute('root') <= 0:
            mcm_req.update_generator_parameters()

        # cast the campaign parameters into the request: knowing that those can be edited at will later
        if not mcm_req.get_attribute('sequences'):
            mcm_req.set_options(can_save=False)

        # c = cdb.get(camp)
        # tobeDraggedInto = ['cmssw_release','pileup_dataset_name']
        # for item in tobeDraggedInto:
        #    mcm_req.set_attribute(item,c.get_attribute(item))
        # nSeq=len(c.get_attribute('sequences'))
        # mcm_req.

        # update history
        if self.with_trace:
            if step:
                mcm_req.update_history({'action': label, 'step': step})
            else:
                mcm_req.update_history({'action': label})

        # save to database or update if existed
        if not existed:
            interested_pwg = mcm_req.get_attribute('interested_pwg')
            pwg = mcm_req.get_attribute('pwg')
            if pwg not in interested_pwg:
                interested_pwg.append(pwg)
                mcm_req.set_attribute('interested_pwg', interested_pwg)

            if not db.save(mcm_req.json()):
                self.logger.error('Could not save results to database')
                return {"results": False}
        else:
            if not db.update(mcm_req.json()):
                self.logger.error('Could not update request in database')
                return {"results": False}
        return {"results": True, "prepid": mcm_req.get_attribute('_id')}


class CloneRequest(RequestRESTResource):

    #access_limit = access_rights.generator_contact ## maybe that is wrong

    def __init__(self):
        RequestRESTResource.__init__(self)
        self.before_request()
        self.count_call()

    def get(self, request_id):
        """
        Make a clone with no special requirement
        """
        return self.clone_request(request_id)

    def put(self):
        """
        Make a clone with specific requirements
        """
        data = loads(flask.request.data.strip())
        pid = data['prepid']
        return self.clone_request(pid, data)

    def clone_request(self, pid, data={}):
        db = database(self.db_name)
        cdb = database("campaigns")

        if db.document_exists(pid):
            new_json = db.get(pid)
            if new_json['flown_with']:
                return {"results": False, "message": "cannot clone a request that has been flown"}

            to_wipe = ['_id',
                       '_rev',
                       'prepid',
                       'approval',
                       'status',
                       'history',
                       'config_id',
                       'reqmgr_name',
                       'member_of_chain',
                       'validation',
                       'completed_events',
                       'version',
                       'priority',
                       'analysis_id',
                       'extension',
                       'output_dataset',
                       'tags',
                       'cmssw_release',
                       'sequences',
                       'keep_output']
            if 'member_of_campaign' in data and data['member_of_campaign'] != new_json['member_of_campaign']:
                # this is a cloning accross campaign: a few other things need to be cleanedup
                to_wipe.extend(['energy', 'ppd_tags'])

            old_validation_multiplier = new_json['validation'].get('time_multiplier', 1)
            new_json.update(data)
            # set the memory of new request to that of future member_of_campaign
            new_json['memory'] = cdb.get(new_json['member_of_campaign'])['memory']
            new_json['generator_parameters'] = new_json['generator_parameters'][-1:]
            new_json['generator_parameters'][0]['version'] = 0
            # remove some of the parameters to get then fresh from a new request.
            for w in to_wipe:
                del new_json[w]

            if old_validation_multiplier != 1:
                new_json['validation'] = {'time_multiplier': old_validation_multiplier}

            return self.import_request(new_json, db, label='clone', step=pid)
        else:
            return {"results": False, "message": "cannot clone an inexisting id %s" % pid}


class ImportRequest(RequestRESTResource):

    #access_limit = access_rights.generator_contact ## maybe that is wrong

    def __init__(self):
        RequestRESTResource.__init__(self)
        self.before_request()
        self.count_call()

    def put(self):
        """
        Saving a new request from a given dictionnary
        """
        db = database(self.db_name)
        return self.import_request(loads(flask.request.data.strip()), db)


class UpdateRequest(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)
        self.before_request()
        self.count_call()

    def put(self):
        """
        Updating an existing request with an updated dictionary
        """
        return self.update()

    def update(self):
        try:
            res = self.update_request(flask.request.data.strip())
            return res
        except Exception as e:
            # trace = traceback.format_exc()
            trace = str(e)
            self.logger.error('Failed to update a request from API \n%s' % (trace))
            return {'results': False, 'message': 'Failed to update a request from API %s' % trace}

    def update_request(self, data):
        data = loads(data)
        db = database(self.db_name)
        if '_rev' not in data:
            self.logger.error('Could not locate the CouchDB revision number in object: %s' % data)
            return {"results": False, 'message': 'could not locate revision number in the object'}

        if not db.document_exists(data['_id']):
            return {"results": False, 'message': 'request %s does not exist' % (data['_id'])}
        else:
            if db.get(data['_id'])['_rev'] != data['_rev']:
                return {"results": False, 'message': 'revision clash'}

        try:
            mcm_req = request(json_input=data)
        except request.IllegalAttributeName:
            return {"results": False, 'message': 'Mal-formatted request json in input'}

        if not mcm_req.get_attribute('prepid') and not mcm_req.get_attribute('_id'):
            self.logger.error('prepid returned was None')
            raise ValueError('Prepid returned was None')

        # operate a check on whether it can be changed
        previous_version = request(db.get(mcm_req.get_attribute('prepid')))
        editable = previous_version.get_editable()
        for (key, right) in editable.items():
            # does not need to inspect the ones that can be edited
            if right:
                if previous_version.get_attribute(key) != mcm_req.get_attribute(key):
                    self.logger.info('##UPDATING [%s] field## %s: %s vs %s' % (
                        mcm_req.get_attribute('prepid'), key,
                        previous_version.get_attribute(key),
                        mcm_req.get_attribute(key)))
                continue

            if key == 'sequences':
                # need a special treatment because it is a list of dicts
                continue
            if previous_version.get_attribute(key) != mcm_req.get_attribute(key):
                self.logger.error('Illegal change of parameter, %s: %s vs %s: %s' % (
                    key, previous_version.get_attribute(key), mcm_req.get_attribute(key), right))
                return {"results": False, 'message': 'Illegal change of parameter %s' % key}
                # raise ValueError('Illegal change of parameter')

        member_of_campaign = mcm_req.get_attribute('member_of_campaign')
        all_ppd_tags = settings.get_value('ppd_tags')
        allowed_ppd_tags = set(all_ppd_tags.get('all',[])).union(set(all_ppd_tags.get(member_of_campaign,[])))
        for ppd_tag in mcm_req.get_attribute('ppd_tags'):
            if ppd_tag not in allowed_ppd_tags:
                self.logger.error('Illegal PPD Tag %s was found while updating %s' % (ppd_tag, mcm_req.get_attribute('prepid')))
                return {"results": False, "message": "PPD Tag %s is not allowed" % (ppd_tag)}

        new_validation_multiplier = mcm_req.get_attribute('validation').get('time_multiplier', 1)
        old_validation_multiplier = previous_version.get_attribute('validation').get('time_multiplier', 1)
        if (new_validation_multiplier != old_validation_multiplier
            and new_validation_multiplier > 2
            and mcm_req.current_user_level < access_rights.generator_convener):
            return {"results": False, 'message': 'You need to be at least generator convener to set validation to >16h %s' % (mcm_req.current_user_level)}

        all_interested_pwg = set(settings.get_value('pwg'))
        req_interested_pwg = mcm_req.get_attribute('interested_pwg')
        for interested_pwg in req_interested_pwg:
            if interested_pwg not in all_interested_pwg:
                return {"results": False, 'message': '%s is not a valid PWG' % (interested_pwg)}

        dataset_name = mcm_req.get_attribute('dataset_name')
        dataset_name_regex = re.compile('.*[^0-9a-zA-Z_-].*')
        if dataset_name_regex.match(dataset_name):
            return {"results": False, 'message': 'Dataset name %s does not match required format' % (dataset_name)}

        requests_events_per_lumi = mcm_req.get_attribute('events_per_lumi')
        if requests_events_per_lumi != 0 and (requests_events_per_lumi < 100 or requests_events_per_lumi > 1000):
            return {"results": False, 'message': 'Events per lumi must be 100<=X<=1000 or 0 to use campaign\'s value'}

        self.logger.info('Updating request %s...' % (mcm_req.get_attribute('prepid')))

        # update history
        if self.with_trace:
            difference = self.get_obj_diff(previous_version.json(),
                                           mcm_req.json(),
                                           ('history', '_rev'))
            difference = ', '.join(difference)
            if difference:
                mcm_req.update_history({'action': 'update', 'step': difference})
            else:
                mcm_req.update_history({'action': 'update'})

        return {"results": db.update(mcm_req.json())}


class ManageRequest(UpdateRequest):
    """
    Same as UpdateRequest, leaving no trace in history, for admin only
    """

    access_limit = access_rights.administrator

    def __init__(self):
        UpdateRequest.__init__(self)
        self.with_trace = False
        self.before_request()
        self.count_call()

    def put(self):
        """
        Updating an existing request with an updated dictionnary, leaving no trace in history, for admin only
        """
        return self.update()


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
        db = database(self.db_name)
        return self.get_cmsDriver(db.get(prepid=request_id))

    def get_cmsDriver(self, data):
        try:
            mcm_req = request(json_input=data)
        except request.IllegalAttributeName:
            return {"results": ''}

        return {"results": mcm_req.build_cmsDrivers()}


class OptionResetForRequest(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.db_name = 'requests'
        self.before_request()
        self.count_call()

    def get(self, request_ids):
        """
        Reset the options for request
        """
        rdb = database(self.db_name)
        req_ids = request_ids.split(',')
        response = []
        for req_id in req_ids:
            req = request(rdb.get(req_id))
            if req.get_attribute('approval') != 'none' or req.get_attribute('status') != 'new':
                response.append({"results": False,
                                 "prepid": req_id,
                                 "message": "Cannot option reset %s because it\'s status is not none-new" % (req_id)})
                continue

            req.set_options()
            response.append({"results": True,
                             "prepid": req_id})

        if len(response) == 1:
            return response[0]
        else:
            return response


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
        # TO-DO: do we need it? We should keep it fow backward compatibility
        v = True if version else False

        db = database(self.db_name)
        res = self.get_fragment(db.get(prepid=request_id), v)
        return dumps(res) if isinstance(res, dict) else res

    def get_fragment(self, data, view):
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
        request_db = database(self.db_name)
        if request_db.document_exists(prepid):
            req = request(request_db.get(prepid))
            output_text = req.get_setup_file2(for_validation=for_validation, automatic_validation=automatic_validation, threads=1)
            return output_text
        else:
            return dumps({"results": False, "message": "%s does not exist" % prepid}, indent=4)


class DeleteRequest(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.db_name = 'requests'
        self.before_request()
        self.count_call()

    def delete(self, request_id):
        """
        Simply delete a request
        """
        return self.delete_request(request_id)

    def delete_request(self, pid):
        db = database(self.db_name)
        crdb = database('chained_requests')
        mcm_r = request(db.get(pid))

        self.logger.info(mcm_r.current_user_level)

        if len(mcm_r.get_attribute("member_of_chain")) != 0 and mcm_r.current_user_level < 3:
            # if request has a member_of_campaign we user role to be equal or more than
            # prod_manager, so we have to do check manually and return False
            return {
                "prepid": pid, "results": False,
                "message": "Only prod_managers and up can delete already chained requests"}

        if mcm_r.get_attribute('status') != 'new':
            return {
                "prepid": pid,
                "results": False,
                "message": "Not possible to delete a request (%s) in status %s" % (pid, mcm_r.get_attribute('status'))}
        if mcm_r.has_at_least_an_action():
            return {
                "prepid": pid,
                "results": False,
                "message": "Not possible to delete a request (%s) that is part of a valid chain" % (pid)}
        in_chains = mcm_r.get_attribute('member_of_chain')
        for in_chain in in_chains:
            mcm_cr = chained_request(crdb.get(in_chain))
            if mcm_cr.get_attribute('chain')[-1] != pid:
                # the pid is not the last of the chain
                return {
                    "prepid": pid,
                    "results": False,
                    "message": "Not possible to delete a request (%s) that is not at the end of an invalid chain (%s)" % (
                        pid, in_chain)}

            if mcm_cr.get_attribute('step') == mcm_cr.get_attribute('chain').index(pid):
                # we are currently processing that request
                return {
                    "prepid": pid,
                    "results": False,
                    "message": "Not possible to delete a request (%s) that is being the current step (%s) of an invalid chain (%s)" % (
                        pid, mcm_cr.get_attribute('step'), in_chain)}

            # found a chain that deserves the request to be pop-ep out from the end
            new_chain = mcm_cr.get_attribute('chain')
            new_chain.remove(pid)
            mcm_cr.set_attribute('chain', new_chain)
            mcm_cr.update_history({'action': 'remove request', 'step': pid})
            mcm_cr.reload()

        # delete chained requests !
        # self.delete_chained_requests(self,pid):
        return {"prepid": pid, "results": db.delete(pid)}

    def delete_chained_requests(self, pid):
        crdb = database('chained_requests')
        __query = crdb.construct_lucene_query({'contains': pid})
        mcm_crs = crdb.full_text_search('search', __query, page=-1)
        for doc in mcm_crs:
            crdb.delete(doc['prepid'])


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
        rdb = database('requests')
        __query = rdb.construct_lucene_query({'produce': datasetname})
        r = rdb.full_text_search('search', __query, page=-1)

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
        rdb = database('requests')

        if is_chain == 'chain':
            collect = []
            crdb = database('chained_requests')
            __query = crdb.construct_lucene_query({'contains': prepid})
            for cr in crdb.full_text_search('search', __query, page=-1):
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


class GetRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.before_request()
        self.count_call()

    def get(self, request_id):
        """
        Retreive the dictionnary for a given request
        """
        return self.get_request(request_id)

    def get_request(self, data):
        db = database(self.db_name)
        if not db.document_exists(data):
            return {"results": {}}
        mcm_r = db.get(prepid=data)
        # cast the sequence for schema evolution !!! here or not ?
        for (i_s, s) in enumerate(mcm_r['sequences']):
            mcm_r['sequences'][i_s] = sequence(s).json()

        mcm_r['generator_parameters'] = [g for g in mcm_r['generator_parameters'] if g]
        return {"results": mcm_r}


class ApproveRequest(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_id=None, step=-1):
        """
        Approve to the next step, or specified index the given request or coma separated list of requests
        """
        if request_id is None:
            return {'results': False, 'message': 'No prepid was given'}

        return self.multiple_approve(request_id, step)

    def post(self, request_id=None, step=-1):
        """
        Approve to next step. Ignore GET parameter, use list of prepids from POST data
        """
        return self.multiple_approve(flask.request.data.decode('utf-8'))

    def multiple_approve(self, rid, val=-1, hard=True):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.approve(r, val, hard))
            return res
        else:
            return self.approve(rid, val, hard)

    def approve(self, rid, val=-1, hard=True):
        _res = ""
        db = database('requests')
        if not db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given request id does not exist.'}
        req = request(json_input=db.get(rid))

        self.logger.info('Approving request %s for step "%s"' % (rid, val))
        if req.get_attribute('approval') == 'define' and req.get_attribute('status') == 'defined' and val == -1:
            username = self.user_dict.get('username', '')
            role = self.user_dict.get('role', 'user')
            allowed_to_approve = settings.get_value('allowed_to_approve')
            if role not in set(['administrator', 'generator_convener']) and username not in allowed_to_approve:
                self.logger.warning('%s (%s) was stopped from approving %s' % (username, role, rid))
                return {'prepid': rid, 'results': False, 'message': 'You are not allowed to approve requests'}
            else:
                self.logger.warning('%s (%s) was allowed to approve %s' % (username, role, rid))


        # req.approve(val)
        try:
            if val == 0:
                req.reset(hard)
                saved = db.update(req.json())
            else:
                with locker.lock('{0}-wait-for-approval'.format(rid)):
                    _res = req.approve(val)
                    saved = db.update(req.json())

        except request.WrongApprovalSequence as ex:
            return {'prepid': rid, 'results': False, 'message': str(ex)}
        except request.WrongStatusSequence as ex:
            return {"prepid": rid, "results": False, 'message': str(ex)}
        except request.IllegalApprovalStep as ex:
            return {"prepid": rid, "results": False, 'message': str(ex)}
        except request.BadParameterValue as ex:
            return {"prepid": rid, "results": False, 'message': str(ex)}
        except Exception:
            trace = traceback.format_exc()
            self.logger.error("Exception caught in approval\n%s" % (trace))
            return {'prepid': rid, 'results': False, 'message': trace}
        if saved:
            if _res:
                return {'prepid': rid, 'approval': req.get_attribute('approval'), 'results': False, 'message': _res["message"]}
            else:
                return {'prepid': rid, 'approval': req.get_attribute('approval'), 'results': True}
        else:
            return {'prepid': rid, 'results': False, 'message': 'Could not save the request after approval'}


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

        db = database('requests')
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
        Get the status and approval of given prepid
        """
        return self.status(prepid)

    def status(self, rid):
        if rid == "":
            return {"results": "You shouldnt be looking for empty prepid"}

        db = database('requests')
        if not db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given request id does not exist.'}

        mcm_r = db.get(rid)
        return {rid: '%s-%s' % (mcm_r['approval'], mcm_r['status'])}


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
        db = database('requests')
        crdb = database('chained_requests')
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

        rdb = database('requests')
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

        rdb = database('requests')
        __query = rdb.construct_lucene_query({"reqmgr_name": wf_id})
        # include only prepids for us
        res = rdb.full_text_search("search", __query, page=-1, include_fields='prepid')
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
        db = database('requests')
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


class TestRequest(RESTResource):
    # a rest api to make a creation test of a request
    def __init__(self):
        self.counter = 0
        self.before_request()
        self.count_call()

    def get(self, request_id):
        """
        this is test for admins only
        """
        rdb = database('requests')

        mcm_r = request(rdb.get(request_id))

        outs = mcm_r.get_outputs()

        return outs


class InjectRequest(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        # set user access to administrator
        self.db_name = 'requests'
        self.before_request()
        self.count_call()

    def get(self, request_ids):
        """
        Perform the thread preparation, injection of a request, or coma separated list of requests.
        """
        ids = request_ids.split(',')
        res = []
        for r_id in ids:
            self.logger.info('Forking the injection of request {0} '.format(r_id))
            _q_lock = locker.thread_lock(r_id)
            if not locker.thread_acquire(r_id, blocking=False):
                res.append({"prepid": r_id, "results": False,
                        "message": "The request {0} request is being handled already".format(r_id)})
                continue

            _submit = RequestInjector(prepid=r_id, lock=locker.lock(r_id), queue_lock=_q_lock)
            submit_pool.add_task(_submit.internal_run)
            res.append({"prepid": r_id, "results": True,
                        "message": "The request {0} will be forked unless same request is being handled already".format(r_id)})

        return res


class GetEditable(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.before_request()
        self.count_call()

    def get(self, request_id):
        """
        Retreive the fields that are currently editable for a given request id
        """
        return self.get_editable(request_id)

    def get_editable(self, prepid):
        db = database(self.db_name)
        request_in_db = request(db.get(prepid=prepid))
        editable = request_in_db.get_editable()
        return {"results": editable}


class GetDefaultGenParams(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.before_request()
        self.count_call()

    def get(self, request_id):
        """
        Simply get the schema for the generator parameters object in request.
        """
        return self.get_default_params(request_id)

    def get_default_params(self, prepid):
        db = database(self.db_name)
        request_in_db = request(db.get(prepid=prepid))
        request_in_db.update_generator_parameters()
        return {"results": request_in_db.get_attribute('generator_parameters')[-1]}


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
        rdb = database('requests')

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
        rdb = database('requests')
        udb = database('users')
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
        rdb = database('requests')
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
        all_campaigns = map(lambda x: x['id'], cdb.query_view("prepid"))
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
        cdb = database('campaigns')

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
            __query3 = odb.construct_lucene_query({'member_of_campaign': possible_campaign})
            all_requests = odb.full_text_search('search', __query3, page=-1)
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
        rdb = database('requests')
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
        rdb = database('requests')
        bdb = database('batches')
        statsDB = database('requests', url='http://vocms074.cern.ch:5984/')
        __query = rdb.construct_lucene_query({'status': 'submitted'})
        today = time.mktime(time.gmtime())
        text = "The following requests appear to be not progressing since %s days or will require more than %s days to complete and are below %4.1f%% completed :\n\n" % (time_since, time_remaining, below_completed)
        reminded = 0
        by_batch = defaultdict(list)
        request_prepids = []
        page = 0
        rs = [{}]
        while len(rs) > 0:
            rs = rdb.full_text_search('search', __query, page=page, limit=100)
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
                    __query2 = bdb.construct_lucene_complex_query([
                        ('contains', {'value': r['prepid']}),
                        ('status', {'value': ['announced', 'hold']})])
                    bs = bdb.full_text_search('search', __query2, page=-1)
                    # take the last one ?
                    in_batch = 'NoBatch'
                    if len(bs):
                        in_batch = bs[-1]['prepid']
                    wma_status = 'not-found'
                    if len(r['reqmgr_name']):
                        wma_name = r['reqmgr_name'][-1]['name']
                        stats = statsDB.get(wma_name)
                        if 'pdmv_status_from_reqmngr' in stats:
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

        udb = database('users')
        __query4 = udb.construct_lucene_query({'role': 'production_manager'})
        __query5 = udb.construct_lucene_query({'role': 'generator_convener'})

        production_managers = udb.full_text_search('search', __query4, page=-1)
        gen_conveners = udb.full_text_search('search', __query5, page=-1)
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

        udb = database('users')
        rdb = database('requests')
        crdb = database('chained_requests')
        # a dictionary contact : { campaign : [ids] }
        ids_for_users = {}

        res = []
        # fill up the reminders
        def get_all_in_status(status, extracheck=None):
            campaigns_and_ids = {}
            __query = rdb.construct_lucene_query({'status': status})
            for mcm_r in rdb.full_text_search('search', __query, page=-1):
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
                    __query2 = udb.construct_lucene_query({'role': 'production_manager'})
                    production_managers = udb.full_text_search('search', __query2, page=-1)
                    message = 'A few requests that needs to be submitted \n\n'
                    message += prepare_text_for(ids_for_production_managers, 'approved')
                    subject = 'Gentle reminder on %s requests to be submitted' % ( count_entries(ids_for_production_managers))
                    com.sendMail(map(lambda u: u['email'], production_managers) + [settings.get_value('service_account')], subject, message)

            if not what or 'gen_conveners' in what or 'generator_convener' in what:
                # send the reminder to generator conveners
                ids_for_gen_conveners = get_all_in_status('defined')
                for c in ids_for_gen_conveners:
                    res.extend(map(lambda i: {"results": True, "prepid": i}, ids_for_gen_conveners[c]))
                if len(ids_for_gen_conveners):
                    __query3 = udb.construct_lucene_query({'role': 'generator_convener'})
                    gen_conveners = udb.full_text_search('search', __query3, page=-1)
                    message = 'A few requests need your approvals \n\n'
                    message += prepare_text_for(ids_for_gen_conveners, 'defined')
                    subject = 'Gentle reminder on %s requests to be approved by you' % (count_entries(ids_for_gen_conveners))
                    com.sendMail(map(lambda u: u['email'], gen_conveners) + [settings.get_value('service_account')], subject, message)

            if not what or 'gen_contact' in what or 'generator_contact' in what:
                all_ids = set()
                # remind the gen contact about requests that are:
                #   - in status new, and have been flown
                # __query4 = rdb.construct_lucene_query({'status' : 'new'})
                __query5 = rdb.construct_lucene_query({'status': 'validation'})
                # mcm_rs = rdb.full_text_search('search', __query4, page=-1)
                mcm_rs = []
                mcm_rs.extend(rdb.full_text_search('search', __query5, page=-1))
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
                __query6 = udb.construct_lucene_query({'role': 'generator_contact'})
                gen_contacts = map(lambda u: u['username'], udb.full_text_search('search', __query6, page=-1))
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
        db = database(self.db_name)
        for elem in list_of_prepids:
            document = db.get(elem)
            for value in updated_values:
                if value in ['generator_parameters', 'sequences', 'keep_output']:
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
        RequestRESTResource.__init__(self)
        self.before_request()
        self.count_call()
        self.db_name = 'requests'
        self.db = database('requests')
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('requestPrepId', type=str, default='*')
        self.parser.add_argument('memberOfCampaign', type=str, default='*')
        self.parser.add_argument('limit', type=int, default=10)

    def get(self):
        """
        List all prepids by given options
        """
        return self.get_prepids()

    def get_prepids(self):
        kwargs = self.parser.parse_args()
        prepid = '*' if kwargs['requestPrepId'] == '*' else kwargs['requestPrepId'] + '*'
        member_of_campaign = '*' if kwargs['memberOfCampaign'] == '*' else kwargs['memberOfCampaign'] + '*'
        request_db = database('requests')
        __query = request_db.construct_lucene_query(
            {
                'prepid': prepid,
                'member_of_campaign': member_of_campaign})
        query_result = request_db.full_text_search("search", __query, page=0, limit=kwargs['limit'], include_fields='prepid')
        self.logger.info('Searching requests id with options: %s' % (kwargs))
        results = [record['prepid'] for record in query_result]
        return {"results": results}


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
        db = database("requests")
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
        db = database("requests")
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
        return self.get_unique_values(field_name)

    def get_unique_values(self, field_name):
        kwargs = flask.request.args.to_dict()
        db = database('requests')
        if 'limit' in kwargs:
            kwargs['limit'] = int(kwargs['limit'])
        kwargs['group'] = True
        return db.query_view_uniques(view_name=field_name, options=kwargs)


class PutToForceComplete(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Put a request to a force complete list
        """
        data = loads(flask.request.data.strip())
        pid = data['prepid']

        reqDB = database('requests')
        lists_db = database('lists')
        udb = database('users')
        self.logger.info('Will try to add to forcecomplete a request: %s' % (pid))
        req = request(reqDB.get(pid))
        curr_user = user(udb.get(req.current_user))
        forcecomplete_list = lists_db.get('list_of_forcecomplete')

        # do some checks
        if req.get_attribute('status') != 'submitted':
            self.logger.info('%s is not submitted for forcecompletion' % (pid))
            message = 'Cannot add a request which is not submitted'
            return {"prepid": pid, "results": False, 'message': message}

        # we want users to close only theirs PWGs
        if not req.get_attribute("pwg") in curr_user.get_pwgs():
            self.logger.info("User's PWG:%s is doesnt have requests PWG:%s" % (
                curr_user.get_pwgs(), req.get_attribute("pwg")))

            message = "User's PWG:%s is doesnt have requests PWG:%s" % (
                ",".join(curr_user.get_pwgs()), req.get_attribute("pwg"))

            return {"prepid": pid, "results": False, 'message': message}
        # check if request if at least 50% complete
        if req.get_attribute("completed_events") < req.get_attribute("total_events") * 0.5 and curr_user.get_attribute('role') != 'administrator':
            self.logger.info('%s is below 50percent completion' % (pid))
            message = 'Request is below 50 percent completion'
            return {"prepid": pid, "results": False, 'message': message}

        if pid in forcecomplete_list['value']:
            self.logger.info('%s already in forcecompletion' % (pid))
            message = 'Request already in forcecomplete list'
            return {"prepid": pid, "results": False, 'message': message}

        forcecomplete_list['value'].append(pid)
        ret = lists_db.update(forcecomplete_list)

        # lets see if we succeeded in saving it to settings DB
        if ret:
            req.update_history({'action': 'forcecomplete'})
            reqDB.save(req.json())
        else:
            self.logger.error('%s failed to save forcecomplete in settings DB' % (pid))
            message = 'Failed to save forcecomplete to DB'
            return {"prepid": pid, "results": False, 'message': message}

        return {"prepid": pid, "results": True,
                'message': 'Successfully added request to force complete list'}


class ForceCompleteMethods(RESTResource):

    access_limit = access_rights.generator_contact

    def __init__(self):
        self.access_user = settings.get_value('allowed_to_acknowledge')
        self.before_request()
        self.count_call()
        self.representations = {'text/plain': self.output_text}

    def get(self):
        """
        Get a list of workflows for force complete
        """
        lists_db = database('lists')
        forcecomplete_list = lists_db.get('list_of_forcecomplete')
        return dumps(forcecomplete_list['value'], indent=4)


class RequestsPriorityChange(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()
        self.requests_db = database("requests")

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
        self.cdb = database("chained_requests")
        self.rdb = database("requests")

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
        requests_db = database('requests')
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
            if mcm_request.get_attribute('block_white_list'):
                wma['BlockWhitelist'] = '"' + ','.join(mcm_request.get_attribute('block_white_list')) + '"'
            if mcm_request.get_attribute('block_black_list'):
                wma['BlockWhitelist'] = '"' + ','.join(mcm_request.get_attribute('block_black_list')) + '"'

        task_counter = 1
        for task in task_dicts:
            if task.get('pilot_'):
                wma['SubRequestType'] = task['pilot_']

            for key in list(task.keys()):
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


class PPDTags(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_id):
        requests_db = database('requests')
        mcm_request = request(requests_db.get(request_id))
        if not mcm_request:
            return {'results': False, 'message': 'Can\'t find request %s' % (request_id)}

        campaign = mcm_request.get_attribute('member_of_campaign')
        ppd_tags = settings.get_value('ppd_tags')
        tags = set(ppd_tags.get('all',[])).union(set(ppd_tags.get(campaign,[])))
        return {'results': sorted(list(tags)),
                'message': '%s tags found' % (len(tags))}


class GENLogOutput(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, request_id):
        requests_db = database('requests')
        mcm_request = request(requests_db.get(request_id))
        if not mcm_request:
            return {'results': False, 'message': 'Can\'t find request %s' % (request_id)}

        result = mcm_request.get_gen_script_output()
        code = 404 if 'Error getting checking script output' in result else 200
        return self.output_text(result, code, headers={'Content-Type': 'text/plain'})
