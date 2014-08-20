#!/usr/bin/env python

import cherrypy
from json import dumps
from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResource
from ChainedRequestPrepId import ChainedRequestPrepId
from json_layer.chained_request import chained_request
from json_layer.chained_campaign import chained_campaign
from json_layer.request import request
from json_layer.action import action
from json_layer.batch import batch
from tools.user_management import access_rights
from tools.json import threaded_loads
import traceback

"""
## import the rest api for wilde request search and dereference to chained_requests using member_of_chain
class SearchChainedRequest(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        self.getter

    def PUT(self):
"""        


class CreateChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'
        self.access_limit = access_rights.administrator

    def PUT(self):
        """
        Create a chained request from the provided json content
        """
        return dumps(self.import_request(cherrypy.request.body.read().strip()))

    def import_request(self, data):
        db = database(self.db_name)
        json_input=threaded_loads(data)
        if 'pwg' not in json_input or 'member_of_campaign' not in json_input:
            self.logger.error('Now pwg or member of campaign attribute for new chained request')
            return {"results":False}
        if 'prepid' in json_input:
            req = chained_request(json_input)
            cr_id = req.get_attribute('prepid')
        else:
            cr_id = ChainedRequestPrepId().next_id(json_input['pwg'], json_input['member_of_campaign'])
            if not cr_id:
                return {"results":False}
            req = chained_request(db.get(cr_id))

        for key in json_input:
            if key not in ['prepid', '_id', '_rev', 'history']:
                req.set_attribute(key, json_input[key])

        if not req.get_attribute('prepid'):
            self.logger.error('prepid returned was None')
            raise ValueError('Prepid returned was None')


        self.logger.log('Created new chained_request %s' % cr_id)

        # update history with the submission details
        req.update_history({'action': 'created'})

        return self.save_request(db, req)

    def save_request(self, db, req):
        if not db.document_exists(req.get_attribute('_id')):
            if db.save(req.json()):
                self.logger.log('new chained_request successfully saved.')
                return {"results":True, "prepid": req.get_attribute('prepid')}
            else:
                self.logger.error('Could not save new chained_request to database')
                return {"results":False}
        else:
            if db.update(req.json()):
                self.logger.log('new chained_request successfully saved.')
                return {"results":True, "prepid": req.get_attribute('prepid')}
            else:
                self.logger.error('Could not save new chained_request to database')
                return {"results":False}

class UpdateChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'
        self.access_limit = access_rights.administrator

    def PUT(self):
        """
        Update a chained request from the provided json content
        """
        return dumps(self.update_request(cherrypy.request.body.read().strip()))

    def update_request(self, data):
        try:
            req = chained_request(json_input=threaded_loads(data))
        except chained_request.IllegalAttributeName as ex:
            return {"results":False}

        if not req.get_attribute('prepid') and not req.get_attribute('_id'):
            self.logger.error('prepid returned was None') 
            raise ValueError('Prepid returned was None')
            #req.set_attribute('_id', req.get_attribute('prepid')

        self.logger.log('Updating chained_request %s' % (req.get_attribute('_id')))
        self.logger.log('wtf %s'%(str(req.get_attribute('approval'))))
        # update history
        req.update_history({'action': 'update'})

        return self.save_request(req)

    def save_request(self, req):
        db = database(self.db_name)
        return {"results": db.update(req.json())}


class DeleteChainedRequest(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def DELETE(self, *args):
        """
        Simply delete a chained requests
        """
        if not args:
            return dumps({"results":False})
        return dumps(self.delete_request(args[0]))

    def delete_request(self, crid):

        crdb = database('chained_requests')
        rdb = database('requests')
        adb = database('actions')
        mcm_cr = chained_request(crdb.get(crid))
        mcm_a = None
        ## get all objects
        mcm_r_s=[]
        for (i,rid) in enumerate(mcm_cr.get_attribute('chain')):
            mcm_r = request(rdb.get(rid))
            #this is not a valid check as it is allowed to remove a chain around already running requests
            #    if mcm_r.get_attribute('status') != 'new':
            #        return {"results":False,"message" : "the request %s part of the chain %s for action %s is not in new status"%( mcm_r.get_attribute('prepid'),
            #                                                                                                                             crid,
            #                                                                                                                             mcm_a.get_attribute('prepid'))}
            in_chains = mcm_r.get_attribute('member_of_chain')
            in_chains.remove( crid )
            mcm_r.set_attribute('member_of_chain', in_chains)
            if i==0:
                # the root is the action id
                mcm_a = action(adb.get(rid))
                if len(in_chains)==0 and mcm_r.get_attribute('status')!='new':
                    return {"results":False,"message" : "the request %s, not in status new, at the root of the chain will not be chained anymore"% rid}
            else:
                if len(in_chains)==0:
                    return {"results":False,"message" : "the request %s, not at the root of the chain will not be chained anymore"% rid}

            mcm_r.update_history({'action':'leave','step':crid})
            mcm_r_s.append( mcm_r )

        ## check if possible to get rid of it !
        # action for the chain is disabled
        chains = mcm_a.get_chains( mcm_cr.get_attribute('member_of_campaign'))
        if chains[crid]['flag']:
            return {"results":False,"message" : "the action %s for %s is not disabled"%(mcm_a.get_attribute('prepid'), crid)}
        #take it out
        mcm_a.remove_chain(  mcm_cr.get_attribute('member_of_campaign'), mcm_cr.get_attribute('prepid') )

        if not adb.update( mcm_a.json()):
            return {"results":False,"message" : "Could not save action "+ mcm_a.get_attribute('prepid')}
        ## then save all changes
        for mcm_r in mcm_r_s:
            if not rdb.update( mcm_r.json()):
                return {"results":False,"message" : "Could not save request "+ mcm_r.get_attribute('prepid')}
            else:
                mcm_r.notify("Request {0} left chain".format( mcm_r.get_attribute('prepid')),
                             "Request {0} has successfuly left chain {1}".format( mcm_r.get_attribute('prepid'), crid))

        return {"results": crdb.delete(crid)}


class GetChainedRequest(RESTResource):
    def __init__(self):
        self.db_name = 'chained_requests'

    def GET(self, *args):
        """
        Retrieve the content of a chained request id
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":{}})
        return dumps(self.get_request(args[0]))

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
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def PUT(self):
        """
        Allows to flow a chained request with the dataset and blocks provided in the json 
        """
        return dumps(self.flow2(cherrypy.request.body.read().strip()))

    def GET(self, *args):
        """
        Allow to flow a chained request with internal information
        """
        if not args:
            self.logger.error('No arguments were given.')
            return dumps({"results":'Error: No arguments were given.'})
        check_stats=True
        reserve = False
        if len(args)>1:
            check_stats=(args[1]!='force')
            self.logger.log(args)
            reserve = args[1]=='reserve'
        return dumps(self.multiple_flow(args[0], check_stats, reserve))

    def multiple_flow(self, rid, check_stats=True, reserve=False):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                 res.append(self.flow(r, check_stats=check_stats, reserve = reserve))
            return res
        else:
            return self.flow(rid, check_stats=check_stats, reserve = reserve)

    def flow2(self,  data):
        try:
            vdata = threaded_loads(data)
        except ValueError as ex:
            self.logger.error('Could not start flowing to next step. Reason: %s' % (ex)) 
            return {"results":str(ex)}
        db = database('chained_requests')
        try:
            creq = chained_request(json_input=db.get(vdata['prepid']))
        except Exception as ex:
            self.logger.error('Could not initialize chained_request object. Reason: %s' % (ex))
            return {"results":str(ex)}

        self.logger.log('Attempting to flow to next step for chained_request %s' %  (creq.get_attribute('_id')))

        # if the chained_request can flow, do it
        inputds = ''
        inblack = []
        inwhite = []
        if 'input_dataset' in vdata:
            inputds = vdata['input_dataset']
        if 'block_black_list' in vdata:
            inblack = vdata['block_black_list']
        if 'block_white_list' in vdata:
            inwhite = vdata['block_white_list']
        if 'force' in vdata:
            check_stats = vdata['force']!='force'
        if 'reserve' in vdata and vdata["reserve"]:
            return creq.reserve()
        return creq.flow_trial( inputds,  inblack,  inwhite, check_stats)

    def flow(self, chainid, check_stats=True, reserve = False):
        try:
            db = database('chained_requests')
            creq = chained_request(json_input=db.get(chainid))
        except Exception as ex:
            self.logger.error('Could not initialize chained_request object. Reason: %s' % (ex)) 
            return {"results":str(ex)}


        # if the chained_request can flow, do it
        if reserve:
            self.logger.log('Attempting to reserve to next step for chained_request %s' %  (creq.get_attribute('_id')))
            return creq.reserve()
        self.logger.log('Attempting to flow to next step for chained_request %s' %  (creq.get_attribute('_id')))
        return creq.flow_trial(check_stats=check_stats)

class RewindToPreviousStep(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def GET(self,  *args):
        """
        Rewind the provided coma separated chained requests of one step.
        """
        if not len(args):
            return dumps({"results":False})

        res=[]

        crids=args[0].split(",")
        for crid in crids:
            res.append( self.rewind_one( crid ) )

        if len(res)!=1:
            return dumps(res)
        else:
            return dumps(res[0])

    def rewind_one(self, crid):
        crdb = database('chained_requests')
        rdb = database('requests')
        if not crdb.document_exists( crid ):
            return {"results":False, "message":"does not exist","prepid" : crid}
        mcm_cr = chained_request( crdb.get( crid) )
        current_step = mcm_cr.get_attribute('step')
        if current_step==0:
            ## or should it be possible to cancel the initial requests of a chained request
            return {"results":False, "message":"already at the root","prepid" : crid}

        ## supposedly all the other requests were already reset!
        for next in mcm_cr.get_attribute('chain')[current_step+1:]:
            ## what if that next one is not in the db
            if not rdb.document_exists( next):
                self.logger.error('%s is part of %s but does not exist'%( next, crid))
                continue
            mcm_r = request(rdb.get( next ))
            if mcm_r.get_attribute('status')!='new':
                # this cannot be right!
                self.logger.error('%s is after the current request and is not new: %s' %( next, mcm_r.get_attribute('status')))
                return {"results":False, "message":"%s is not new"%(next),"prepid" : crid}

        ##get the one to be reset
        current_id=mcm_cr.get_attribute('chain')[current_step]
        mcm_r = request( rdb.get( current_id ))
        mcm_r.reset()
        saved = rdb.update( mcm_r.json() )
        if not saved:
            {"results":False, "message":"could not save the last request of the chain","prepid" : crid}
        ## the current chained request has very likely been updated : reload it as you have not changed anything to it yet
        mcm_cr = chained_request( crdb.get( crid) )

        mcm_cr.set_attribute('step',current_step -1 )
        # set status, last status
        mcm_cr.set_last_status()
        mcm_cr.set_attribute('status','processing')

        saved = crdb.update( mcm_cr.json())
        if saved:
            return {"results":True,"prepid" : crid}
        else:
            return {"results":False, "message":"could not save chained requests. the DB is going to be inconsistent !","prepid" : crid}
        

class ApproveRequest(RESTResource):
    def __init__(self):
        self.acces_limit = 3 

    def GET(self,  *args):
        """
        move the chained request approval to the next step
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results":'Error: No arguments were given'})
        if len(args) == 1:
                return dumps(self.multiple_approve(args[0]))
        return dumps(self.multiple_approve(args[0], int(args[1])))

    def multiple_approve(self, rid, val=-1):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                 res.append(self.approve(r, val))
            return res
        else:
            return self.approve(rid, val)

    def approve(self,  rid,  val=-1):
        db = database('chained_requests')
        if not db.document_exists(rid):
            return {"prepid": rid, "results":'Error: The given chained_request id does not exist.'}
        creq = chained_request(json_input=db.get(rid))
        try:
            creq.approve(val)
        except Exception as ex:
            return {"prepid": rid, "results":False, 'message' : str(ex)} 

        saved = db.update(creq.json())
        if saved:
            return {"prepid":rid, "results":True}
        else:
            return {"prepid":rid, "results":False , 'message': 'unable to save the updated chained request'}


class InspectChain(RESTResource):
    def __init__(self):
        self.acces_limit = 3

    def GET(self, *args):
        """
        Inspect a chained request for next action
        """
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return dumps(self.multiple_inspect(args[0]))

    def multiple_inspect(self, crid):
        crlist=crid.rsplit(',')
        res = []
        crdb = database('chained_requests')
        for cr in crlist:
            if crdb.document_exists( cr):
                mcm_cr = chained_request( crdb.get( cr) )
                res.append( mcm_cr.inspect() )
            else:
                res.append( {"prepid": cr, "results":False, 'message' : '%s does not exist'% cr})

        if len(res)>1:
            return res
        else:
            return res[0]

class GetConcatenatedHistory(RESTResource):
    def __init__(self):
        self.acces_limit = 1

    def GET(self, *args):
        if not args:
            return dumps({"results": 'Error: No arguments were given'})
        return dumps(self.concatenate_history(args[0]))

    def concatenate_history(self, id_string):
        res = {}
        tmp_history = {}
        crdb = database('chained_requests')
        rdb = database('requests')
        id_list = id_string.split(',')
        for elem in id_list: ##get data for single chain -> save in tmp_hist key as chain_id ???
            tmp_history[elem] = []
            chain_data = crdb.get(elem)
            #/get request and then data!
            for request in chain_data["chain"]:
                request_data = rdb.get(request)
                tmp_data = request_data["history"]
                try:
                    if tmp_data[0]["step"] != "new":  #we set 1st step to new -> so graph would not ignore undefined steps: clone, <flown> step, migrated
                        tmp_data[0]["step"] = "new"
                except:
                    tmp_data[0]["step"] = "new"

                for step in tmp_data:
                    step["request_id"] = request_data["prepid"]
                    tmp_history[elem].append(step)
        return {"results":tmp_history, "key": id_string}

class SearchableChainedRequest(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self, *args):
        """
        Return a document containing several usable values that can be searched and the value can be find. /do will trigger reloading of that document from all requests
        """
        rdb = database('chained_requests')
        if len(args) and args[0] == 'do':
            all_requests = rdb.queries([])

            searchable = {}

            for request in all_requests:
                for key in ["prepid", "approval", "status", "pwg", "step",
                            "last_status", "member_of_campaign", "dataset_name"]:
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
            if search.document_exists('chained_requests'):
                search.delete('chained_requests')
            searchable.update({'_id': 'chained_requests'})
            search.save(searchable)
            searchable.pop('_id')
            return dumps(searchable)
        else:
            ## just retrieve that value
            search = database('searchable')
            searchable = search.get('chained_requests')
            searchable.pop('_id')
            searchable.pop('_rev')
            return dumps(searchable)

class TestChainedRequest(RESTResource):  
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args): 
        """
        Perform test for chained requests    
        """
        
        from tools.handlers import Handler
        class RunChainValid(Handler):
            """
            Operate the full testing of a chained request
            """
            def __init__(self, **kwargs):
                Handler.__init__(self, **kwargs)
                self.crid = kwargs['crid']

            def reset_all(self, message, what = 'Chained validation run test', notify_one=None):
                crdb = database('chained_requests')
                rdb = database('requests')
                mcm_cr = chained_request(crdb.get(self.crid))
                for rid in mcm_cr.get_attribute('chain'):
                    mcm_r = request( rdb.get( rid ) )
                    notify = True
                    if notify_one and notify_one != rid:
                        notify = False
                    mcm_r.test_failure( message, 
                                        what = what,
                                        rewind=True,
                                        with_notification=notify)

            def internal_run(self):
                from tools.installer import installer
                from tools.batch_control import batch_control 
                location = installer( self.crid, care_on_existing=False, clean_on_exit=True)
                try:
                    crdb = database('chained_requests')
                    rdb = database('requests')
                    mcm_cr = chained_request(crdb.get(self.crid))
                    mcm_rs = []
                    for rid in mcm_cr.get_attribute('chain'):
                        mcm_rs.append( request( rdb.get( rid ) ))

                    test_script = location.location() + 'validation_run_test.sh'
                    with open(test_script, 'w') as there:
                        there.write(mcm_cr.get_setup(directory=location.location(), run=True, validation=True))
                        
                    batch_test = batch_control( self.crid, test_script )
                    
                    try:
                        success = batch_test.test()
                    except:
                        self.reset_all( traceback.format_exc() )
                        return
                    if not success:
                        self.reset_all( '\t .out \n%s\n\t .err \n%s\n ' % ( batch_test.log_out, batch_test.log_err) )
                        return

                    last_fail=mcm_rs[0]
                    trace=""
                    for mcm_r in mcm_rs:
                        ### if not mcm_r.is_root: continue ##disable for dr request
                        (success,trace) = mcm_r.pickup_all_performance(location.location())
                        if not success: 
                            last_fail = mcm_r
                            break
                    
                    self.logger.error('I came all the way to here and %s (request %s)' % ( success, self.crid ))
                    if success:
                        for mcm_r in mcm_rs:
                            if mcm_r.is_root:
                                mcm_current = request( rdb.get(mcm_r.get_attribute('prepid')))
                                if mcm_current.json()['_rev'] == mcm_r.json()['_rev']:
                                    mcm_r.set_status(with_notification=True)
                                    if not mcm_r.reload():
                                        self.reset_all( 'The request %s could not be saved after the runtest procedure' % (mcm_r.get_attribute('prepid')))
                                        return
                                else:
                                    self.reset_all( 'The request %s has changed during the run test procedure'%(mcm_r.get_attribute('prepid')), notify_one = mcm_r.get_attribute('prepid'))
                                    return
                    else:
                        self.reset_all( trace , notify_one = last_fail.get_attribute('prepid') )
                        return
                except:
                    mess = 'We have been taken out of run_safe of runtest_genvalid for %s because \n %s \n During an un-excepted exception. Please contact support.' % (
                        self.crid, traceback.format_exc())
                    self.logger.error(mess)
                finally:
                    location.close()

        ## now in the core of the api
        from tools.locker import locker
        runtest = RunChainValid( crid= args[0] )

        crdb = database('chained_requests')
        rdb = database('requests')
        mcm_cr = chained_request(crdb.get(args[0]))
        mcm_rs = []
        for rid in mcm_cr.get_attribute('chain'):
            mcm_r = request( rdb.get( rid ) )
            if not mcm_r.is_root: continue
            try:
                mcm_r.ok_to_move_to_approval_validation(for_chain=True)
                mcm_r.update_history({'action': 'approve', 'step':'validation'})
                mcm_r.set_attribute('approval','validation')
                mcm_r.notify('Approval validation in chain for request %s'%(mcm_r.get_attribute('prepid')),
                             mcm_r.textified(), accumulate=True)
                mcm_r.reload()
            except Exception as e:
                runtest.reset_all( str(e) , notify_one = rid )
                return dumps({"results" : False, "message" : str(e)})
                
        runtest.start()
        return "run test started"
        
"""
        rdb = database('requests')
        mcm_rs=[]
        for rn in mcm_cr.get_attribute('chain'):
            mcm_rs.append( request( rdb.get( rn )))
        
        for mcm_r in mcm_rs:
            mcm_r.set_attribute('status', 'approved')
            mcm_r.reload()
"""

class InjectChainedRequest(RESTResource):
    def __init__(self, mode='show'):
        self.access_limit = access_rights.production_manager
        self.mode = mode
        if self.mode not in ['inject','show']:
            raise Exception("%s not allowed"%( self.mode))

    def GET(self, *args):
        """                       
        Provides the injection command and does the injection.
        """
        crn= args[0]
        crdb = database('chained_requests')
        mcm_cr = chained_request(crdb.get(crn))
        rdb = database('requests')
        mcm_rs=[]
        ## upload all config files to config cache, with "configuration economy" already implemented
        from tools.locker import locker
        from tools.handlers import ConfigMakerAndUploader
        for rn in mcm_cr.get_attribute('chain'):
            mcm_rs.append( request( rdb.get( rn )))
            if self.mode=='inject' and mcm_rs[-1].get_attribute('status') != 'approved':
                return dumps({"results" : False, "message" : 'requests %s in in "%s" status, requires "approved"'%( rn, mcm_rs[-1].get_attribute('status'))})
            uploader = ConfigMakerAndUploader(prepid=rn, lock = locker.lock(rn))
            uploader.run()

        mcm_r = mcm_rs[-1]
        from rest_api.BatchPrepId import BatchPrepId
        batch_name = BatchPrepId().next_batch_id( mcm_cr.get_attribute('member_of_campaign') , create_batch=self.mode=='inject')
        from tools.locker import semaphore_events, locker
        semaphore_events.increment(batch_name)

        from tools.ssh_executor import ssh_executor
        from tools.locator import locator
        l_type = locator()
        with ssh_executor(server = 'pdmvserv-test.cern.ch') as ssh:
            cmd='cd /afs/cern.ch/cms/PPD/PdmV/work/McM/dev-submit/\n'
            cmd+=mcm_r.make_release()
            cmd+='export X509_USER_PROXY=/afs/cern.ch/user/p/pdmvserv/private/$HOST/voms_proxy.cert\n'
            cmd+='export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n'
            ## until we get into production
            there='--wmtest --wmtesturl cmsweb-testbed.cern.ch'
            cmd+='wmcontrol.py --url-dict %s/public/restapi/chained_requests/get_dict/%s %s \n'%(l_type.baseurl(), crn, there)
            if self.mode == 'show':
                cherrypy.response.headers['Content-Type'] = 'text/plain'
                return cmd
            else:
                _, stdout, stderr = ssh.execute(cmd)
                cherrypy.response.headers['Content-Type'] = 'text/plain'
                output = stdout.read()
                error = stderr.read()
                self.logger.log(output)
                self.logger.log(error)

                injected_requests = [l.split()[-1] for l in output.split('\n') if
                                     l.startswith('Injected workflow:')]
                approved_requests = [l.split()[-1] for l in output.split('\n') if
                                     l.startswith('Approved workflow:')]
                if injected_requests and not approved_requests:
                    return dumps({"results" : False, "message" : "Request %s was injected but could not be approved" % ( injected_requests )})

                objects_to_invalidate = [
                    {"_id": inv_req, "object": inv_req, "type": "request", "status": "new", "prepid": self.prepid}
                    for inv_req in injected_requests if inv_req not in approved_requests]
                if objects_to_invalidate:
                    return dumps({"results" : False, "message" : "Some requests %s need to be invalidated"})
                
                added_requests = []
                for mcm_r in mcm_rs:
                    added = [{'name': app_req, 'content': {'pdmv_prep_id': mcm_r.get_attribute('prepid')}} for app_req in approved_requests]
                    added_requests.extend( added )
                
                with locker.lock(batch_name):
                    bdb = database('batches') 
                    bat = batch(bdb.get(batch_name))      
                    bat.add_requests(added_requests)
                    bat.update_history({'action': 'updated', 'step': crn})
                    bat.reload()
                    for mcm_r in mcm_rs:
                        mcm_r.set_attribute('reqmgr_name',  added_requests)

                for mcm_r in mcm_rs:
                    added = [{'name': app_req, 'content': {'pdmv_prep_id': mcm_r.get_attribute('prepid')}} for app_req in approved_requests]
                    mcm_r.set_attribute('reqmgr_name', added )
                    mcm_r.update_history({'action': 'inject','step' : batch_name})
                    mcm_r.set_attribute('approval', 'submit')
                    mcm_r.set_status(with_notification=False) ## maybe change to false
                    mcm_r.reload()
                
                mcm_cr.update_history({'action' : 'inject','step': batch_name})
                mcm_cr.set_attribute('step', len(mcm_rs)-1)
                mcm_cr.set_attribute('status','processing')
                mcm_cr.set_attribute('last_status', mcm_rs[-1].get_attribute('status'))
                message=""
                for mcm_r in mcm_rs:
                    message+=mcm_r.textified()
                    message+="\n\n"
                mcm_cr.notify('Injection succeeded for %s'% crn,
                              message)

                mcm_cr.reload()
                
                return dumps({"results" : True, "message" : "request send to batch %s"% batch_name})
                #return output+'\n\n-------------\n\n'+error



class TaskChainDict(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        
    def GET(self, *args):
        """                       
        Provide the taskchain dictionnary for uploading to request manager
        """
        from tools.locker import locker
        crn= args[0]
        crdb = database('chained_requests')
        ccdb = database('chained_campaigns')
        rdb = database('requests')
        def request_to_tasks( r , base, depend):
            ts=[]
            for si in range(len(r.get_attribute('sequences'))):
                task_dict={"TaskName": "%s_%d"%( r.get_attribute('prepid'), si),
                           "KeepOutput" : True,
                           "ConfigCacheID" : None,
                           "GlobalTag" : r.get_attribute('sequences')[si]['conditions'],
                           "CMSSWVersion" : r.get_attribute('cmssw_release'),
                           "ScramArch": r.get_scram_arch(),
                           "PrimaryDataset" : r.get_attribute('dataset_name'),
                           "AcquisitionEra" : r.get_attribute('member_of_campaign'),
                           "ProcessingString" : r.get_processing_string(si),
                           "ProcessingVersion" : r.get_attribute('version'),
                           "TimePerEvent" : r.get_attribute("time_event"),
                           "SizePerEvent" : r.get_attribute('size_event'),
                           "Memory" : r.get_attribute('memory'),
                           "FilterEfficiency" : r.get_efficiency()
                           }
                if len(r.get_attribute('config_id'))>si:
                    task_dict["ConfigCacheID"] = r.get_attribute('config_id')[si]

                if len(r.get_attribute('keep_output'))>si:
                    task_dict["KeepOutput"] = r.get_attribute('keep_output')[si]

                if r.get_attribute('pileup_dataset_name'):
                    task_dict["MCPileup"] = r.get_attribute('pileup_dataset_name')
                    
                if si==0:
                    if base:
                        task_dict.update({"SplittingAlgo"  : "EventBased",
                                          "RequestNumEvents" : r.get_attribute('total_events'),
                                          "Seeding" : "AutomaticSeeding",
                                          "EventsPerLumi" : 100,
                                          "LheInputFiles" : r.get_attribute('mcdb_id')>0
                                          })
                    else:
                        if depend:
                            task_dict.update({"SplittingAlgo"  : "EventAwareLumiBased",
                                              "InputFromOutputModule" : None,
                                              "InputTask" : None})
                        else:
                            task_dict.update({"SplittingAlgo"  : "EventAwareLumiBased",
                                              "InputDataset" : r.get_attribute('input_dataset')})
                else:
                    task_dict.update({"SplittingAlgo"  : "EventAwareLumiBased",
                                      "InputFromOutputModule" : ts[-1]['output_'],
                                      "InputTask" : ts[-1]['TaskName']})
                task_dict['output_'] = "%soutput"%(r.get_attribute('sequences')[si]['eventcontent'][0])
                task_dict['priority_'] = r.get_attribute('priority')
                ts.append(task_dict)    
            return ts

        if not crdb.document_exists(crn):
            ## it's a request actually
            mcm_r = rdb.get( crn )
            mcm_crs = crdb.query(query="root_request==%s"% crn)
            if len(mcm_crs)==0:  return dumps({})

            tasktree = {}
            inambiguous_id = None
            specific_campaign = None
            if len(mcm_crs) == 1:
                mcm_cc = ccdb.get( mcm_crs[0]['member_of_campaign'] )
                specific_campaign = mcm_cc['prepid']
                inambiguous_id = mcm_crs[0]['prepid'].replace( mcm_cc['prepid'], mcm_cc['alias'] )

            for mcm_cr in mcm_crs:
                starting_point=mcm_cr['step']
                for (ir,r) in enumerate(mcm_cr['chain']):
                    if (ir<starting_point) : continue ## ad no task for things before what is already done
                    if not r in tasktree:
                        tasktree[r] = { 'next' : [],
                                        'dict' : [],
                                        'rank' : ir}
                    base=(ir==0) ## there is only one that needs to start from scratch
                    depend=(ir>starting_point) ## all the ones later than the starting point depend on a previous task
                    if ir<(len(mcm_cr['chain'])-1):
                        tasktree[r]['next'].append( mcm_cr['chain'][ir+1])

                    tasktree[r]['dict'] = request_to_tasks( request(rdb.get( r )), base, depend)

            for (r,item) in tasktree.items():
                for n in item['next']:
                    tasktree[n]['dict'][0].update({"InputFromOutputModule" : item['dict'][-1]['output_'],
                                                       "InputTask" : item['dict'][-1]['TaskName']})
        

            wma={
                "RequestType" : "TaskChain",
                "inputMode" : "couchDB",
                "Group" : "ppd",
                "Requestor": "pdmvserv",
                "OpenRunningTimeout" : 43200,
                "TaskChain" : 0,
                "ProcessingVersion": 1,
                "RequestPriority" : 0,
                }

            task=1
            for (r,item) in sorted(tasktree.items(), key=lambda d: d[1]['rank']):
                for d in item['dict']:
                    if d['priority_'] > wma['RequestPriority']:  wma['RequestPriority'] = d['priority_']
                    for k in d.keys():
                        if k.endswith('_'):
                            d.pop(k)
                    wma['Task%d'%task] = d
                    task+=1
            wma['TaskChain'] = task-1

            for item in ['CMSSWVersion','ScramArch','TimePerEvent','SizePerEvent','GlobalTag','Memory']:
                wma[item] = wma['Task%d'% wma['TaskChain']][item]

            wma['Campaign' ] = wma['Task1']['AcquisitionEra']
            wma['PrepID' ] = 'task_'+wma['Task1']['TaskName'].split('_')[0]
            wma['RequestString' ] = wma['PrepID']
            return dumps(wma)
            

        mcm_cr = chained_request(crdb.get(crn))
        mcm_cc = chained_campaign( ccdb.get( mcm_cr.get_attribute('member_of_campaign')))
        from tools.locator import locator
        l_type=locator()
        wma={
            "RequestType" : "TaskChain",
            "inputMode" : "couchDB",
            "RequestString" : crn.replace(mcm_cc.get_attribute('prepid'), mcm_cc.get_attribute('alias')),
            "Group" : "ppd",
            "Requestor": "pdmvserv",
            "Campaign" : mcm_cc.get_attribute('prepid'),
            "OpenRunningTimeout" : 43200,
            "TaskChain" : 0,
            "ProcessingVersion": 1,
            "RequestPriority" : 0,
            "PrepID" : crn
            }
        #need to do something much more fancy for prepid to be able to trace it back

        mcm_rs=[]
        for rn in mcm_cr.get_attribute('chain'):
            mcm_rs.append( request( rdb.get( rn )))


        step=1
        last_io=None
        for (i,r) in enumerate( mcm_rs ):
            
            steps='step%d'%step
            for (si, seq) in enumerate(r.get_attribute('sequences')):
                if r.get_attribute('priority') > wma["RequestPriority"]:
                    wma["RequestPriority"] = r.get_attribute('priority')

                wma['Task%d'%step] ={'TaskName' : r.get_attribute('prepid'),#'Task%d'%step,
                                     "GlobalTag" : r.get_attribute('sequences')[si]['conditions'],
                                     "CMSSWVersion" : r.get_attribute('cmssw_release'),
                                     "ScramArch": r.get_scram_arch(),
                                     "PrimaryDataset" : r.get_attribute('dataset_name'),
                                     "AcquisitionEra" : r.get_attribute('member_of_campaign'),
                                     "ProcessingString" : r.get_processing_string(si),
                                     "ProcessingVersion" : r.get_attribute('version'),
                                     "TimePerEvent" : r.get_attribute("time_event"),
                                     "SizePerEvent" : r.get_attribute('size_event'),
                                     "Memory" : r.get_attribute('memory')
                      }
                if len(r.get_attribute('config_id'))>si:
                    wma['Task%d'%step]["ConfigCacheID"] = r.get_attribute('config_id')[si]
                else:
                    ## this should throw an exception
                    wma['Task%d'%step]["ConfigCacheID"] = None
                if len(r.get_attribute('keep_output'))>si:
                    wma['Task%d'%step]["KeepOutput"] = r.get_attribute('keep_output')[si]
                else:
                    wma['Task%d'%step]["KeepOutput"] = True

                if r.get_attribute('pileup_dataset_name'):
                    wma['Task%d'%step]["MCPileup"] = r.get_attribute('pileup_dataset_name')
                for item in ['CMSSWVersion','ScramArch','TimePerEvent','SizePerEvent','GlobalTag','Memory']:
                    ## needed for dictionnary validation in requests manager, but not used explicitely
                    if item not in wma:
                        wma[item] = wma['Task%d'%step][item]

                if step==1:
                    wma['Task%d'%step].update({"SplittingAlgo"  : "EventBased",
                                               "RequestNumEvents" : r.get_attribute('total_events'),
                                               "Seeding" : "AutomaticSeeding", 
                                               "EventsPerLumi" : 100, 
                                               "LheInputFiles" : r.get_attribute('mcdb_id')>0,
                                               "FilterEfficiency" : r.get_efficiency()
                                               })
                else:
                    wma['Task%d'%step].update({"SplittingAlgo"  : "EventAwareLumiBased",
                                               "InputFromOutputModule" : "%soutput"%last_io,
                                               "InputTask" : "Task%d"%(step-1),
                                               })
                last_io=r.get_attribute('sequences')[si]['eventcontent'][0]
                wma['TaskChain']+=1
                step+=1
        return dumps(wma)


class GetSetupForChains(RESTResource):
    def __init__(self, mode='setup'):
        self.access_limit = access_rights.user
        self.opt = mode
        if self.opt not in ['setup','test','valid']:
            raise Exception("Cannot create this resource with mode %s"% self.opt)
        if self.opt=='valid':
            self.access_limit = access_rights.administrator


    def GET(self, *args, **kwargs):
        if not len(args):
            return dumps({"results": False, "message": "Chained request prepid not given"})
        crdb = database('chained_requests')
        if not crdb.document_exists(args[0]):
            return dumps({"results": False, "message": "Chained request with prepid {0} does not exist".format(args[0])})
        cr = chained_request(crdb.get(args[0]))
        events = None
        run = False
        valid = False
        directory = ''
        if self.opt=='test' or self.opt=='valid':
            run = True
        if self.opt=='valid':
            valid = True

        if 'events' in kwargs:
            events = int(kwargs['events'])
        if 'directory' in kwargs:
            directory = kwargs['directory']

        cherrypy.response.headers['Content-Type'] = 'text/plain'
        return cr.get_setup(directory=directory, run=run, events=events, validation=valid)
