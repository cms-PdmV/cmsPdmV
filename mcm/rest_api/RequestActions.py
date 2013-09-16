#!/usr/bin/env python

import cherrypy
import sys
import traceback
import string
import time
from math import sqrt
from json import loads, dumps
from couchdb_layer.prep_database import database
from RestAPIMethod import RESTResource
from RequestPrepId import RequestPrepId
from json_layer.json_base import json_base
from json_layer.request import request
from json_layer.sequence import sequence
from json_layer.request import runtest_genvalid
from json_layer.action import action
from json_layer.campaign import campaign
from json_layer.generator_parameters import generator_parameters
from threading import Thread
from submitter.package_builder import package_builder
from tools.locator import locator
from tools.communicator import communicator
from tools.locker import locker


class RequestRESTResource(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.adb = database('actions')
        self.cdb = database('campaigns')
        self.request = None
        self.access_limit = 1
        self.with_trace = True

    def set_campaign(self):
        # check that the campaign it belongs to exsits
        camp = self.request.get_attribute('member_of_campaign')
        if not self.cdb.document_exists(camp):
            return False
            ## get campaign
        self.campaign = self.cdb.get(camp)
        self.request.set_attribute('energy', self.campaign['energy'])
        return True

    ## duplicate version to be centralized in a unique class
    def add_action(self, force=False):
        # Check to see if the request is a root request
        #camp = self.request.get_attribute('member_of_campaign')

        #if not self.cdb.document_exists(camp):
        #    return dumps({"results":'Error: Campaign '+str(camp)+' does not exist.'})

        # get campaign
        #self.c = self.cdb.get(camp)
        rootness = self.campaign['root']
        mcdbid = int(self.request.get_attribute('mcdb_id'))
        inputds = self.request.get_attribute('input_filename')
        if (not force) and ((rootness == 1 ) or (rootness == -1 and mcdbid > -1)):
            ## c['root'] == 1
            ##            :: not a possible root --> no action in the table
            ## c['root'] == -1 and mcdb > -1 
            ##            ::a possible root and mcdbid=0 (import from WMLHE) or mcdbid>0 (imported from PLHE) --> no action on the table
            if self.adb.document_exists(self.request.get_attribute('prepid')):
                ## check that there was no already inserted actions, and remove it in that case

                ##check that it empty !!!
                mcm_a = self.adb.get(self.request.get_attribute('prepid'))
                for (cc,c) in mcm_a['chains'].items():
                    if 'flag' in c and c['flag']:
                        raise Exception("The action item that corresponds to %s is set within %s"%( self.request.get_attribute('prepid'), cc))
                    if 'chains' in c:
                        for cr in c['chains']:
                            raise Exception("The action item that corresponds to %s has a chained request %s attached within %s"%(  self.request.get_attribute('prepid'), cr, cc))
                        
                self.adb.delete(self.request.get_attribute('prepid'))
            return

        # check to see if the action already exists
        if not self.adb.document_exists(self.request.get_attribute('prepid')):
            # add a new action
            #a= action('automatic')
            a = action()
            a.set_attribute('prepid', self.request.get_attribute('prepid'))
            a.set_attribute('_id', a.get_attribute('prepid'))
            a.set_attribute('dataset_name', self.request.get_attribute('dataset_name'))
            a.set_attribute('member_of_campaign', self.request.get_attribute('member_of_campaign'))
            a.find_chains()
            self.logger.log('Adding an action for %s' % (self.request.get_attribute('prepid')))
            self.adb.save(a.json())
        else:
            a = action(self.adb.get(self.request.get_attribute('prepid')))
            if a.get_attribute('dataset_name') != self.request.get_attribute('dataset_name'):
                a.set_attribute('dataset_name', self.request.get_attribute('dataset_name'))
                self.logger.log('Updating an action for %s' % (self.request.get_attribute('prepid')))
                self.adb.save(a.json())

    def import_request(self, data, label='created'):

        if '_rev' in data:
            return dumps({"results": False, 'message': 'could not save object with a revision number in the object'})

        try:
            #self.request = request(json_input=loads(data))
            self.request = request(json_input=data)
        except request.IllegalAttributeName as ex:
            return dumps({"results": False, "message": str(ex)})

        if not self.set_campaign():
            return dumps({"results": False, "message": 'Error: Campaign ' + self.request.get_attribute(
                'member_of_campaign') + ' does not exist.'})

        if self.campaign['status'] != 'started':
            return dumps({"results": False, "message": "Cannot create a request in a campaign that is not started"})

        self.logger.log('Building new request...')

        # set '_id' and 'prepid' fields
        if self.request.get_attribute('_id'):
            self.request.set_attribute('prepid', self.request.get_attribute('_id'))
        elif self.request.get_attribute('prepid'):
            self.request.set_attribute('_id', self.request.get_attribute('prepid'))
        else:
            self.request.set_attribute('_id', '')
            self.request.set_attribute('prepid', '')

        ##N.B (JR), '' is always an existing document
        if self.db.document_exists(self.request.get_attribute('_id')):
            self.logger.error('prepid %s already exists. Generating another...' % (self.request.get_attribute('_id')),
                              level='warning')

            id = RequestPrepId().generate_prepid(self.request.get_attribute('pwg'),
                                                 self.request.get_attribute('member_of_campaign'))
            self.request.set_attribute('prepid', loads(id)['prepid'])

            if not self.request.get_attribute('prepid'):
                self.logger.error('prepid returned was None')
                return dumps({"results": False, "message": "internal error and the request id is null"})

            self.request.set_attribute('_id', self.request.get_attribute('prepid'))

        self.logger.log('New prepid: %s' % (self.request.get_attribute('prepid')))



        ## put a generator info by default in case of possible root request
        if self.campaign['root'] <= 0:
            self.request.update_generator_parameters()

        ##cast the campaign parameters into the request: knowing that those can be edited at will later
        if not self.request.get_attribute('sequences'):
            self.request.build_cmsDrivers(cast=1, can_save=False)

        #c = self.cdb.get(camp)
        #tobeDraggedInto = ['cmssw_release','pileup_dataset_name']
        #for item in tobeDraggedInto:
        #    self.request.set_attribute(item,c.get_attribute(item))
        #nSeq=len(c.get_attribute('sequences'))
        #self.request.

        # update history
        if self.with_trace:
            self.request.update_history({'action': label})

        # save to database
        if not self.db.save(self.request.json()):
            self.logger.error('Could not save results to database')
            return dumps({"results": False})

        # add an action to the action_db
        try:
            self.add_action()
        except Exception as ex:
            return dumps({"results": False, "prepid": self.request.get_attribute('_id'), "message" : "It was not possible to set the action because %s"%(str(ex))})
        return dumps({"results": True, "prepid": self.request.get_attribute('_id')})


class CloneRequest(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)
        #self.access_limit = 1 ## maybe that is wrong

    def GET(self, *args):
        """
        Make a clone with no special requirement
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given.'})
        return self.clone_request(args[0])

    def PUT(self):
        """
        Make a clone with specific requirements
        """
        data = loads(cherrypy.request.body.read().strip())
        pid = data['prepid']
        return self.clone_request(pid, data)

    def clone_request(self, pid, data={}):
        new_pid = None

        if self.db.document_exists(pid):
            new_json = self.db.get(pid)
            new_json.update(data)
            del new_json['_id']
            del new_json['_rev']
            del new_json['prepid']
            del new_json['approval']
            del new_json['status']
            del new_json['history']
            del new_json['config_id']
            del new_json['member_of_chain']
            del new_json['validation']
            del new_json['completed_events']
            new_json['version'] = 0
            del new_json['generator_parameters']
            del new_json['reqmgr_name']
            del new_json['priority']

            return self.import_request(new_json, label='clone')
        else:
            return dumps({"results": False, "message": "cannot clone an inexisting id %s" % ( pid)})


class ImportRequest(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)
        #self.access_limit = 1 ## maybe that is wrong

    def PUT(self):
        """
        Saving a new request from a given dictionnary
        """
        return self.import_request(loads(cherrypy.request.body.read().strip()))


class UpdateRequest(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)

    def PUT(self):
        """
        Updating an existing request with an updated dictionnary
        """
        return self.update()

    def update(self):
        try:
            res = self.update_request(cherrypy.request.body.read().strip())
            return res
        except:
            self.logger.error('Failed to update a request from API')
            return dumps({'results': False, 'message': 'Failed to update a request from API'})

    def update_request(self, data):
        data = loads(data)
        if '_rev' not in data:
            self.logger.error('Could not locate the CouchDB revision number in object: %s' % (data))
            return dumps({"results": False, 'message': 'could not locate revision number in the object'})

        if not self.db.document_exists(data['_id']):
            return dumps({"results": False, 'message': 'request %s does not exist' % ( data['_id'])})
        else:
            if self.db.get(data['_id'])['_rev'] != data['_rev']:
                return dumps({"results": False, 'message': 'revision clash'})

        try:
            self.request = request(json_input=data)
        except request.IllegalAttributeName as ex:
            return dumps({"results": False, 'message': 'Mal-formatted request json in input'})

        if not self.request.get_attribute('prepid') and not self.request.get_attribute('_id'):
            self.logger.error('prepid returned was None')
            raise ValueError('Prepid returned was None')

        ## operate a check on whether it can be changed
        previous_version = request(self.db.get(self.request.get_attribute('prepid')))
        editable = previous_version.get_editable()
        for (key, right) in editable.items():
            # does not need to inspect the ones that can be edited
            if right: continue
            #self.logger.log('%s: %s vs %s : %s'%(key,previous_version.get_attribute(key),self.request.get_attribute(key),right))
            if key == 'sequences':
                ## need a special treatment because it is a list of dicts
                continue
            if (previous_version.get_attribute(key) != self.request.get_attribute(key)):
                self.logger.error('Illegal change of parameter, %s: %s vs %s : %s' % (
                    key, previous_version.get_attribute(key), self.request.get_attribute(key), right))
                return dumps({"results": False, 'message': 'Illegal change of parameter %s' % (key)})
                #raise ValueError('Illegal change of parameter')

        self.logger.log('Updating request %s...' % (self.request.get_attribute('prepid')))

        if len(self.request.get_attribute('history')) and 'action' in self.request.get_attribute('history')[0] and \
                        self.request.get_attribute('history')[0]['action'] == 'migrated':
            self.logger.log(
                'Not changing the actions for %s as it has been migrated' % (self.request.get_attribute('prepid')))
            pass
        else:
            # check on the action 
            if not self.set_campaign():
                return dumps({
                    "results": 'Error: Campaign ' + self.request.get_attribute('member_of_campaign') + ' does not exist.'})
            self.add_action()

        # update history
        if self.with_trace:
            self.request.update_history({'action': 'update'})
        return self.save_request()

    def save_request(self):
        return dumps({"results": self.db.update(self.request.json())})


class ManageRequest(UpdateRequest):
    """
    Same as UpdateRequest, leaving no trace in history, for admin only
    """

    def __init__(self):
        UpdateRequest.__init__(self)
        self.access_limit = 4
        self.with_trace = False

    def PUT(self):
        """
        Updating an existing request with an updated dictionnary, leaving no trace in history, for admin only
        """
        return self.update()


class MigratePage(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)

    def GET(self, *args):
        """
        Provides a page to migrate requests from prep
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": False, "message": 'Error: No arguments were given.'})
        prep_campaign = args[0]
        html = '<html><body>This is the migration page for %s' % (prep_campaign)
        html += '</body></html>'
        return html


class MigrateRequest(RequestRESTResource):
    """
    Self contained PREP->McM migration class
    """

    def __init__(self):
        RequestRESTResource.__init__(self)

    def GET(self, *args):
        """
        Imports am existing request from prep (id provided) to an already existing campaign in McM
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": False, "message": 'Error: No arguments were given.'})
        return self.migrate_from_prep(args[0])

    def migrate_from_prep(self, pid):

        ## get the campaign name
        prep_campaign = pid.split('-')[1]
        mcm_campaign = prep_campaign.replace('_', '')

        if not self.cdb.document_exists(mcm_campaign):
            return dumps(
                {"results": False, "message": 'no campaign %s exists in McM to migrate %s' % (mcm_campaign, pid)})
        camp = campaign(self.cdb.get(mcm_campaign))

        from sync.get_request import prep_scraper

        prep = prep_scraper()
        mcm_requests = prep.get(pid)
        if not len(mcm_requests):
            return dumps({"results": False, "message": "no conversions for prepid %s" % (pid)})
        mcm_request = mcm_requests[0]
        try:
            self.request = mcm_r = request(mcm_request)
        except:
            return dumps({"results": False, "message": "json does not cast into request type <br> %s" % (mcm_request)})

        ## make the sequences right ? NO, because that cast also the conditions ...
        #mcm_r.build_cmsDrivers(cast=-1)
        #mcm_r.build_cmsDrivers(cast=1)

        if mcm_r.get_attribute('mcdb_id') > 0 and mcm_r.get_attribute('status') not in ['submitted', 'done']:
            return dumps({"results": False,
                          "message": "A request which will require a step0 (%s) cannot be migrated in status %s, requires submitted or done" % (
                              mcm_r.get_attribute('mcdb_id'), mcm_r.get_attribute('status'))})

        mcm_r.update_history({'action': 'migrated'})
        if not self.db.document_exists(mcm_r.get_attribute('prepid')):
            mcm_r.get_stats(override_id=pid)

            if not len(mcm_r.get_attribute('reqmgr_name')) and mcm_r.get_attribute('status') in [
                'done']: #['done','submitted']:
                # no requests provided, the request should fail migration. 
                # I have put fake docs in stats so that it never happens
                return dumps(
                    {"results": False, "message": "Could not find an entry in the stats DB for prepid %s" % (pid)})

            # set the completed events properly
            if mcm_r.get_attribute('status') == 'done' and len(
                    mcm_r.get_attribute('reqmgr_name')) and mcm_r.get_attribute('completed_events') <= 0:
                mcm_r.set_attribute('completed_events',
                                    mcm_r.get_attribute('reqmgr_name')[-1]['content']['pdmv_evts_in_DAS'])

            saved = self.db.save(mcm_r.json())

            ## force to add an action on those requests
            #it might be that later on, upon update of the request that the action get deleted
            if camp.get_attribute('root') <= 0:
                if not self.set_campaign():
                    return dumps({"results": 'Error: Campaign ' + self.request.get_attribute(
                        'member_of_campaign') + ' does not exist.'})
                self.add_action(force=True)
        else:
            html = '<html><body>Request from PREP ((<a href="http://cms.cern.ch/iCMS/jsp/mcprod/admin/requestmanagement.jsp?code=%s" target="_blank">%s</a>) <b>already</b> in McM (<a href="/mcm/requests?prepid=%s&page=0" target="_blank">%s</a>)</body></html>' % (
                pid,
                pid,
                mcm_r.get_attribute('prepid'),
                mcm_r.get_attribute('prepid'))
            return html
            #return dumps({"results":False,"message":"prepid %s already exists as %s in McM"%(pid, mcm_r.get_attribute('prepid'))})

        if saved:
            html = '<html><body>Request migrated from PREP (<a href="http://cms.cern.ch/iCMS/jsp/mcprod/admin/requestmanagement.jsp?code=%s" target="_blank">%s</a>) to McM (<a href="/mcm/requests?prepid=%s&page=0" target="_blank">%s</a>)</body></html>' % (
                pid,
                pid,
                mcm_r.get_attribute('prepid'),
                mcm_r.get_attribute('prepid'))
            return html
            #return dumps({"results":saved,"message":"Request migrated from PREP (%s) to McM (%s)"%(pid,mcm_r.get_attribute('prepid'))})
        else:
            return dumps({"results": saved, "message": "could not save converted prepid %s in McM" % (pid)})

            #return dumps({"results":True,"message":"not implemented"})


class GetCmsDriverForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.json = {}
        self.request = None

    def GET(self, *args):
        """
        Retrieve the cmsDriver commands for a given request
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given.'})
        cast = 0
        if len(args) > 1:
            cast = int(args[1])
        return self.get_cmsDriver(self.db.get(prepid=args[0]), cast)

    def get_cmsDriver(self, data, cast):
        try:
            self.request = request(json_input=data)
        except request.IllegalAttributeName as ex:
            return dumps({"results": ''})

        return dumps({"results": self.request.build_cmsDrivers(cast=cast)})


class GetFragmentForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
      Retrieve the fragment as stored for a given request
      """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given.'})
        v = False
        if len(args) > 1:
            v = True
        return self.get_fragment(self.db.get(prepid=args[0]), v)

    def get_fragment(self, data, view):
        try:
            self.request = request(json_input=data)
        except request.IllegalAttributeName as ex:
            return dumps({"results": ''})

        fragmentText = self.request.get_attribute('fragment')
        if view:
            fragmentHTML = "<pre>"
            fragmentHTML += fragmentText
            fragmentHTML += "</pre>"
            return fragmentHTML
            fragmentHTML = ""
            for line in fragmentText.split('\n'):
                blanks = ""
                while line.startswith(' '):
                    blanks += "&nbsp;"
                    line = line[1:]
                line = blanks + line
                fragmentHTML += line.replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;") + "<br>"
            return fragmentHTML
        else:
            return fragmentText


class GetSetupForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
      Retrieve the script necessary to setup and test a given request
      """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given.'})
        pid = args[0]
        n = None
        if len(args) > 1:
            n = int(args[1])
                
        if self.db.document_exists(pid):
            try:
                self.request = request(self.db.get(pid))
            except request.IllegalAttributeName as ex:
                return dumps({"results": False})
            if n ==0:
                n = self.request.get_n_for_test(target=100.0)
            setupText = self.request.get_setup_file(events=n)
            cherrypy.response.headers['Content-Type'] = 'text/plain'
            return setupText
        else:
            return dumps({"results": False, "message": "%s does not exist" % (pid)})

    """
    def get_fragment(self, data):
    try:
    self.request = request(json_input=data)
    except request.IllegalAttributeName as ex:
    return dumps({"results":False})
    
    setupText = self.request.get_setup_file()
    return setupText
    """


class DeleteRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.adb = database('actions')
        self.crdb = database('chained_requests')

    def DELETE(self, *args):
        """
        Simply delete a request
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": False})
        return self.delete_request(args[0])

    def delete_request(self, pid):
        # delete actions !
        self.delete_action(pid)

        # delete chained requests !
        #self.delete_chained_requests(self,pid):

        return dumps({"results": self.db.delete(pid)})

    def delete_action(self, pid):
        if self.adb.document_exists(pid):
            self.adb.delete(pid)

    def delete_chained_requests(self, pid):
        mcm_crs = self.crdb.queries(['contains==' + pid])
        for doc in mcm_crs:
            self.crdb.delete(doc['prepid'])


class GetRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
        Retreive the dictionnary for a given request
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": {}})
        return self.get_request(args[0])

    def get_request(self, data):
        if not self.db.document_exists(data):
            return dumps({"results": {}})
        mcm_r = self.db.get(prepid=data)
        # cast the sequence for schema evolution !!! here or not ?
        for (i_s, s) in enumerate(mcm_r['sequences']):
            mcm_r['sequences'][i_s] = sequence(s).json()
        return dumps({"results": mcm_r})


class ApproveRequest(RESTResource):
    def __init__(self):
        self.db = database('requests')

    def GET(self, *args):
        """
        Approve to the next step, or specified index the given request or coma separated list of requests
        """
        if not args:
            return dumps({"results": 'Error: No arguments were given'})
        if len(args) == 1:
            return self.multiple_approve(args[0])
        return self.multiple_approve(args[0], int(args[1]))

    def multiple_approve(self, rid, val=-1):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.approve(r, val))
            return dumps(res)
        else:
            return dumps(self.approve(rid, val))

    def approve(self, rid, val=-1):
        if not self.db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given request id does not exist.'}
        req = request(json_input=self.db.get(rid))

        self.logger.log('Approving request %s for step "%s"' % (rid, val))

        #req.approve(val)
        try:
            if val == 0:
                req.reset()
            else:
                req.approve(val)

        except request.WrongApprovalSequence as ex:
            return {'prepid': rid, 'results': False, 'message': str(ex)}
        except request.WrongStatusSequence as ex:
            return {"prepid": rid, "results": False, 'message': str(ex)}
        except request.IllegalApprovalStep as ex:
            return {"prepid": rid, "results": False, 'message': str(ex)}
        except:
            return {'prepid': rid, 'results': False, 'message': traceback.format_exc()}

        return {'prepid': rid, 'approval': req.get_attribute('approval'), 'results': self.db.update(req.json())}


class ResetRequestApproval(ApproveRequest):
    def __init__(self):
        ApproveRequest.__init__(self)
        self.access_limit = 2

    def GET(self, *args):
        """
        Reste both approval and status to their initial state.
        """
        if not args:
            return dumps({"results": 'Error: No arguments were given'})
        return self.multiple_approve(args[0], 0)


class GetStatus(RESTResource):
    def __init__(self):
        self.db = database('requests')

    def GET(self, *args):
        if not args:
            return dumps({"results": 'Error: No arguments were given'})

        return self.multiple_status(args[0])

    def multiple_status(self, rid):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.status(r))
            return dumps(res)
        else:
            return dumps(self.status(rid))

    def status(self, rid):
        if not self.db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given request id does not exist.'}

        mcm_r = self.db.get(rid)
        
        while not 'status' in mcm_r:
            time.sleep(0.5)
            mcm_r = self.db.get(rid)

        return {rid: mcm_r['status']}


class InspectStatus(RESTResource):
    def __init__(self):
        self.db = database('requests')
        self.access_limit = 3

    def GET(self, *args):
        """
        Triggers the internal inspection of the status of a request or coma separated list of request
        """
        if not args:
            return dumps({"results": 'Error: No arguments were given'})
        return self.multiple_inspect(args[0])

    def multiple_inspect(self, rid):
        rlist = rid.rsplit(',')
        res = []
        for r in rlist:
            mcm_r = request(self.db.get(r))
            if mcm_r:
                res.append(mcm_r.inspect())
            else:
                res.append({"prepid": r, "results": False, 'message': '%s does not exist' % (r)})
        if len(res) > 1:
            return dumps(res)
        else:
            return dumps(res[0])


class SetStatus(RESTResource):
    def __init__(self):
        self.db = database('requests')
        self.access_limit = 3

    def GET(self, *args):
        """
        Perform the change of status to the next (/ids) or to the specidied index (/ids/index)
        """
        if not args:
            return dumps({"results": 'Error: No arguments were given'})
        if len(args) < 2:
            return self.multiple_status(args[0])
        return self.multiple_status(args[0], int(args[1]))

    def multiple_status(self, rid, val=-1):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.status(r, val))
            return dumps(res)
        else:
            return dumps(self.status(rid, val))

    def status(self, rid, step=-1):
        if not self.db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given request id does not exist.'}

        req = request(json_input=self.db.get(rid))

        try:
            ## set the status with a notification if done via the rest api
            req.set_status(step, with_notification=True)
        except request.WrongStatusSequence as ex:
            return {"prepid": rid, "results": False, 'message': str(ex)}
        except:
            return {"prepid": rid, "results": False, 'message': 'Unknow error' + traceback.format_exc()}

        return {"prepid": rid, "results": self.db.update(req.json())}


from tools.request_to_wma import request_to_wmcontrol
from tools.handler import handler, PoolOfHandlers
from tools.installer import installer
from tools.ssh_executor import ssh_executor


class prepare_and_submit(handler):
    """
    operate a runtest with the configs in config cache, operate submission, toggles the status to submitted
    """

    def __init__(self, rid):
        handler.__init__(self)
        self.rid = rid
        self.db = database('requests')

    def run(self):
        try:
            location = installer(self.rid, care_on_existing=False, clean_on_exit=True)

            test_script = location.location() + 'inject.sh'
            there = open(test_script, 'w')
            mcm_r = request(self.db.get(self.rid))
            there.write(mcm_r.get_setup_file(location.location()))
            there.write('\n')
            r2wm = request_to_wmcontrol()
            there.write(r2wm.get_command(mcm_r, 167, True))
            there.close()

            r2wm.get_requests(mcm_r)

            #ssh = ssh_executor( location.location(), self.rid )
            #stdin,  stdout,  stderr = ssh.execute('bash %s'%( test_script))

            ## now need to get the request manager name !

            self.logger.error(stdout.read())
            self.logger.error(stderr.read())
        finally:
            location.close()


class TestRequest(RESTResource):
    ## a rest api to make a creation test of a request
    def __init__(self):
        pass

    def GET(self, *args):
        """ 
        this is test for admins only
        """

        ids_list = args[0].split(',')
        new_list = []
        for rid in ids_list:
            new_list.append({'rid': rid})
        pool = PoolOfHandlers(runtest_genvalid, new_list)
        pool.start()


        #rdb = database('actions')
        #res = rdb.query('member_of_campaign==Summer11')
        #statsDB = database('stats',url='http://cms-pdmv-stats.cern.ch:5984/') 
        #res=statsDB.query(query='prepid==HIG-Summer11dr53X-00063')
        #return dumps(res)
        ### test for wmcontrol config
        #rdb = database('requests')
        #mcm_r = request( rdb.get(args[0]))
        #return request_to_wmcontrol().get_command( mcm_r, 12345, True)

        ### test for submission
        #inject = prepare_and_submit(args[0])
        #inject.run()

        ######################
        #### part of a test
        ########################
        #threaded_test = runtest_genvalid(args[0])
        #threaded_test.start()
        ###################

        return dumps({"on-going": True})


class InjectRequest(RESTResource):
    def __init__(self):
        # set user access to administrator
        self.authenticator.set_limit(4)
        self.db_name = 'requests'
        self.db = database(self.db_name)
        self.access_limit = 3

    class INJECTOR(Thread):
        def __init__(self, pid, log, how_far=None,check_on_approval=True,wait=0):
            Thread.__init__(self)
            self.logger = log
            self.wait=wait
            self.db = database('requests')
            self.act_on_pid = []
            self.res = []
            self.how_far = how_far
            if not self.db.document_exists(pid):
                self.res.append({"prepid": pid, "results": False, "message": "The request %s does not exist" % (pid)})
                return

            req = request(self.db.get(pid))
            if req.get_attribute('status') != 'approved':
                self.res.append({"prepid": pid, "results": False,
                                 "message": "The request is in status %s, while approved is required" % (
                                     req.get_attribute('status'))})
                return
            if check_on_approval and req.get_attribute('approval') != 'submit':
                self.res.append({"prepid": pid, "results": False,
                                 "message": "The request is in approval %s, while submit is required" % (
                                     req.get_attribute('approval'))})
                return
            if not req.get_attribute('member_of_chain'):
                self.res.append({"prepid": pid, "results": False, "message": "The request is not member of any chain"})
                return

            self.act_on_pid.append(pid)
            ## this is a line that allows to brows back the logs efficiently
            self.logger.inject('## Logger instance retrieved', level='info', handler=pid)

            self.res.append({"prepid": pid, "results": True,
                             "message": "The request %s will be forked unless same request is being handled already" % (
                                 pid)})

        def run(self):
            if len(self.act_on_pid):
                self.res = []
            for pid in self.act_on_pid:
                time.sleep(self.wait)
                if not locker.acquire(pid, blocking=False):
                    self.res.append(
                        {"prepid": pid, "results": False, "message": "The request is already being handled"})
                    continue
                try:
                    req = request(self.db.get(pid))
                    pb = None
                    try:
                        pb = package_builder(req_json=req.json())
                    except:
                        message = "Errors in making the request : \n" + traceback.format_exc()
                        self.logger.inject(message, handler=pid)
                        self.logger.error(message)
                        self.res.append({"prepid": pid, "results": False, "message": message})
                        req.test_failure(message)
                        continue
                    try:
                        res_sub = pb.build_package()
                    except:
                        message = "Errors in building the request : \n" + traceback.format_exc()
                        self.logger.inject(message, handler=pid)
                        self.logger.error(message)
                        self.res.append({"prepid": pid, "results": False, "message": message})
                        req.test_failure(message)
                        continue

                    self.res.append({"prepid": pid, "results": res_sub})
                    ## now remove the directory maybe ?
                finally:
                    locker.release(pid)

        def status(self):
            return self.res

    def GET(self, *args):
        """
        Perform the thread (/ids/thread) or live preparation (/ids), testing, injection of a request, or coma separated list of requests.
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})

        res = []
        forking = False
        if len(args) > 1 and args[1] == 'thread':
            forking = True

        forks = []
        ids = args[0].split(',')
        for pid in ids:
            forks.append(self.INJECTOR(pid, self.logger))
            if forking:
                self.logger.log('Forking the injection of request %s ' % (pid))
                res.extend(forks[-1].status())
                ##forks the process directly
                forks[-1].start()
            else:
                ##makes you wait until it goes
                self.logger.log('Running the injection of request %s ' % (pid))
                forks[-1].run()
                res.extend(forks[-1].status())

        if len(res) > 1:
            return dumps(res)
        elif len(res) == 0:
            return dumps({"results": False})
        else:
            return dumps(res)


class GetEditable(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
        Retreive the fields that are currently editable for a given request id
        """
        if not args:
            self.logger.error('Request/GetEditable: No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})
        return self.get_editable(args[0])

    def get_editable(self, prepid):
        request_in_db = request(self.db.get(prepid=prepid))
        editable = request_in_db.get_editable()
        return dumps({"results": editable})


class GetDefaultGenParams(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
        Simply get the schema for the generator parameters object in request.
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})

        return self.get_default_params(args[0])

    def get_default_params(self, prepid):
        request_in_db = request(self.db.get(prepid=prepid))
        request_in_db.update_generator_parameters()
        return dumps({"results": request_in_db.get_attribute('generator_parameters')[-1]})


class NotifyUser(RESTResource):
    def __init__(self):
        self.rdb = database('requests')

    def PUT(self):
        """
        Sends the prodived posted text to the user registered to a list of requests request
        """
        data = loads(cherrypy.request.body.read().strip())
        # read a message from data
        message = data['message']
        pids = data['prepids']
        results = []
        for pid in pids:
            if not self.rdb.document_exists(pid):
                return results.append({"prepid": pid, "results": False, "message": "%s does not exist" % (pid)})

            req = request(self.rdb.get(pid))
            # notify the actors of the request
            req.notify('Communication about request %s' % (pid),
                       message)
            # update history with "notification"
            req.update_history({'action': 'notify', 'step': message})
            if not self.rdb.save(req.json()):
                return results.append({"prepid": pid, "results": False, "message": "Could not save %s" % (pid)})

            results.append({"prepid": pid, "results": True, "message": "Notification send for %s" % (pid)})
        return dumps(results)


class RegisterUser(RESTResource):
    def __init__(self):
        self.rdb = database('requests')
        self.udb = database('users')

    def GET(self, *args):
        """
        Any person with cern credential can register to a request or a list of requests
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": False, 'message': 'Error: No arguments were given'})
        return self.multiple_register(args[0]);

    def multiple_register(self, rid):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.register_user(r))
            return dumps(res)
        else:
            return dumps(self.register_user(rid))

    def register_user(self, pid):
        request_in_db = request(self.rdb.get(pid))
        current_user = request_in_db.current_user
        if not current_user or not self.udb.document_exists(current_user):
            return {"prepid": pid, "results": False,
                    'message': "You (%s) are not a registered user to McM, correct this first" % (current_user)}

        if current_user in request_in_db.get_actors():
            return {"prepid": pid, "results": False,
                    'message': "%s already in the list of people for notification of %s" % (current_user, pid)}

        #self.logger.error('list of users %s'%(request_in_db.get_actors()))
        #self.logger.error('current actor %s'%(current_user))

        request_in_db.update_history({'action': 'register', 'step': current_user})
        self.rdb.save(request_in_db.json())
        return {"prepid": pid, "results": True, 'message': 'You (%s) are registered to %s' % (current_user, pid)}


class GetActors(RESTResource):
    def __init__(self):
        self.rdb = database('requests')

    def GET(self, *args):
        """
        Provide the list of user registered and actors to a given request
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": False, 'message': 'Error: No arguments were given'})
        if len(args) > 1:
            return self.show_user(args[0], args[1])
        return self.show_user(args[0])

    def show_user(self, pid, what=None):
        request_in_db = request(self.rdb.get(pid))
        if what:
            return dumps(request_in_db.get_actors(what=what))
        else:
            return dumps(request_in_db.get_actors())


class SearchableRequest(RESTResource):
    def __init__(self):
        self.rdb = database('requests')
        self.access_limit = 0

    def GET(self, *args):
        """
        Return a document containing several usal values that can be searched and the value can be find. /do will trigger reloading of that document from all requests
        """
        if len(args) and args[0] == 'do':
            all_requests = self.rdb.queries([])

            searchable = {}

            for request in all_requests:
                for key in ['energy', 'dataset_name', 'status', 'approval', 'extension', 'generators',
                            'member_of_chain', 'pwg', 'process_string', 'mcdb_id', 'prepid', 'flown_with',
                            'member_of_campaign']:
                    if not key in searchable:
                        searchable[key] = set([])
                    if not key in request:
                        ## that should make things break down, and due to schema evolution missed-migration
                        continue
                    if type(request[key]) == list:
                        for item in request[key]:
                            searchable[key].add(str(item))
                    else:
                        searchable[key].add(str(request[key]))

            #unique it
            for key in searchable:
                searchable[key] = list(searchable[key])
                searchable[key].sort()

            #store that value
            search = database('searchable')
            if search.document_exists('searchable'):
                search.delete('searchable')
            searchable.update({'_id': 'searchable'})
            search.save(searchable)
            searchable.pop('_id')
            return dumps(searchable)
        else:
            ## just retrieve that value
            search = database('searchable')
            searchable = search.get('searchable')
            searchable.pop('_id')
            searchable.pop('_rev')
            return dumps(searchable)


class SearchRequest(RESTResource):
    def __init__(self):
        self.rdb = database('requests')
        self.crdb = database('chained_requests')
        self.access_limit = 0

    def PUT(self, *args):
        """
        Search requests according to the search json provided for wild search
        """
        search_dict = loads(cherrypy.request.body.read().strip())
        self.logger.error("Got a wild search dictionnary %s" % ( str(search_dict) ))

        output_object = 'requests'
        if len(args):
            output_object = args[0]

        wild_search_dict = {}
        reg_queries = []
        for (key, search) in search_dict.items():
            if '*' in search or '+' in search:
                wild_search_dict[str(key)] = str(search)
            else:
                reg_queries.append('%s==%s' % ( key, search))

        if len(reg_queries) == 0 and len(wild_search_dict) == 0:
            return dumps({"results": []})

        ## do all the regular search the regular way
        results = self.rdb.queries(reg_queries)

        self.logger.error("Got %s results so far" % ( len(results)))

        for (key, search) in wild_search_dict.items():
            ## * is and
            key_searchs = filter(lambda s: len(s), map(string.lower, search.split('*')))
            self.logger.error("Wild search on %s %s %s" % (key, search, key_searchs ))
            if len(results) == 0:
                self.logger.error("no results anymore...")
                break
                #try:
            #    x= results[0][key] 
            #except:
            #    self.logger.error("Request content %s"%( str( results[0])))

            if type(results[0][key]) == list:
                for key_search in key_searchs:
                    #self.logger.error("Got %s results so far (list)"%( len( results)))
                    results = filter(lambda doc: any(map(lambda item: key_search in item.lower(), doc[key])), results)
                    #self.logger.error("Got %s results so far (list)"%( len( results)))
            elif type(results[0][key]) == int:
                for key_search in key_searchs:
                    ##until something better comes up
                    results = filter(lambda doc: str(key_search) in str(doc[key]).lower(), results)
            else:
                for key_search in key_searchs:
                    #self.logger.error("Got %s results so far (else)"%( len( results)))
                    results = filter(lambda doc: key_search in doc[key].lower(), results)
                    #self.logger.error("Got %s results so far (else)"%( len( results)))

        if output_object == 'chained_requests':
            cr_ids = set()
            for r in results:
                for cr in r['member_of_chain']:
                    if self.crdb.document_exists(cr):
                        cr_ids.add(cr)
            cr_results = []
            for cr in sorted(cr_ids):
                cr_results.append(self.crdb.get(cr))
            return dumps({"results": cr_results})

        return dumps({"results": results})


class RequestPerformance(RESTResource):
    def __init__(self):
        self.rdb = database('requests')
        self.access_limit = 4

    def PUT(self, *args):
        """
        Upload performance report .xml : retrieve size_event and time_event
        """
        self.logger.error("Got a performance file from uploading %s" % (str(args)))
        if len(args) != 2:
            return dumps({"results": False, "message": "not enough arguments"})

        rid = args[0]
        if not self.rdb.document_exists(rid):
            return dumps({"results": False, "message": "%s does not exist" % ( rid)})

        what = args[1]
        if not what in ["perf", "eff"]:
            return dumps({"results": False, "message": "%s is not a valid option" % ( what)})

        xml_doc = cherrypy.request.body.read()

        ## then get the request ID and update it's value
        mcm_r = request(self.rdb.get(rid))
        to_be_saved = mcm_r.update_performance(xml_doc, what)

        if to_be_saved:
            saved = self.rdb.update(mcm_r.json())
            if saved:
                return dumps({"results": True, "prepid": rid})
            else:
                return dumps({"results": False, "prepid": rid})
        else:
            return dumps({"results": False, "prepid": rid})


class RequestLister():
    def __init__(self):
        self.rdb = database('requests')
        self.cdb = database('campaigns')
        self.all_campaigns = map(lambda x: x['id'], self.cdb.raw_query("prepid"))
        self.retrieve_db = None

    def get_objects(self, all_ids):
        all_objects = []
        if len(all_ids) and self.retrieve_db:
            for oid in all_ids:
                if self.retrieve_db.document_exists(oid):
                    all_objects.append(self.retrieve_db.get(oid))

        self.logger.error("Got %s ids identified" % ( len(all_objects)))
        return dumps({"results": all_objects})

    def identify_an_id(self, word):
        if word.count('-') == 2:
            (pwg, campaign, serial) = word.split('-')
            if len(pwg) != 3:
                return None
            if not serial.isdigit():
                return None
            if not campaign in self.all_campaigns:
                return None
            if self.rdb.document_exists(word):
                return word
        return None

    def identify_a_dataset_name(self, word):
        #self.logger.error('word %s %s'%(word, word.count('/')))
        if word.count('/') == 3:
            #self.logger.error('word %s'%(word))
            (junk, dsn, ps, tier) = word.split('/')
            if junk:
                return None
            return dsn

    def get_list_of_ids(self):
        self.logger.error("Got a file from uploading")
        data = loads(cherrypy.request.body.read().strip())
        text = data['contents']

        all_ids = []
        all_dsn = {}
        ## parse that file for prepids
        possible_campaign = None
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
                    if not possible_campaign in all_dsn:
                        all_dsn[possible_campaign] = []

                ## is that a prepid ?
                an_id = None
                a_dsn = None
                if possible_campaign == None:
                    an_id = self.identify_an_id(word)

                if an_id:
                    all_ids.append(an_id)
                    in_the_line.append(an_id)
                elif possible_campaign:
                    a_dsn = self.identify_a_dataset_name(word)
                    if a_dsn:
                        all_dsn[possible_campaign].append(a_dsn)

                ## the ley word for range
                if word == '->':
                    if len(in_the_line):
                        in_the_line = [in_the_line[-1]]

                ## dealing with id range
                if len(in_the_line) == 2:
                    id_start = in_the_line[0]
                    id_end = in_the_line[1]
                    in_the_line = []
                    if id_start[0:4] == id_end[0:4]:
                        serial_start = int(id_start.split('-')[-1])
                        serial_end = int(id_end.split('-')[-1]) + 1
                        for serial in range(serial_start, serial_end):
                            all_ids.append('-'.join(id_start.split('-')[0:2] + ['%05d' % (serial)]))

        for (possible_campaign, possible_dsn) in all_dsn.items():
            #self.logger.error("Found those dsn to look for %s"%(possible_dsn))
            if not self.cdb.document_exists(possible_campaign):
                continue
                ## get all requests
            all_requests = self.rdb.queries(['member_of_campaign==%s' % ( possible_campaign)])
            for request in all_requests:
                if request['dataset_name'] in possible_dsn:
                    all_ids.append(request['prepid'])

        all_ids = list(set(all_ids))
        all_ids.sort()
        return all_ids


class RequestsFromFile(RequestLister, RESTResource):
    def __init__(self):
        RequestLister.__init__(self)
        self.retrieve_db = self.rdb
        self.access_limit = 0

    def PUT(self, *args):
        """
        Parse the posted text document for request id and request ranges for display of requests
        """
        all_ids = self.get_list_of_ids()
        return self.get_objects(all_ids)


class RequestsReminder(RESTResource):
    def __init__(self):
        self.access_limit = 4

    def GET(self, *args):
        """
        Goes through all requests and send reminder to whom is concerned
        """
        what = None
        if len(args):
            #we've been passed parameters
            what = args[0].split(',')
            if 'all' in what:
                what = None

        udb = database('users')
        rdb = database('requests')

        #all_requests = rdb.queries([])
        # a dictionnary  campaign : [ids]
        ids_for_production_managers = {}
        # a dictionnary  campaign : [ids]
        ids_for_gen_conveners = {}
        # a dictionnary contact : { campaign : [ids] }
        ids_for_users = {}

        res = []
        ## fill up the reminders
        def get_all_in_status(status, extracheck=None):
            campaigns_and_ids = {}
            for mcm_r in rdb.queries(['status==%s' % (status)]):
                ## check whether it has a valid action before to add them in the reminder
                c = mcm_r['member_of_campaign']
                if not c in campaigns_and_ids:
                    campaigns_and_ids[c] = []
                if extracheck == None or extracheck(mcm_r):
                    campaigns_and_ids[c].append(mcm_r['prepid'])

            #then remove the empty entries
            for c in campaigns_and_ids.keys():
                if not len(campaigns_and_ids[c]):
                    campaigns_and_ids.pop(c)
            
            return campaigns_and_ids

        com = communicator()
        l_type = locator()


        def prepare_text_for(campaigns_and_ids, status_for_link):
            message = ''
            for (camp, ids) in campaigns_and_ids.items():
                message += 'For campaign: %s \n' % ( camp )
                message += '%srequests?page=-1&member_of_campaign=%s&status=%s \n' % (
                    l_type.baseurl(), camp, status_for_link)
                for rid in ids:
                    message += '\t%s\n' % ( rid)
                message += '\n'
            return message

        def is_in_chain(r):
            if len(r['member_of_chain']) != 0:
                return True
            else:
                return False

        if not what or 'production_manager' in what:
            ## send the reminder to the production managers
            ids_for_production_managers = get_all_in_status('approved', extracheck=is_in_chain)
            for c in ids_for_production_managers:
                res.extend(map(lambda i: {"results": True, "prepid": i}, ids_for_production_managers[c]))

            if len(ids_for_production_managers):
                production_managers = udb.queries(['role==production_manager'])
                message = 'A few request that needs to be submitted \n\n'
                message += prepare_text_for(ids_for_production_managers, 'approved')
                com.sendMail(map(lambda u: u['email'], production_managers) + ['pdmvserv@cern.ch'],
                             'Gentle reminder on requests to be submitted',
                             message)

        if not what or 'gen_conveners' in what:
        ## send the reminder to generator conveners
            ids_for_gen_conveners = get_all_in_status('defined')
            for c in ids_for_gen_conveners:
                res.extend(map(lambda i: {"results": True, "prepid": i}, ids_for_gen_conveners[c]))
            if len(ids_for_gen_conveners):
                gen_conveners = udb.queries(['role==generator_convener'])
                message = 'A few requests need your approvals \n\n'
                message += prepare_text_for(ids_for_gen_conveners, 'defined')
                com.sendMail(map(lambda u: u['email'], gen_conveners) + ['pdmvserv@cern.ch'],
                             'Gentle reminder on requests to be approved by you',
                             message)

        if not what:
            if len(ids_for_users):
                gen_contacts = udb.queries(['role==generator_contact'])
                users = udb.queries(['role==user'])
                for (user, campaigns_and_ids) in ids_for_users.items():
                    if len(campaigns_and_ids):
                        message = 'A few request need you action \n\n'
                        message += prepare_text_for(campaigns_and_ids, 'validation')
                        com.sendMail([user['email'], 'pdmvserv@cern.ch'],
                                     'Gentle reminder on requests to be looked at',
                                     message
                        )

        return dumps(res)

class UpdateMany(RequestRESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.db = database(self.db_name)
        RequestRESTResource.__init__(self)
        self.updateSingle = UpdateRequest()

    def PUT(self):
        """
        Updating an existing multiple requests with an updated dictionnary
        """
        return self.update_many(loads(cherrypy.request.body.read().strip()))

    def update_many(self, data):
        list_of_prepids = data["prepids"]
        updated_values = data["updated_data"]
        return_info = []
        for elem in list_of_prepids:
            document = self.db.get(elem)
            for value in updated_values:
                document[value] = updated_values[value]
            return_info.append(loads(self.updateSingle.update_request(dumps(document))))
        self.logger.log('updating requests: %s' %(return_info))
        return dumps({"results":return_info})
