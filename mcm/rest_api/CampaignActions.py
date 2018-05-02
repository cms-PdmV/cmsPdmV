#!/usr/bin/env python

import flask
import time
import traceback

from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResource
from json_layer.campaign import campaign
from json_layer.request import request
from json_layer.sequence import sequence
from json_layer.chained_campaign import chained_campaign
from json_layer.notification import notification
from tools.user_management import access_rights
from simplejson import loads, dumps


class CreateCampaign(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Create a request with the provided json content
        """
        return self.create_campaign(flask.request.data)

    def create_campaign(self, data):
        db = database('campaigns')
        try:
            camp_mcm = campaign(json_input=loads(data))
        except campaign.IllegalAttributeName as ex:
            return {"results": False}

        if not camp_mcm.get_attribute('prepid'):
            self.logger.error('Invalid prepid: Prepid returned None')
            return {"results": False}

        if '_' in camp_mcm.get_attribute('prepid'):
            self.logger.error('Invalid campaign name %s' % (camp_mcm.get_attribute('prepid')))
            return {"results": False}

        camp_mcm.set_attribute('_id', camp_mcm.get_attribute('prepid'))

        camp_mcm.update_history({'action': 'created'})

        # this is to create, not to update
        if db.document_exists( camp_mcm.get_attribute('prepid') ):
            return {"results": False}

        # save to db
        if not db.save(camp_mcm.json()):
            self.logger.error('Could not save object to database')
            return {"results": False}

        # create dedicated chained campaign
        self.create_chained_campaign(camp_mcm.get_attribute('_id'), db)

        return {"results": True}

    # creates a chained campaign containing only the given campaign
    def create_chained_campaign(self, cid, db):
        if db.get(cid)['root'] < 1:
            cdb = database('chained_campaigns')
            dcc = chained_campaign({'prepid': 'chain_' + cid, '_id': 'chain_' + cid})
            dcc.add_campaign(cid)  # flow_name = None
            cdb.save(dcc.json())


class UpdateCampaign(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def put(self):
        """
        Update the content of a campaign data with the provided information
        """
        return self.update_campaign(loads(flask.request.data))

    def update_campaign(self, data):
        if '_rev' not in data:
            return {"results": False, 'message': 'There is no previous revision provided'}
        try:
            camp_mcm = campaign(json_input=data)
        except campaign.IllegalAttributeName:
            return {"results": False}

        if not camp_mcm.get_attribute('prepid') and not camp_mcm.get_attribute('_id'):
            raise ValueError('Prepid returned was None')

        # cast schema evolution of sequences
        sequences = camp_mcm.get_attribute('sequences')
        for steps in sequences:
            for label in steps:
                steps[label] = sequence(steps[label]).json()
        camp_mcm.set_attribute('sequences', sequences)

        # create dedicated chained campaign
        self.create_chained_campaign(camp_mcm.get_attribute('_id'), camp_mcm.get_attribute('root'))
        camp_mcm.update_history({'action': 'update'})
        return self.save_campaign(camp_mcm)

    def save_campaign(self, camp_mcm):
        db = database('campaigns')
        return {"results": db.update(camp_mcm.json())}

    # unfortunate duplicate
    # creates a chained campaign containing only the given campaign
    def create_chained_campaign(self, cid, root):
        if root < 1:
            cdb = database('chained_campaigns')
            dcc = chained_campaign({"prepid": 'chain_' + cid,
                                    "_id": 'chain_' + cid})
            dcc.add_campaign(cid)
            if not cdb.document_exists(dcc.get_attribute('prepid')):
                cdb.save(dcc.json())


class DeleteCampaign(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.db_name = 'campaigns'
        self.before_request()
        self.count_call()

    def delete(self, campaign_id):
        """
        Delete a campaign
        """
        return self.delete_request(campaign_id)

    def delete_request(self, cid):
        db = database(self.db_name)
        if not self.delete_all_requests(cid):
                return {"results": False}

        # delete all chained_campaigns and flows that have this campaign as a member
        self.resolve_dependencies(cid, db)
        return {"results": db.delete(cid)}

    def delete_all_requests(self, cid):
        rdb = database('requests')
        res = rdb.query('member_of_campaign==' + cid, page_num=-1)
        try:
                for req in res:
                        rdb.delete(req['prepid'])
                return True
        except Exception as ex:
                self.logger.error(str(ex))
                return False

    def resolve_dependencies(self, cid, db):
        if not db.document_exists(cid):
            return

        cdb = database('chained_campaigns')
        # update all campaigns
        chains = cdb.query('campaign==' + cid)
        # include the delete method
        if chains:
            try:
                from rest_api.ChainedCampaignActions import DeleteChainedCampaign
            except ImportError as ex:
                return {'results': str(ex)}

            # init deleter
            delr = DeleteChainedCampaign()

            for cc in chains:
                delr.delete_request(cc)

        # get all campaigns that contain cid in their next parameter
        allowed_campaigns = db.query('next==' + cid)

        # update all those campaigns
        for c in allowed_campaigns:
            c['next'].remove(cid)
            db.update(c)


class GetCampaign(RESTResource):
    def __init__(self):
        self.db_name = 'campaigns'
        self.before_request()
        self.count_call()

    def get(self, campaign_id):
        """
        Retrive the json content of a campaign attributes
        """
        return self.get_request(campaign_id)

    def get_request(self, data):
        db = database(self.db_name)
        return {"results": db.get(prepid=data)}


class ToggleCampaignStatus(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, campaign_id):
        """
        Move the campaign status to the next state
        """
        return self.toggle_campaign(campaign_id)

    def toggle_campaign(self, rid):
        db = database('campaigns')
        if not db.document_exists(rid):
            return {"results": 'Error: The given campaign id does not exist.'}
        camp = campaign(json_input=db.get(rid))
        try:
            camp.toggle_status()
            saved = db.update(camp.json())
            if saved:
                return {"results": True}
            else:
                return {"results": False, "message": "Could not save request"}

        except Exception as ex:
            return {"results": False, "message": str(ex)}


class ApproveCampaign(RESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, campaign_ids, index=-1):
        """
        Move campaign or provided list of campaigns ids to the next approval (/ids) or to the specified index (/ids/index)
        """
        return self.multiple_toggle(campaign_ids, index)

    def multiple_toggle(self, rid, val=-1):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.toggle_campaign(r, val))
            return res
        else:
            return self.toggle_campaign(rid, val)

    def toggle_campaign(self,  rid, index):
        db = database('campaigns')
        if not db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given campaign id does not exist.'}
        camp = campaign(json_input=db.get(rid))
        camp.approve(int(index))
        if int(index) == 0:
            camp.set_status(0)
        res = db.update(camp.json())
        return {"prepid": rid, "results": res, "approval": camp.get_attribute('approval')}


class GetCmsDriverForCampaign(RESTResource):
    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, campaign_id):
        """
        Retrieve the list of cmsDriver commands for a given campaign id
        """
        db = database('campaigns')
        return self.get_cmsDriver(db.get(prepid=campaign_id))

    def get_cmsDriver(self, data):
        try:
            camp_mcm = campaign(json_input=data)
        except campaign.IllegalAttributeName:
            return {"results": ''}

        return {"results": camp_mcm.build_cmsDrivers()}


class CampaignsRESTResource(RESTResource):

    def listAll(self):
        cdb = database('campaigns')
        all_campaigns = cdb.raw_query("prepid")
        prepids_list = map(lambda x: x['id'], all_campaigns)
        return prepids_list

    def multiple_inspect(self, cid, in_statuses=['submitted', 'approved']):
        clist = list(set(cid.rsplit(',')))
        res = []
        rdb = database('requests')
        index = 0
        self.logger.error("Chain inspect begin. Number of chains to be inspected: %s" % (len(clist)))
        try:
            while len(clist) > index:
                yield dumps({"current cr element": "%s/%s" % (index, len(clist))}, indent=2)
                query = rdb.construct_lucene_complex_query([
                    ('member_of_campaign', {'value': clist[index: index + 1]}),
                    ('status', {'value': in_statuses})
                ])
                ##do another loop over the requests themselves
                req_page = 0
                request_res = rdb.full_text_search('search', query, page=req_page)

                while len(request_res) > 0:
                    self.logger.info("inspecting single requests. page: %s" % (req_page))
                    for r in request_res:
                        self.logger.info("running inspect on request: %s" % (r['prepid']))
                        mcm_r = request(r)

                        if mcm_r:
                            #making it as a stream
                            yield dumps(mcm_r.inspect(), indent=4)
                        else:
                            #making it as a stream
                            yield dumps({"prepid": r, "results": False,
                                    'message': '%s does not exist' % (r)}, indent=4)

                    req_page += 1
                    request_res = rdb.full_text_search('search', query, page=req_page)
                    time.sleep(0.5)

                index += 1
                time.sleep(1)
        except Exception as e:
            subject = "Exception while inspecting request "
            message = "Request: %s \n %s traceback: \n %s" % (mcm_r.get_attribute('prepid'), str(e), traceback.format_exc())
            self.logger.error(subject + message)
            notification(
                subject,
                message,
                [],
                group=notification.REQUEST_OPERATIONS,
                action_objects=[mcm_r.get_attribute('prepid')],
                object_type='requests',
                base_object=mcm_r)
            mcm_r.notify(subject, message, accumulate=True)

        self.logger.info("Campaign inspection finished!")


class ListAllCampaigns(CampaignsRESTResource):
    def __init__(self):
        CampaignsRESTResource.__init__(self)
        self.before_request()
        self.count_call()

    def get(self):
        """
        Retrieve the list of all existing campaigns
        """
        return {"results": self.listAll()}


class InspectRequests(CampaignsRESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        CampaignsRESTResource.__init__(self)
        self.before_request()
        self.count_call()

    def get(self, campaign_id):
        """
        Inspect the campaign or coma separated list of campaigns for completed requests
        """
        return ["this api will be deprecated"]
        #return self.multiple_inspect(campaign_id)


class InspectCampaigns(CampaignsRESTResource):

    access_limit = access_rights.production_manager

    def __init__(self):
        CampaignsRESTResource.__init__(self)
        self.before_request()
        self.count_call()

    def get(self, group):
        """
        Inspect all the campaigns in McM for completed requests. Requires /all
        """
        if group != 'all':
            return {"results": 'Error: Incorrect argument provided'}
        c_list = self.listAll()
        # force pretify output in browser for multiple lines
        self.representations = {'text/plain': self.output_text}

        from random import shuffle
        shuffle(c_list)
        return flask.Response(flask.stream_with_context(self.multiple_inspect(','.join(c_list))))


class HoldCampaigns(CampaignsRESTResource):

    def __init__(self):
        CampaignsRESTResource.__init__(self)
        self.before_request()
        self.count_call()

    def form_response(self, data, code, headers=None):
        if type(data) == dict:
            data = dumps(data, indent=4)
            if headers is None:
                headers = {}

            headers['Content-type'] = 'application/json'

        return self.output_text(data, code, headers)

    def post(self):
        """
        Change campaign hold status. Content type 'application/json' must be set.
        Request is a JSON with 'prepid' and 'on_hold' (0/1) attributes.
        """
        data = flask.request.data
        try:
            data_json = loads(data)
            campaign_name = data_json['prepid']
            campaign_hold = int(data_json['on_hold'])
        except:
            return self.form_response({'error': 'Request must have \'prepid\' and \'on_hold\' attributes'}, code=400)

        if campaign_hold != 0 and campaign_hold != 1:
            return self.form_response({'error': 'campaign_hold must be (0/1) or (true/false)'}, code=400)

        db = database('campaigns')
        if not db.document_exists(campaign_name):
            return self.form_response({'error': 'Campaign %s is not found' % (campaign_name)}, code=404)

        camp = campaign(json_input=db.get(campaign_name))
        camp.set_attribute('on_hold', campaign_hold)
        result = db.update(camp.json())
        if result:
            return self.form_response({'result': 'success'}, code=200)
        else:
            return self.form_response({'result': 'failure'}, code=500)
