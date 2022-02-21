import flask
import traceback
import time

from flask.globals import request
from collections import defaultdict

from couchdb_layer.mcm_database import database as Database
from rest_api.RestAPIMethod import DeleteRESTResource, GetEditableRESTResource, GetRESTResource, GetUniqueValuesRESTResource, RESTResource, UpdateRESTResource
from json_layer.request import Request
from json_layer.campaign import Campaign
from json_layer.user import Role, User
from json_layer.chained_request import ChainedRequest
from tools.exceptions import InvalidActionException, NotFoundException
from tools.locator import locator
from tools.locker import locker
from tools.handlers import RequestInjector
from tools.utils import clean_split, expand_range


class RequestImport(RESTResource):

    @RESTResource.ensure_role(Role.MC_CONTACT)
    @RESTResource.request_with_json
    def put(self, data):
        """
        Saving a new request from a given dictionnary
        """
        data = {'pwg': data['pwg'],
                'member_of_campaign': data['member_of_campaign']}
        return self.import_request(data)

    def import_request(self, request_json, cloned_from=None):
        campaign_name = request_json['member_of_campaign']
        campaign = Campaign.fetch(campaign_name)
        if not campaign:
            return {"results": False,
                    "message": 'Campaign %s could not be found' % (campaign_name)}

        if campaign.get('status') != 'started':
            return {"results": False,
                    "message": "Cannot create a request in a campaign that is not started"
                               "%s is %s" % (campaign_name, campaign.get('status'))}

        pwg = request_json['pwg']
        self.logger.info('Building new request for %s in %s', pwg, campaign_name)
        request = Request(request_json)
        request.reset_options()
        request.validate()
        # Register a new prepid
        from rest_api.RequestFactory import RequestFactory
        request = RequestFactory.make(request.json())
        prepid = request.get('prepid')
        request.set_attribute('history', [])
        if cloned_from:
            request.update_history('clone', cloned_from)
        else:
            request.update_history('created')

        # Add PWG as interested one
        if pwg not in request.get_attribute('interested_pwg'):
            request.set_attribute('interested_pwg', request.get_attribute('interested_pwg') + [pwg])

        if not request.save():
            return {'results': False,
                    'messagge': 'Could not save request %s to the database' % (prepid),
                    'prepid': prepid}

        return {'results': True,
                'prepid': prepid}


class RequestClone(RequestImport):

    @RESTResource.ensure_role(Role.MC_CONTACT)
    @RESTResource.request_with_json
    def put(self, data):
        """
        Make a clone with specific requirements
        """
        prepid = data.get('prepid', '')
        if not prepid:
            return {'results': False,
                    'message': 'Missing prepid'}

        pwg = data.get('pwg', '')
        if not prepid:
            return {'results': False,
                    'message': 'Missing PWG'}

        new_campaign = data.get('member_of_campaign', '')
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


class UpdateRequest(UpdateRESTResource):
    """
    Endpoint for updating a request
    """

    @RESTResource.ensure_role(Role.USER)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Update a request with the provided content
        Required attributes - prepid and revision
        """
        return self.update_object(data, Request)

    def before_update(self, old_obj, new_obj):
        # Special check for validation multiplier
        new_multiplier = old_obj.get('validation').get('time_multiplier', 1)
        old_multiplier = new_obj.get('validation').get('time_multiplier', 1)
        if new_multiplier != old_multiplier and new_multiplier > 2:
            if User().get_role() < Role.PRODUCTION_MANAGER:
                raise InvalidActionException('Only production managers can set validation to >16h')


class RequestDelete(DeleteRESTResource):

    @RESTResource.ensure_role(Role.MC_CONTACT)
    def delete(self, prepid):
        """
        Delete a campaign
        """
        return self.delete_object(prepid, Request)

    def delete_check(self, obj):
        approval_status = obj.get_approval_status()
        if approval_status != 'none-new':
            raise InvalidActionException(f'Cannot delete "{approval_status}", must be "none-new"')

        chained_request_ids = obj.get('member_of_chain')
        if chained_request_ids:
            # If request is a member of chain, only prod managers can delete it
            if User().get_role() < Role.PRODUCTION_MANAGER:
                raise InvalidActionException('Only production managers can delete request '
                                             'that is a member of a chained request')

        prepid = obj.get('prepid')
        chained_request_db = ChainedRequest.get_database()
        chained_requests = chained_request_db.bulk_get(chained_request_ids)
        for chained_request in chained_requests:
            if not chained_request:
                # Don't care about this in deletion
                continue

            chain = chained_request['chain']
            if prepid not in chain:
                # Don't care about this in deletion
                continue

            chained_request_id = chained_request['prepid']
            if chained_request.get('enabled'):
                # All chains must be disabled
                raise InvalidActionException(f'Member of enabled chained request {chained_request_id}')

            if prepid != chain[-1]:
                # Must be last request in chain
                raise InvalidActionException(f'Must be the last request in {chained_request_id}')

            if chained_request['step'] >= chain.index(prepid):
                # Request is the current step in the chain
                raise InvalidActionException(f'{chained_request_id} step is at or after {prepid}')

    def before_delete(self, obj):
        prepid = obj.get('prepid')
        chained_request_db = ChainedRequest.get_database()
        chained_requests = chained_request_db.bulk_get(obj.get('member_of_chain'))
        for chained_request_dict in chained_requests:
            if not chained_request_dict:
                # Don't care about this in deletion
                continue

            chain = chained_request_dict['chain']
            if prepid not in chain:
                # Don't care about this in deletion
                continue

            chained_request_id = chained_request_dict['prepid']
            if prepid == chain[0]:
                # Request is root - delete it together with the chained request
                chained_request_db.delete(chained_request_id)
            else:
                # Request is not root - just pop it off the chained request
                chained_request = ChainedRequest(chained_request_dict)
                chain.remove(prepid)
                chained_request.update_history('remove request', prepid)
                chained_request.reload()

        return super().before_delete(obj)


class GetRequest(GetRESTResource):
    """
    Endpoing for retrieving a request
    """
    object_class = Request


class GetEditableRequest(GetEditableRESTResource):
    """
    Endpoing for retrieving a request and it's editing info
    """
    object_class = Request


class GetUniqueRequestValues(GetUniqueValuesRESTResource):
    """
    Endpoint for getting unique values of request attributes
    """
    object_class = Request


class RequestOptionReset(RESTResource):

    @RESTResource.ensure_role(Role.MC_CONTACT)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Reset the options for request
        """
        def reset_options(request):
            if request.get_approval_status() != 'none-new':
                raise Exception('%s it is not none-new' % (request.get('prepid')))

            request.reset_options()

        return self.do_multiple_items(data['prepid'], Request, reset_options)


class RequestNextStatus(RESTResource):

    @RESTResource.ensure_role(Role.MC_CONTACT)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Move request to the next status
        """
        def next_status(request):
            request.approve()

        return self.do_multiple_items(data['prepid'], Request, next_status)


class RequestReset(RESTResource):

    @RESTResource.ensure_role(Role.MC_CONTACT)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Reset request to it's initial state
        """
        def reset_request(request):
            request.reset(soft=False)

        return self.do_multiple_items(data['prepid'], Request, reset_request)


class RequestSoftReset(RESTResource):

    @RESTResource.ensure_role(Role.MC_CONTACT)
    @RESTResource.request_with_json
    def post(self, data):
        """
        Reset request to previous state
        """
        def reset_request(request):
            request.reset(soft=True)

        return self.do_multiple_items(data['prepid'], Request, reset_request)


class GetCmsDriverForRequest(RESTResource):
    """
    Endpoing for getting cmsDriver commands of a request
    """

    def get(self, prepid):
        """
        Retrieve the dictionary of cmsDriver commands of a request
        """
        request = Request.fetch(prepid)
        if not request:
            raise NotFoundException(prepid)

        return {'results': request.get_cmsdrivers()}


class GetFragmentForRequest(RESTResource):
    """
    Endpoint for getting fragment of a request
    """

    def get(self, prepid):
        """
        Retrieve the fragment as stored for a given request
        """
        request = Request.fetch(prepid)
        if not request:
            raise NotFoundException(prepid)

        fragment = request.get('fragment')
        return self.build_response(data=fragment, content_type='text/plain')


class GetSetupFileForRequest(RESTResource):

    def get(self, prepid):
        """
        Retrieve the script necessary to setup and submit a given request
        """
        request = Request.fetch(prepid)
        return self.build_response(data=request.get_setup_file(True, False, False),
                                   content_type='text/plain')


class GetTestFileForRequest(RESTResource):

    def get(self, prepid):
        """
        Retrieve the script necessary to setup and submit a given request
        """
        request = Request.fetch(prepid)
        return self.build_response(data=request.get_setup_file(False, True, False),
                                   content_type='text/plain')


class GetValidationFileForRequest(RESTResource):

    def get(self, prepid):
        """
        Retrieve the script necessary to setup and submit a given request
        """
        request = Request.fetch(prepid)
        return self.build_response(data=request.get_setup_file(False, False, True),
                                   content_type='text/plain')



class GetRequestByDataset(RESTResource):

    def get(self, dataset):
        """
        retrieve the dictionnary of a request, based on the output dataset specified
        """
        self.representations = {'text/plain': self.output_text}
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


class GetStatus(RESTResource):

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

    def get(self, prepid):
        """
        Get the status and approval of given prepid(s)
        """
        prepids = clean_split(prepid)
        if not prepids:
            return {'results': False,
                    'message': 'No prepids given'}

        request_db = Database('requests')
        results = [r for r in request_db.bulk_get(prepids) if r]
        return {r['prepid']: '%s-%s' % (r['approval'], r['status']) for r in results}


class InspectStatus(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
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

    @RESTResource.ensure_role(Role.PRODUCTION_EXPERT)
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

    @RESTResource.ensure_role(Role.PRODUCTION_EXPERT)
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

    @RESTResource.ensure_role(Role.ADMINISTRATOR)
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




class NotifyUser(RESTResource):

    @RESTResource.ensure_role(Role.USER)
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
            req.update_history('notify', message)
            if not rdb.save(req.json()):
                results.append({"prepid": pid, "results": False,
                        "message": "Could not save %s" % pid})

                return results

            results.append({"prepid": pid, "results": True, "message": "Notification send for %s" % pid})

        return results


class RegisterUser(RESTResource):

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

        request_in_db.update_history('register', current_user)
        rdb.save(request_in_db.json())
        return {"prepid": pid, "results": True, 'message': 'You (%s) are registered to %s' % (current_user, pid)}


class GetActors(RESTResource):

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

    @RESTResource.ensure_role(Role.USER)
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


class RequestsFromFile(RESTResource):

    @RESTResource.ensure_role(Role.USER)
    def put(self):
        """
        Parse the posted text document for request id and request ranges for
        display of requests
        """
        request_db = database('requests')
        self.logger.info('File was uploaded to listfromfile')
        data = loads(flask.request.data)
        lines = clean_split(data['contents'], '\n')
        ids = []
        for line in lines:
            split_line = clean_split(line, '->')
            if len(split_line) >= 2:
                ids.extend(expand_range(split_line[0], split_line[1]))
            else:
                ids.append(line)

        # Limit number of IDs to 999 not to go crazy with thousands of requests
        self.logger.info('Parsed %s ids', len(ids))
        ids = sorted(list(set(ids)))[:999]
        objects = [obj for obj in request_db.bulk_get(ids) if obj]
        self.logger.info('Fetched %s objects from %s ids', len(objects), len(ids))
        return {"results": objects}


class StalledReminder(RESTResource):

    @RESTResource.ensure_role(Role.ADMINISTRATOR)
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

    @RESTResource.ensure_role(Role.ADMINISTRATOR)
    def get(self, what=None, who=None):
        """
        Goes through all requests and send reminder to whom is concerned. /production_manager for things to be submitted. /generator_convener for things to be approved. /generator_contact for things to be looked at by /generator_contact/contact (if specified)
        """
        self.representations = {'text/plain': self.output_text}
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


class UpdateMany(RESTResource):

    def put(self):
        """
        Updating an existing multiple requests with an updated dictionnary
        """
        self.updateSingle = UpdateRequest()
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


class GetUploadCommand(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def get(self, request_id):
        """
        Get command used to upload configurations for given request.
        """
        self.representations = {'text/plain': self.output_text}
        db = Database('requests')
        if not db.document_exists(request_id):
            self.logger.error('GetUploadCommand: request with id {0} does not exist'.format(request_id))
            return {"results": False, 'message': 'Error: request with id {0} does not exist'.format(request_id)}
        req = request(db.get(request_id))

        return req.prepare_and_upload_config(execute=False)


class GetInjectCommand(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
    def get(self, request_id):
        """
        Get command used to inject given request.
        """
        self.representations = {'text/plain': self.output_text}
        db = Database('requests')
        if not db.document_exists(request_id):
            self.logger.error('GetInjectCommand: request with id {0} does not exist'.format(request_id))
            return {"results": False, 'message': 'Error: request with id {0} does not exist'.format(request_id)}
        req = request(db.get(request_id))
        return RequestInjector(prepid=request_id).make_injection_command(req)


class RequestsPriorityChange(RESTResource):

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
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

    @RESTResource.ensure_role(Role.PRODUCTION_MANAGER)
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

    @RESTResource.ensure_role(Role.USER)
    def get(self, request_id):
        requests_db = Database('requests')
        self.representations = {'text/plain': self.output_text}
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

    @RESTResource.ensure_role(Role.USER)
    def get(self, request_id):
        requests_db = Database('requests')
        mcm_request = request(requests_db.get(request_id))
        if not mcm_request:
            return {'results': False, 'message': 'Can\'t find request %s' % (request_id)}

        result = mcm_request.get_gen_script_output()
        code = 404 if 'Error getting checking script output' in result else 200
        return self.output_text(result, code, headers={'Content-Type': 'text/plain'})
