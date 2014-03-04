#!/usr/bin/env python

import cherrypy
import traceback
import string
import time
import urllib2
from json import loads, dumps
from collections import defaultdict

from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResource
from RequestPrepId import RequestPrepId
from BatchPrepId import BatchPrepId
from json_layer.request import request
from json_layer.chained_request import chained_request
from json_layer.sequence import sequence
from json_layer.action import action
from json_layer.campaign import campaign
from tools.locator import locator
from tools.communicator import communicator
from tools.locker import locker
from tools.settings import settings
from tools.handlers import RequestInjector
from tools.user_management import access_rights

class RequestRESTResource(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.access_limit = access_rights.generator_contact
        self.with_trace = True

    def set_campaign(self, mcm_req):
        cdb = database('campaigns')
        # check that the campaign it belongs to exists
        camp = mcm_req.get_attribute('member_of_campaign')
        if not cdb.document_exists(camp):
            return None
            ## get campaign
        camp = campaign(cdb.get(camp))
        mcm_req.set_attribute('energy', camp.get_attribute('energy'))
        if not mcm_req.get_attribute('cmssw_release'):
            mcm_req.set_options(can_save=False)

        return camp

    ## duplicate version to be centralized in a unique class
    def add_action(self, mcm_req, camp, force=False):
        # Check to see if the request is a root request
        #camp = mcm_req.get_attribute('member_of_campaign')

        #if not cdb.document_exists(camp):
        #    return dumps({"results":'Error: Campaign '+str(camp)+' does not exist.'})

        # get campaign
        #self.c = cdb.get(camp)
        adb = database('actions')
        rootness = camp.get_attribute('root')
        mcdbid = int(mcm_req.get_attribute('mcdb_id'))
        inputds = mcm_req.get_attribute('input_dataset')
        if (not force) and (rootness == 1 or rootness == -1 and mcdbid > -1):
            ## c['root'] == 1
            ##            :: not a possible root --> no action in the table
            ## c['root'] == -1 and mcdb > -1
            ##            ::a possible root and mcdbid=0 (import from WMLHE) or mcdbid>0 (imported from PLHE) --> no action on the table
            if adb.document_exists(mcm_req.get_attribute('prepid')):
                ## check that there was no already inserted actions, and remove it in that case

                ##check that it empty !!!
                mcm_a = adb.get(mcm_req.get_attribute('prepid'))
                for (cc,c) in mcm_a['chains'].items():
                    if 'flag' in c and c['flag']:
                        raise Exception("The action item that corresponds to %s is set within %s"%( mcm_req.get_attribute('prepid'), cc))
                    if 'chains' in c:
                        for cr in c['chains']:
                            raise Exception("The action item that corresponds to %s has a chained request %s attached within %s"%(  mcm_req.get_attribute('prepid'), cr, cc))

                adb.delete(mcm_req.get_attribute('prepid'))
            return

        # check to see if the action already exists
        if not adb.document_exists(mcm_req.get_attribute('prepid')):
            # add a new action
            #a= action('automatic')
            a = action()
            a.set_attribute('prepid', mcm_req.get_attribute('prepid'))
            a.set_attribute('_id', a.get_attribute('prepid'))
            a.set_attribute('dataset_name', mcm_req.get_attribute('dataset_name'))
            a.set_attribute('member_of_campaign', mcm_req.get_attribute('member_of_campaign'))
            a.find_chains()
            self.logger.log('Adding an action for %s' % (mcm_req.get_attribute('prepid')))
            adb.save(a.json())
        else:
            a = action(adb.get(mcm_req.get_attribute('prepid')))
            if a.get_attribute('dataset_name') != mcm_req.get_attribute('dataset_name'):
                a.set_attribute('dataset_name', mcm_req.get_attribute('dataset_name'))
                self.logger.log('Updating an action for %s' % (mcm_req.get_attribute('prepid')))
                adb.save(a.json())

    def import_request(self, data, db, label='created', step=None):

        if '_rev' in data:
            return {"results": False, 'message': 'could not save object with a revision number in the object'}

        try:
            #mcm_req = request(json_input=loads(data))
            mcm_req = request(json_input=data)
        except request.IllegalAttributeName as ex:
            return {"results": False, "message": str(ex)}
        camp = self.set_campaign(mcm_req)
        if not camp:
            return {"results": False, "message": 'Error: Campaign ' + mcm_req.get_attribute(
                'member_of_campaign') + ' does not exist.'}

        if camp.get_attribute('status') != 'started':
            return {"results": False, "message": "Cannot create a request in a campaign that is not started"}

        self.logger.log('Building new request...')

        # set '_id' and 'prepid' fields
        if mcm_req.get_attribute('_id'):
            mcm_req.set_attribute('prepid', mcm_req.get_attribute('_id'))
        elif mcm_req.get_attribute('prepid'):
            mcm_req.set_attribute('_id', mcm_req.get_attribute('prepid'))
        else:
            mcm_req.set_attribute('_id', '')
            mcm_req.set_attribute('prepid', '')

        ##N.B (JR), '' is always an existing document
        existed = False
        if db.document_exists(mcm_req.get_attribute('_id')):
            existed = True
            self.logger.error('prepid %s already exists. Generating another...' % (mcm_req.get_attribute('_id')),
                              level='warning')

            prepid = RequestPrepId().next_prepid(mcm_req.get_attribute('pwg'),
                                                 mcm_req.get_attribute('member_of_campaign'))
            mcm_req = request(db.get(prepid))
            for key in data:
                if key not in ['prepid', '_id', 'history']:
                    mcm_req.set_attribute(key, data[key])

            if not mcm_req.get_attribute('prepid'):
                self.logger.error('prepid returned was None')
                return {"results": False, "message": "internal error and the request id is null"}

        self.logger.log('New prepid: %s' % (mcm_req.get_attribute('prepid')))



        ## put a generator info by default in case of possible root request
        if camp.get_attribute('root') <= 0:
            mcm_req.update_generator_parameters()

        ##cast the campaign parameters into the request: knowing that those can be edited at will later
        if not mcm_req.get_attribute('sequences'):
            mcm_req.set_options(can_save=False)

        #c = cdb.get(camp)
        #tobeDraggedInto = ['cmssw_release','pileup_dataset_name']
        #for item in tobeDraggedInto:
        #    mcm_req.set_attribute(item,c.get_attribute(item))
        #nSeq=len(c.get_attribute('sequences'))
        #mcm_req.

        # update history
        if self.with_trace:
            if step:
                mcm_req.update_history({'action': label, 'step' : step})
            else:
                mcm_req.update_history({'action': label})

        # save to database or update if existed
        if not existed:
            if not db.save(mcm_req.json()):
                self.logger.error('Could not save results to database')
                return {"results": False}
        else:
            if not db.update(mcm_req.json()):
                self.logger.error('Could not update request in database')
                return {"results": False}

        # add an action to the action_db
        try:
            self.add_action(mcm_req, camp)
        except Exception as ex:
            return {"results": False, "prepid": mcm_req.get_attribute('_id'), "message" : "It was not possible to set the action because %s"%(str(ex))}
        return {"results": True, "prepid": mcm_req.get_attribute('_id')}


class CloneRequest(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)
        #self.access_limit = access_rights.generator_contact ## maybe that is wrong

    def GET(self, *args):
        """
        Make a clone with no special requirement
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given.'})
        return dumps(self.clone_request(args[0]))

    def PUT(self):
        """
        Make a clone with specific requirements
        """
        data = loads(cherrypy.request.body.read().strip())
        pid = data['prepid']
        return dumps(self.clone_request(pid, data))

    def clone_request(self, pid, data={}):
        db = database(self.db_name)
        if db.document_exists(pid):
            new_json = db.get(pid)
            if new_json['flown_with']:
                return {"results": False, "message": "cannot clone a request that has been flown"}

        
            to_wipe=['_id','_rev','prepid','approval','status','history','config_id','reqmgr_name','member_of_chain','validation','completed_events','version','generator_parameters','priority','analysis_id', 'extension','output_dataset']
            if 'member_of_campaign' in data and data['member_of_campaign'] != new_json['member_of_campaign']:
                ## this is a cloning accross campaign: a few other things need to be cleanedup
                to_wipe.extend( ['cmssw_release','energy','sequences'] )

            new_json.update(data)
            ## remove some of the parameters to get then fresh from a new request.
            for w in to_wipe:
                del new_json[w]

            return self.import_request(new_json, db, label='clone', step=pid)
        else:
            return {"results": False, "message": "cannot clone an inexisting id %s" % pid}


class ImportRequest(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)
        #self.access_limit = access_rights.generator_contact ## maybe that is wrong

    def PUT(self):
        """
        Saving a new request from a given dictionnary
        """
        db = database(self.db_name)
        return dumps(self.import_request(loads(cherrypy.request.body.read().strip()), db))


class UpdateRequest(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)

    def PUT(self):
        """
        Updating an existing request with an updated dictionary
        """
        return dumps(self.update())

    def update(self):
        try:
            res = self.update_request(cherrypy.request.body.read().strip())
            return res
        except:
            self.logger.error('Failed to update a request from API \n%s'%( traceback.format_exc() ))
            return {'results': False, 'message': 'Failed to update a request from API'}

    def update_request(self, data):
        data = loads(data)
        db = database(self.db_name)
        if '_rev' not in data:
            self.logger.error('Could not locate the CouchDB revision number in object: %s' % data)
            return {"results": False, 'message': 'could not locate revision number in the object'}

        if not db.document_exists(data['_id']):
            return {"results": False, 'message': 'request %s does not exist' % ( data['_id'])}
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

        ## operate a check on whether it can be changed
        previous_version = request(db.get(mcm_req.get_attribute('prepid')))
        editable = previous_version.get_editable()
        for (key, right) in editable.items():
            # does not need to inspect the ones that can be edited
            if right: continue
            #self.logger.log('%s: %s vs %s : %s'%(key,previous_version.get_attribute(key),mcm_req.get_attribute(key),right))
            if key == 'sequences':
                ## need a special treatment because it is a list of dicts
                continue
            if previous_version.get_attribute(key) != mcm_req.get_attribute(key):
                self.logger.error('Illegal change of parameter, %s: %s vs %s : %s' % (
                    key, previous_version.get_attribute(key), mcm_req.get_attribute(key), right))
                return {"results": False, 'message': 'Illegal change of parameter %s' % key}
                #raise ValueError('Illegal change of parameter')

        self.logger.log('Updating request %s...' % (mcm_req.get_attribute('prepid')))

        if len(mcm_req.get_attribute('history')) and 'action' in mcm_req.get_attribute('history')[0] and \
                        mcm_req.get_attribute('history')[0]['action'] == 'migrated':
            self.logger.log(
                'Not changing the actions for %s as it has been migrated' % (mcm_req.get_attribute('prepid')))
            pass
        else:
            # check on the action
            camp = self.set_campaign(mcm_req)
            if not camp:
                return {"results": 'Error: Campaign ' + mcm_req.get_attribute('member_of_campaign') + ' does not exist.'}
            self.add_action(mcm_req, camp)

        # update history
        if self.with_trace:
            mcm_req.update_history({'action': 'update'})
        return self.save_request(mcm_req, db)

    def save_request(self, mcm_req, db):
        return {"results": db.update(mcm_req.json())}


class ManageRequest(UpdateRequest):
    """
    Same as UpdateRequest, leaving no trace in history, for admin only
    """

    def __init__(self):
        UpdateRequest.__init__(self)
        self.access_limit = access_rights.administrator
        self.with_trace = False

    def PUT(self):
        """
        Updating an existing request with an updated dictionnary, leaving no trace in history, for admin only
        """
        return dumps(self.update())


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
        html = '<html><body>This is the migration page for %s' % prep_campaign
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
        res = self.migrate_from_prep(args[0])
        return dumps(res) if isinstance(res, dict) else res

    def migrate_from_prep(self, pid):

        ## get the campaign name
        prep_campaign = pid.split('-')[1]
        mcm_campaign = prep_campaign.replace('_', '')

        cdb = database('campaigns')
        db = database(self.db_name)

        if not cdb.document_exists(mcm_campaign):
            return {"results": False, "message": 'no campaign %s exists in McM to migrate %s' % (mcm_campaign, pid)}
        camp = campaign(cdb.get(mcm_campaign))

        from sync.get_request import prep_scraper

        prep = prep_scraper()
        mcm_requests = prep.get(pid)
        if not len(mcm_requests):
            return {"results": False, "message": "no conversions for prepid %s" % pid}
        mcm_request = mcm_requests[0]
        try:
            mcm_req = mcm_r = request(mcm_request)
        except:
            return {"results": False, "message": "json does not cast into request type <br> %s" % mcm_request}

        ## make the sequences right ? NO, because that cast also the conditions ...
        #mcm_r.build_cmsDrivers(cast=-1)
        #mcm_r.build_cmsDrivers(cast=1)

        if mcm_r.get_attribute('mcdb_id') > 0 and mcm_r.get_attribute('status') not in ['submitted', 'done']:
            return {"results": False,
                          "message": "A request which will require a step0 (%s) cannot be migrated in status %s, requires submitted or done" % (
                              mcm_r.get_attribute('mcdb_id'), mcm_r.get_attribute('status'))}

        mcm_r.update_history({'action': 'migrated'})
        if not db.document_exists(mcm_r.get_attribute('prepid')):
            mcm_r.get_stats(override_id=pid)

            if not len(mcm_r.get_attribute('reqmgr_name')) and mcm_r.get_attribute('status') in [
                'done']: #['done','submitted']:
                # no requests provided, the request should fail migration. 
                # I have put fake docs in stats so that it never happens
                return {"results": False, "message": "Could not find an entry in the stats DB for prepid %s" % pid}

            # set the completed events properly
            if mcm_r.get_attribute('status') == 'done' and len(
                    mcm_r.get_attribute('reqmgr_name')) and mcm_r.get_attribute('completed_events') <= 0:
                mcm_r.set_attribute('completed_events',
                                    mcm_r.get_attribute('reqmgr_name')[-1]['content']['pdmv_evts_in_DAS'])

            saved = db.save(mcm_r.json())

            ## force to add an action on those requests
            #it might be that later on, upon update of the request that the action get deleted
            if camp.get_attribute('root') <= 0:
                if not self.set_campaign(mcm_req):
                    return {"results": 'Error: Campaign ' + mcm_req.get_attribute('member_of_campaign') + ' does not exist.'}
                self.add_action(mcm_req, camp, force=True)
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
            return {"results": saved, "message": "could not save converted prepid %s in McM" % pid}

            #return dumps({"results":True,"message":"not implemented"})


class GetCmsDriverForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.json = {}

    def GET(self, *args):
        """
        Retrieve the cmsDriver commands for a given request
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given.'})
        db = database(self.db_name)
        return dumps(self.get_cmsDriver(db.get(prepid=args[0])))

    def get_cmsDriver(self, data):
        try:
            mcm_req = request(json_input=data)
        except request.IllegalAttributeName:
            return {"results": ''}

        return {"results": mcm_req.build_cmsDrivers()}


class OptionResetForRequest(RESTResource):

    def __init__(self):
        self.db_name = 'requests'
        self.access_limit = access_rights.generator_contact

    def GET(self, *args):
        """
        Reset the options for request
        """
        rdb = database(self.db_name)
        if not args:
            self.logger.error('No ids given to option reset of request')
            return dumps({"results": False, "message": "Provide comma-separated ids for option reset!"})
        req_ids = args[0].split(',')
        res = {}
        for req_id in req_ids:
            req = request(rdb.get(req_id))
            req.set_options()
            res[req_id] = True
        return dumps({"results": res})


class GetFragmentForRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'

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
        db = database(self.db_name)
        res = self.get_fragment(db.get(prepid=args[0]), v)
        return dumps(res) if isinstance(res, dict) else res

    def get_fragment(self, data, view):
        try:
            mcm_req = request(json_input=data)
        except request.IllegalAttributeName:
            return {"results": ''}

        fragmentText = mcm_req.get_attribute('fragment')
        if view:
            fragmentHTML = "<pre>"
            fragmentHTML += fragmentText
            fragmentHTML += "</pre>"
            return fragmentHTML
            # fragmentHTML = ""
            # for line in fragmentText.split('\n'):
            #     blanks = ""
            #     while line.startswith(' '):
            #         blanks += "&nbsp;"
            #         line = line[1:]
            #     line = blanks + line
            #     fragmentHTML += line.replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;") + "<br>"
            # return fragmentHTML
        else:
            return fragmentText


class GetSetupForRequest(RESTResource):
    def __init__(self, mode='setup'):
        self.db_name = 'requests'
        self.opt = mode
        if self.opt not in ['setup','test','valid']:
            raise Exception("Cannot create this resource with mode %s"% self.opt)
        if self.opt=='valid':
            self.access_limit = access_rights.administrator

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

        run=False
        do_valid=False
        if self.opt=='test' or self.opt=='valid':
            run=True
        if self.opt=='valid':
            do_valid=True

        db = database(self.db_name)
        if db.document_exists(pid):
            try:
                mcm_req = request(db.get(pid))
            except request.IllegalAttributeName:
                return dumps({"results": False})
            setupText = mcm_req.get_setup_file(run=run,do_valid=do_valid,events=n)
            cherrypy.response.headers['Content-Type'] = 'text/plain'
            return setupText
        else:
            return dumps({"results": False, "message": "%s does not exist" % pid})

class DeleteRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        self.access_limit = access_rights.production_manager

    def DELETE(self, *args):
        """
        Simply delete a request
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": False})
        return dumps(self.delete_request(args[0]))

    def delete_request(self, pid):
        db = database(self.db_name)
        crdb = database('chained_requests')
        adb = database('actions')
        mcm_r = request(db.get( pid))

        if mcm_r.get_attribute('status') != 'new':
            return {"results": False,"message":"Not possible to delete a request (%s) in status %s" %( pid, mcm_r.get_attribute('status'))}

        in_chains = mcm_r.get_attribute('member_of_chain')
        for in_chain in in_chains:
            mcm_cr = chained_request( crdb.get(in_chain) )
            try:
                action_item = mcm_cr.retrieve_original_action_item(adb)
                ## this is a valid action item
                return {"results": False,"message":"Not possible to delete a request (%s) that is part of a valid chain (%s)" %( pid, in_chain)}
            except:
                ## this is not a valid action item
                # further check
                if mcm_cr.get_attribute('chain')[-1]!= pid:
                    ## the pid is not the last of the chain
                    return {"results": False,"message":"Not possible to delete a request (%s) that is not at the end of an invalid chain (%s)" % (pid, in_chain)}
                if mcm_cr.get_attribute('step') == mcm_cr.get_attribute('chain').index( pid ):
                    ## we are currently processing that request
                    return {"results": False,"message":"Not possible to delete a request (%s) that is being the current step (%s) of an invalid chain (%s)" % (pid, mcm_cr.get_attribute('step'), in_chain)}
                ## found a chain that deserves the request to be pop-ep out from the end
                new_chain = mcm_cr.get_attribute('chain')
                new_chain.remove( pid )
                mcm_cr.set_attribute('chain', new_chain)
                mcm_cr.update_history({'action':'remove request', 'step': pid})
                mcm_cr.reload()


        # delete actions !
        self.delete_action(pid)

        # delete chained requests !
        #self.delete_chained_requests(self,pid):

        return {"results": db.delete(pid)}

    def delete_action(self, pid):
        adb = database('actions')
        if adb.document_exists(pid):
            adb.delete(pid)

    def delete_chained_requests(self, pid):
        crdb = database('chained_requests')
        mcm_crs = crdb.queries(['contains==' + pid])
        for doc in mcm_crs:
            crdb.delete(doc['prepid'])

class GetRequestByDataset(RESTResource):
    def __init__(self):   
        pass
    
    def GET(self, *args):
        """
        retrieve the dictionnary of a request, based on the output dataset specified
        """
        if not args: 
            return dumps({"results": {}})
        datasetname = '/'+'/'.join(args).replace('*','')
        rdb =database('requests')
        r=rdb.queries(['produce==%s' % datasetname])
        if len(r):
            return dumps({"results" : r[0]})
        else:
            return dumps({"results": {}})
        
class GetRequestOutput(RESTResource):
    def __init__(self):
        self.db_name = 'requests'
        
    def GET(self, *args):
        """
        Retrieve the list of datasets from a give request
        """
        ## how to structure better the output ? using a dict ?
        main_arg = args[0]
        res = { main_arg : []}
        rdb = database('requests')

        if len(args)>1 and args[1]=='chain':
            collect = []
            crdb = database('chained_requests')
            for cr in crdb.queries(['contains==%s'% main_arg]):
                for r in reversed(cr['chain']):
                    if not r in collect:
                        collect.append(r)
        else:
            collect = [main_arg]

        for rid in collect:
            mcm_r = rdb.get(rid)
            if len(mcm_r['reqmgr_name']):
                if 'pdmv_dataset_list' in mcm_r['reqmgr_name'][-1]['content']:
                    res[main_arg].extend( mcm_r['reqmgr_name'][-1]['content']['pdmv_dataset_list'] )
                else:
                    res[main_arg].append( mcm_r['reqmgr_name'][-1]['content']['pdmv_dataset_name'] )
                
                
        return dumps(res)

class GetRequest(RESTResource):
    def __init__(self):
        self.db_name = 'requests'

    def GET(self, *args):
        """
        Retreive the dictionnary for a given request
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": {}})
        return dumps(self.get_request(args[0]))

    def get_request(self, data):
        db = database(self.db_name)
        if not db.document_exists(data):
            return {"results": {}}
        mcm_r = db.get(prepid=data)
        # cast the sequence for schema evolution !!! here or not ?
        for (i_s, s) in enumerate(mcm_r['sequences']):
            mcm_r['sequences'][i_s] = sequence(s).json()
        return {"results": mcm_r}


class ApproveRequest(RESTResource):

    def GET(self, *args):
        """
        Approve to the next step, or specified index the given request or coma separated list of requests
        """
        if not args:
            return dumps({"results": 'Error: No arguments were given'})
        if len(args) == 1:
            return dumps(self.multiple_approve(args[0]))
        return dumps(self.multiple_approve(args[0], int(args[1])))

    def multiple_approve(self, rid, val=-1, hard=True):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                res.append(self.approve(r, val, hard))
            return res
        else:
            return self.approve(rid, val, hard)

    def approve(self, rid, val=-1,hard=True):
        db = database('requests')
        if not db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given request id does not exist.'}
        req = request(json_input=db.get(rid))

        self.logger.log('Approving request %s for step "%s"' % (rid, val))

        #req.approve(val)
        try:
            if val == 0:
                req.reset(hard)
                saved = db.update(req.json())
            else:
                with locker.lock('{0}-wait-for-approval'.format( rid ) ):
                    req.approve(val)
                    saved = db.update(req.json())

        except request.WrongApprovalSequence as ex:
            return {'prepid': rid, 'results': False, 'message': str(ex)}
        except request.WrongStatusSequence as ex:
            return {"prepid": rid, "results": False, 'message': str(ex)}
        except request.IllegalApprovalStep as ex:
            return {"prepid": rid, "results": False, 'message': str(ex)}
        except:
            return {'prepid': rid, 'results': False, 'message': traceback.format_exc()}
        if saved:
            return {'prepid': rid, 'approval': req.get_attribute('approval'), 'results': True}
        else:
            return {'prepid': rid, 'results': False, 'message': 'Could not save the request after approval'}


class ResetRequestApproval(ApproveRequest):
    def __init__(self,hard=True):
        ApproveRequest.__init__(self)
        self.access_limit = access_rights.generator_contact
        self.hard = hard

    def GET(self, *args):
        """
        Reste both approval and status to their initial state.
        """
        if not args:
            return dumps({"results": 'Error: No arguments were given'})
        return dumps(self.multiple_approve(args[0], 0, self.hard))


class GetStatus(RESTResource):

    def GET(self, *args):
        if not args:
            return dumps({"results": 'Error: No arguments were given'})

        return dumps(self.multiple_status(args[0]))

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
        db = database('requests')
        if not db.document_exists(rid):
            return {"prepid": rid, "results": 'Error: The given request id does not exist.'}

        mcm_r = db.get(rid)
        
        while not 'status' in mcm_r:
            time.sleep(0.5)
            mcm_r = db.get(rid)

        return {rid: mcm_r['status']}


class InspectStatus(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def GET(self, *args):
        """
        Triggers the internal inspection of the status of a request or coma separated list of request
        """
        if not args:
            return dumps({"results": 'Error: No arguments were given'})
        return dumps(self.multiple_inspect(args[0]))

    def multiple_inspect(self, rid):
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
                answer = mcm_r.inspect()
                res.append(answer)
                ### trigger chained request inspection on "true" results from inspection
                if answer['results']:
                    crs = mcm_r.get_attribute('member_of_chain')
                    for cr in crs:
                        if crdb.document_exists( cr ):
                            mcm_cr = chained_request( crdb.get( cr ) )
                            res.append( mcm_cr.inspect() )
                        else:
                            res.append( {"prepid": cr, "results":False, 'message' : '%s does not exist'% cr})
            else:
                res.append({"prepid": r, "results": False, 'message': '%s does not exist' % r})


        if len(res) > 1:
            return res
        else:
            return res[0]


class SetStatus(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Perform the change of status to the next (/ids) or to the specified index (/ids/index)
        """
        if not args:
            return dumps({"results": 'Error: No arguments were given'})
        if len(args) < 2:
            return dumps(self.multiple_status(args[0]))
        return dumps(self.multiple_status(args[0], int(args[1])))

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
            ## set the status with a notification if done via the rest api
            req.set_status(step, with_notification=True)
        except request.WrongStatusSequence as ex:
            return {"prepid": rid, "results": False, 'message': str(ex)}
        except:
            return {"prepid": rid, "results": False, 'message': 'Unknown error' + traceback.format_exc()}

        return {"prepid": rid, "results": db.update(req.json())}


class TestRequest(RESTResource):
    ## a rest api to make a creation test of a request
    def __init__(self):
        self.counter = 0

    def GET(self, *args):
        """ 
        this is test for admins only
        """
        from tools.json import threaded_loads
        import simplejson

        opener = urllib2.build_opener(urllib2.HTTPHandler)
        req = urllib2.Request('http://cms-pdmv-mcmdev:5984/requests/_design/requests/_view/all?include_docs=true')
        req.add_header('Content-Type', 'application/json')
        final = opener.open(req).read()

        return simplejson.dumps(threaded_loads(final)["rows"])

        #a = []
        #rdb = database('requests')
        #for i in args:
        #    mcm_r = request(rdb.get(i))
        #    old_prio = int(mcm_r.get_attribute('priority'))
        #    a.append({i : mcm_r.change_priority(6500)})
        #    mcm_r.change_priority(old_prio)
        #return dumps(a)
        #rdb = database('requests')
        #
        #mcm_r = request( rdb.get(args[0]))
        #
        #def get_procString( mcm_r ):
        #    proc= ""
        #    if mcm_r.get_attribute('process_string') :
        #        proc="_%s"%mcm_r.get_attribute('process_string')
        #    ext=""
        #    if mcm_r.get_attribute('extension'):
        #        ext="_ext%s"%mcm_r.get_attribute('extension')
        #
        #def get_outputs( mcm_r):
        #    outs=[]
        #    keeps = mcm_r.get_attribute('keep_output')
        #    proc= ""
        #    if mcm_r.get_attribute('process_string') :
        #        proc="_%s"%mcm_r.get_attribute('process_string')
        #    ext=""
        #    if mcm_r.get_attribute('extension'):
        #        ext="_ext%s"%mcm_r.get_attribute('extension')
        #    camp = mcm_r.get_attribute('member_of_campaign')
        #    dsn = mcm_r.get_attribute('dataset_name')
        #    v = mcm_r.get_attribute('version')
        #
        #    for (i,s) in enumerate( mcm_r.get_attribute('sequences')):
        #        if not keeps[i]: continue
        #        gt = s['conditions'].replace('::All','')
        #        tiers = s['datatier']
        #        for t in tiers:
        #            outs.append( '/%s/%s-%s%s%s-v%s/%s' % ( dsn,
        #                                                    camp,
        #                                                    gt,
        #                                                    proc,
        #                                                    ext,
        #                                                    v,
        #                                                    t))
        #    return outs
        #
        #outs= get_outputs( mcm_r )
        #
        ##check for collisions
        #
        #return dumps(outs)



class InjectRequest(RESTResource):
    
    def __init__(self):
        # set user access to administrator
        self.db_name = 'requests'
        self.access_limit = access_rights.production_manager

    def GET(self, *args):
        """
        Perform the thread preparation, injection of a request, or coma separated list of requests.
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})

        ids = args[0].split(',')
        res = []
        for r_id in ids:
            self.logger.log('Forking the injection of request {0} '.format(r_id))
            RequestInjector(prepid=r_id, lock=locker.lock(r_id)).start()
            res.append({"prepid": r_id, "results": True,
                        "message": "The request {0} will be forked unless same request is being handled already" .format(r_id)})
        return dumps(res)


class GetEditable(RESTResource):
    def __init__(self):
        self.db_name = 'requests'

    def GET(self, *args):
        """
        Retreive the fields that are currently editable for a given request id
        """
        if not args:
            self.logger.error('Request/GetEditable: No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})
        return dumps(self.get_editable(args[0]))

    def get_editable(self, prepid):
        db = database(self.db_name)
        request_in_db = request(db.get(prepid=prepid))
        editable = request_in_db.get_editable()
        return {"results": editable}


class GetDefaultGenParams(RESTResource):
    def __init__(self):
        self.db_name = 'requests'

    def GET(self, *args):
        """
        Simply get the schema for the generator parameters object in request.
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})

        return dumps(self.get_default_params(args[0]))

    def get_default_params(self, prepid):
        db = database(self.db_name)
        request_in_db = request(db.get(prepid=prepid))
        request_in_db.update_generator_parameters()
        return {"results": request_in_db.get_attribute('generator_parameters')[-1]}


class NotifyUser(RESTResource):

    def PUT(self):
        """
        Sends the prodived posted text to the user registered to a list of requests request
        """
        data = loads(cherrypy.request.body.read().strip())
        # read a message from data
        message = data['message']
        l_type = locator()
        pids = data['prepids']
        results = []
        rdb = database('requests')

        for pid in pids:
            if not rdb.document_exists(pid):
                results.append({"prepid": pid, "results": False, "message": "%s does not exist" % pid})
                return dumps(results)

            req = request(rdb.get(pid))
            # notify the actors of the request
            
            req.notify('Communication about request %s' % pid,
                       '%s \n\n %srequests?prepid=%s\n'%(message, 
                                                       l_type.baseurl(), 
                                                       pid),accumulate=True)
            # update history with "notification"
            req.update_history({'action': 'notify', 'step': message})
            if not rdb.save(req.json()):
                results.append({"prepid": pid, "results": False, "message": "Could not save %s" % pid})
                return dumps(results)

            results.append({"prepid": pid, "results": True, "message": "Notification send for %s" % pid})
        return dumps(results)


class RegisterUser(RESTResource):

    def GET(self, *args):
        """
        Any person with cern credential can register to a request or a list of requests
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": False, 'message': 'Error: No arguments were given'})
        return dumps(self.multiple_register(args[0]))

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
            return {"prepid": pid, "results": False,
                    'message': "You (%s) are not a registered user to McM, correct this first" % current_user}

        if current_user in request_in_db.get_actors():
            return {"prepid": pid, "results": False,
                    'message': "%s already in the list of people for notification of %s" % (current_user, pid)}

        #self.logger.error('list of users %s'%(request_in_db.get_actors()))
        #self.logger.error('current actor %s'%(current_user))

        request_in_db.update_history({'action': 'register', 'step': current_user})
        rdb.save(request_in_db.json())
        return {"prepid": pid, "results": True, 'message': 'You (%s) are registered to %s' % (current_user, pid)}


class GetActors(RESTResource):

    def GET(self, *args):
        """
        Provide the list of user registered and actors to a given request
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": False, 'message': 'Error: No arguments were given'})
        if len(args) > 1:
            return dumps(self.show_user(args[0], args[1]))
        return dumps(self.show_user(args[0]))

    def show_user(self, pid, what=None):
        rdb = database('requests')
        request_in_db = request(rdb.get(pid))
        if what:
            return request_in_db.get_actors(what=what)
        else:
            return request_in_db.get_actors()


class SearchableRequest(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self, *args):
        """
        Return a document containing several usable values that can be searched and the value can be find. /do will trigger reloading of that document from all requests
        """
        searchable = {}
        for key in ['energy', 'dataset_name', 'status', 'approval', 'extension', 'generators',
                             'member_of_chain', 'pwg', 'process_string', 'mcdb_id', 'prepid', 'flown_with',
                             'member_of_campaign','tags']:
            searchable[key] = []
        return dumps(searchable)


class SearchRequest(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def PUT(self, *args):
        """
        Search requests according to the search json provided for wild search
        """
        search_dict = loads(cherrypy.request.body.read().strip())
        self.logger.error("Got a wild search dictionary %s" % ( str(search_dict) ))

        output_object = 'requests'
        if len(args):
            output_object = args[0]

        wild_search_dict = {}
        reg_queries = []
        rdb = database('requests')
        query = rdb.construct_lucene_query(search_dict)
        self.logger.error("lucenese query: %s" % ( str(query) ))
        results = rdb.full_text_search('search', query)

        if output_object == 'chained_requests':
            crdb = database('chained_requests')
            cr_ids = set()
            for r in results:
                for cr in r['member_of_chain']:
                    if crdb.document_exists(cr):
                        cr_ids.add(cr)
            cr_results = []
            for cr in sorted(cr_ids):
                cr_results.append(crdb.get(cr))
            return dumps({"results": cr_results})

        return dumps({"results": results})


class RequestPerformance(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def PUT(self, *args):
        """
        Upload performance report .xml : retrieve size_event and time_event
        """
        self.logger.error("Got a performance file from uploading %s" % (str(args)))
        if len(args) != 2:
            return dumps({"results": False, "message": "not enough arguments"})
        rdb = database('requests')
        rid = args[0]
        if not rdb.document_exists(rid):
            return dumps({"results": False, "message": "%s does not exist" % rid})

        what = args[1]
        if not what in ["perf", "eff"]:
            return dumps({"results": False, "message": "%s is not a valid option" % what})

        xml_doc = cherrypy.request.body.read()

        ## then get the request ID and update it's value
        mcm_r = request(rdb.get(rid))
        to_be_saved = mcm_r.update_performance(xml_doc, what)

        if to_be_saved:
            saved = rdb.update(mcm_r.json())
            if saved:
                return dumps({"results": True, "prepid": rid})
            else:
                return dumps({"results": False, "prepid": rid})
        else:
            return dumps({"results": False, "prepid": rid})


class RequestLister():
    def __init__(self):
        pass 

    def get_objects(self, all_ids, retrieve_db):
        all_objects = []
        if len(all_ids) and retrieve_db:
            for oid in all_ids:
                if retrieve_db.document_exists(oid):
                    all_objects.append(retrieve_db.get(oid))

        self.logger.error("Got %s ids identified" % ( len(all_objects)))
        return {"results": all_objects}

    def identify_an_id(self, word, in_range_line, cdb, odb):
        all_campaigns = map(lambda x: x['id'], cdb.raw_query("prepid"))
        if word.count('-') == 2:
            (pwg, campaign, serial) = word.split('-')
            if len(pwg) != 3:
                return None
            if not serial.isdigit():
                return None
            if not campaign in all_campaigns:
                return None
            if odb.document_exists(word):
                return word
            elif in_range_line:
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

    def get_list_of_ids(self, odb):
        self.logger.error("Got a file from uploading")
        data = loads(cherrypy.request.body.read().strip())
        text = data['contents']

        all_ids = []
        all_dsn = {}
        ## parse that file for prepids
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
                    if not possible_campaign in all_dsn:
                        all_dsn[possible_campaign] = []

                ## is that a prepid ?
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
                            all_ids.append('-'.join(id_start.split('-')[0:2] + ['%05d' % serial]))

        for (possible_campaign, possible_dsn) in all_dsn.items():
            #self.logger.error("Found those dsn to look for %s"%(possible_dsn))
            if not cdb.document_exists(possible_campaign):
                continue
                ## get all requests
            all_requests = odb.queries(['member_of_campaign==%s' % possible_campaign])
            for request in all_requests:
                if request['dataset_name'] in possible_dsn:
                    all_ids.append(request['prepid'])

        all_ids = list(set(all_ids))
        all_ids.sort()
        return all_ids


class RequestsFromFile(RequestLister, RESTResource):
    def __init__(self):
        RequestLister.__init__(self)
        self.access_limit = access_rights.user

    def PUT(self, *args):
        """
        Parse the posted text document for request id and request ranges for display of requests
        """
        rdb = database('requests')
        all_ids = self.get_list_of_ids(rdb)
        return dumps(self.get_objects(all_ids, rdb))


class StalledReminder(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Collect the requests that have been running for too long (/since) or will run for too long (/since/remaining) and send a reminder. 
        """
        time_since=15
        time_remaining=15
        if len(args)>0:
            time_since=args[0]
        if len(args)>1:
            time_remaining=args[1]
        rdb = database('requests')
        bdb = database('batches')
        rs = rdb.queries(['status==submitted'])
        today = time.mktime( time.gmtime())
        subject="Gentle reminder of requests that appear stalled"
        text="The following requests appear to be not progressing since %s days or will require more than %s days to complete:\n\n"%( time_since, time_remaining)
        reminded=0
        by_batch=defaultdict(list)
        for r in rs:
            date_s = filter( lambda h : 'step' in h and h['step']=='submitted', r['history'])[-1]['updater']['submission_date']
            date= time.mktime( time.strptime(date_s, "%Y-%m-%d-%H-%M"))
            elapsed_t = (today-date)
            elapsed=(today-date)/60./60./24. #in days
            remaining=float("inf")
            if r['completed_events']:
                remaining_t = (elapsed_t * ((r['total_events'] / float(r['completed_events']))-1))
                remaining = remaining_t /60./60./24.
                if remaining<0: ## already over stats
                    remaining=0.
            if (remaining>time_remaining and remaining!=float('Inf')) or (elapsed>time_since and remaining!=0):
                reminded+=1
                bs = bdb.queries(['contains==%s'%r['prepid'],'status==announced'])
                ## take the last one ?
                in_batch = 'NoBatch'
                if len (bs):
                    in_batch = bs[-1]['prepid']

                line="%30s: %4.1f days since submission: %8s = %5.1f%% completed, remains %6.1f days, priority %s \n"%( r['prepid'],
                                                                                                                          elapsed,
                                                                                                                          r['completed_events'],
                                                                                                                          r['completed_events']*100./r['total_events'],
                                                                                                                          remaining,
                                                                                                                          r['priority'])
                by_batch[in_batch].append(line)
        l_type = locator()
        for (b,lines) in by_batch.items():
            text+="In batch %s:\n"%b
            text+='%sbatches?prepid=%s\n'%( l_type.baseurl(), b)
            for line in lines:
                text+=line
            text+='\n'
        text+="\nAttention might be required\n"
        com = communicator()

        udb = database('users')
        production_managers = udb.queries(['role==production_manager'])
        if reminded!=0:
            com.sendMail(map(lambda u: u['email'], production_managers) + [settings().get_value('service_account')],
                         subject, text)
        

class RequestsReminder(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Goes through all requests and send reminder to whom is concerned. /production_manager for things to be submitted. /generator_convener for things to be approved. /generator_contact for things to be looked at by /generator_contact/contact (if specified)
        """
        what = None
        who = None
        if len(args):
            #we have been passed parameters
            what = args[0].split(',')
            if 'all' in what:
                what = None

            if len(args)>=2:
                who = args[1].split(',')

        udb = database('users')
        rdb = database('requests')
        crdb = database('chained_requests')

        #all_requests = rdb.queries([])
        # a dictionary  campaign : [ids]
        ids_for_production_managers = {}
        # a dictionary  campaign : [ids]
        ids_for_gen_conveners = {}
        # a dictionary contact : { campaign : [ids] }
        ids_for_users = {}

        res = []
        ## fill up the reminders
        def get_all_in_status(status, extracheck=None):
            campaigns_and_ids = {}
            for mcm_r in rdb.queries(['status==%s' % status]):
                ## check whether it has a valid action before to add them in the reminder
                c = mcm_r['member_of_campaign']
                if not c in campaigns_and_ids:
                    campaigns_and_ids[c] = set()
                if extracheck is None or extracheck(mcm_r):
                    campaigns_and_ids[c].add(mcm_r['prepid'])

            #then remove the empty entries, and sort the others
            for c in campaigns_and_ids.keys():
                if not len(campaigns_and_ids[c]):
                    campaigns_and_ids.pop(c)
                else:
                    campaigns_and_ids[c] = sorted( campaigns_and_ids[c] )

            return campaigns_and_ids

        com = communicator()
        l_type = locator()

        def count_entries(campaigns_and_ids):
            s=0
            for (camp, ids) in campaigns_and_ids.items():
                s+=len(ids)
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
                    message += '\t%s (%s) (%d chains) (prio %s) \n' % ( rid, 
                                                                     req.get_attribute('dataset_name'),
                                                                     len(req.get_attribute('member_of_chain')),
                                                                     req.get_attribute('priority'))
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
                com.sendMail(map(lambda u: u['email'], production_managers) + [settings().get_value('service_account')],
                             'Gentle reminder on %s requests to be submitted'%( count_entries(ids_for_production_managers)),
                             message)

        if not what or 'gen_conveners' in what or 'generator_convener' in what:
        ## send the reminder to generator conveners
            ids_for_gen_conveners = get_all_in_status('defined')
            for c in ids_for_gen_conveners:
                res.extend(map(lambda i: {"results": True, "prepid": i}, ids_for_gen_conveners[c]))
            if len(ids_for_gen_conveners):
                gen_conveners = udb.queries(['role==generator_convener'])
                message = 'A few requests need your approvals \n\n'
                message += prepare_text_for(ids_for_gen_conveners, 'defined')
                com.sendMail(map(lambda u: u['email'], gen_conveners) + [settings().get_value('service_account')],
                             'Gentle reminder on %s requests to be approved by you'%(count_entries(ids_for_gen_conveners)),
                             message)

        if not what or 'gen_contact' in what or 'generator_contact' in what:
            all_ids = set()
            ## remind the gen contact about requests that are:
            ##   - in status new, and have been flown
            mcm_rs = rdb.queries(['status==new'])
            mcm_rs.extend(rdb.queries(['status==validation']))
            for mcm_r in mcm_rs:
                c = mcm_r['member_of_campaign']
                rid = mcm_r['prepid']
                if not 'flown_with' in mcm_r: continue # just because in -dev it might be the case
                fw = mcm_r['flown_with']
                # to get a remind only on request that are in a chain (including flown by construction)
                if len(mcm_r['member_of_chain'])==0: continue
                # to get a remind only on request that are being necessary to move forward : being the request being processed in at least a chain.
                on_going=False
                for in_chain in mcm_r['member_of_chain']:
                    mcm_cr = chained_request( crdb.get( in_chain ) )
                    if mcm_cr.get_attribute('chain')[mcm_cr.get_attribute('step')] == rid:
                        on_going=True
                        break
                if not on_going: continue

                all_involved = request(mcm_r).get_actors()
                for contact in all_involved:
                    if not contact in ids_for_users:
                        ids_for_users[contact]={}
                    
                    if not c in ids_for_users[contact]:
                        ids_for_users[contact][c] = set()
                    ids_for_users[contact][c].add( rid )
                    
            #then remove the non generator
            gen_contacts = map(lambda u : u['username'], udb.queries(['role==generator_contact']))
            for contact in ids_for_users.keys():
                if who and not contact in who:
                    ids_for_users.pop( contact )
                    continue
                if contact not in gen_contacts: 
                    # not a contact
                    ids_for_users.pop( contact )
                    continue

                for c in ids_for_users[contact].keys():
                    if not len(ids_for_users[contact][c]):
                        ids_for_users[contact].pop(c)
                    else:
                        ids_for_users[contact][c] = sorted( ids_for_users[contact][c] )
                    #for serialization only in dumps
                    #ids_for_users[contact][c] = list( ids_for_users[contact][c] )
                
                #if there is nothing left. remove
                if not len( ids_for_users[contact].keys() ):
                    ids_for_users.pop( contact )
                    continue

            if len(ids_for_users):
                for (contact, campaigns_and_ids) in ids_for_users.items():
                    for c in campaigns_and_ids:
                        all_ids.update( campaigns_and_ids[c] )

                    mcm_u = udb.get( contact )
                    if len(campaigns_and_ids):
                        message = 'Few requests need your action \n\n'
                        message += prepare_text_for(campaigns_and_ids, '')
                        to_who=[settings().get_value('service_account')]
                        if l_type.isDev():
                            message += '\nto %s' %( mcm_u['email'] )
                        else:
                            to_who.append( mcm_u['email'] )
                        name=contact
                        if mcm_u['fullname']:
                            name=mcm_u['fullname']
                        com.sendMail(to_who,
                                     'Gentle reminder on %s requests to be looked at by %s'% (count_entries(campaigns_and_ids),name),
                                     message
                                     )
                res = map (lambda i : {"results": True, "prepid": i}, all_ids)
        return dumps(res)


class UpdateMany(RequestRESTResource):
    def __init__(self):
        self.db_name = 'requests'
        RequestRESTResource.__init__(self)
        self.updateSingle = UpdateRequest()

    def PUT(self):
        """
        Updating an existing multiple requests with an updated dictionnary
        """
        return dumps(self.update_many(loads(cherrypy.request.body.read().strip())))

    def update_many(self, data):
        list_of_prepids = data["prepids"]
        updated_values = data["updated_data"]
        return_info = []
        db = database(self.db_name)
        for elem in list_of_prepids:
            document = db.get(elem)
            for value in updated_values:
                if value in ['generator_parameters','sequences']:
                    document[value] = updated_values[value]
                elif isinstance(updated_values[value],list):
                    temp = updated_values[value]
                    temp.extend(document[value])
                    document[value] = list(set(temp))
                else:
                    document[value] = updated_values[value]
            return_info.append(self.updateSingle.update_request(dumps(document)))
        self.logger.log('updating requests: %s' % return_info)
        return {"results": return_info}


class GetAllRevisions(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)
        self.db_url = locator().dbLocation()
        self.opener = urllib2.build_opener(urllib2.HTTPHandler)
        self.db_name = 'requests'

    def GET(self, *args):
        """
        Getting All AVAILABLE revisions for request document
        """
        if not args:
            self.logger.error('GetAllRevisions: No arguments were given')
            return dumps({"results": False, 'message': 'Error: No arguments were given'})
        return dumps(self.get_all_revs(args[0]))

    def get_all_revs(self, prepid):
        list_of_revs = []
        doc_id = prepid
        all_revs_url = self.db_url+"/"+self.db_name+"/"+doc_id+"?revs_info=true"
        single_rev_url = self.db_url+"/"+self.db_name+"/"+doc_id+"?rev="
        http_request = urllib2.Request(all_revs_url)
        http_request.add_header('Content-Type', 'text/plain')
        http_request.get_method = lambda : 'GET'
        result = self.opener.open(http_request)
        revision_data = loads(result.read())
        for revision in revision_data["_revs_info"]:
            if revision["status"] == "available":
                single_request = urllib2.Request(single_rev_url+revision["rev"])
                single_request.add_header('Content-Type', 'text/plain')
                single_request.get_method = lambda : 'GET'
                single_result = self.opener.open(single_request)
                single_doc = single_result.read()
                list_of_revs.append(loads(single_doc))
        self.logger.log('Getting all revisions for: %s' % doc_id)
        return {"results": list_of_revs}


class ListRequestPrepids(RequestRESTResource):
    def __init__(self):
        RequestRESTResource.__init__(self)
        self.db_name = 'requests'
        self.db = database('requests')

    def GET(self, *args):
        """
        List all prepids by given key(-s)
        """
        if not args:
            self.logger.error(' No arguments were given')
            return dumps({"results": False, 'message': 'Error: No arguments were given'})
        if len(args) >= 2:
            return dumps(self.get_all_prepids(args[0], args[1]))
        else:
            return dumps(self.get_all_prepids(args[0]))

    def get_all_prepids(self, view, key=None):
        view_name = view
        if key:
            result = self.db.raw_query(view_name, {'key': key})
            self.logger.log('All list raw_query view:%s searching for: %s' %(view_name, key))
        else:
            result = self.db.raw_query(view_name)
            self.logger.log('All list raw_query view:%s searching for all' %(view_name))
        data = [key['value'] for key in result]
        return {"results": data}


class GetUploadCommand(RESTResource):

    def __init__(self):
        self.access_limit = access_rights.production_manager

    def GET(self, *args):
        """
        Get command used to upload configurations for given request.
        """
        if not len(args):
            self.logger.error('GetUploadCommand: No arguments were given')
            return dumps({"results": False, 'message': 'Error: No arguments were given'})
        db = database("requests")
        if not db.document_exists(args[0]):
            self.logger.error('GetUploadCommand: request with id {0} does not exist'.format(args[0]))
            return dumps({"results": False, 'message': 'Error: request with id {0} does not exist'.format(args[0])})
        req = request(db.get(args[0]))
        cherrypy.response.headers['Content-Type'] = 'text/plain'

        return req.prepare_and_upload_config(execute=False)


class GetInjectCommand(RESTResource):

    def __init__(self):
        self.access_limit = access_rights.production_manager

    def GET(self, *args):
        """
        Get command used to inject given request.
        """
        if not len(args):
            self.logger.error('GetInjectCommand: No arguments were given')
            return dumps({"results": False, 'message': 'Error: No arguments were given'})
        db = database("requests")
        if not db.document_exists(args[0]):
            self.logger.error('GetInjectCommand: request with id {0} does not exist'.format(args[0]))
            return dumps({"results": False, 'message': 'Error: request with id {0} does not exist'.format(args[0])})
        req = request(db.get(args[0]))
        batch_name = BatchPrepId().next_id(req.json(), create_batch=False)
        cherrypy.response.headers['Content-Type'] = 'text/plain'

        return req.prepare_submit_command(batch_name)


class GetUniqueValues(RESTResource):
    def GET(self, *args):
        """
        Get unique values for navigation by field_name
        """
        if not args:
            self.logger.error('GetUniqueValues: No arguments were given')
            return dumps({"results": False, 'message': 'Error: No arguments were given'})
        return dumps(self.get_unique_values(args[0]))

    def get_unique_values(self, field_name):
        db = database('requests')
        data = db.raw_view_query(view_doc="unique", view_name=field_name, options={"group":True})
        unique_list = [str(elem["key"]) for elem in data]
        return {"results": unique_list}
