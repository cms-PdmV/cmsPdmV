#!/usr/bin/env python

import cherrypy
import traceback

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
from tools.locker import locker
from tools.settings import settings

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


        self.logger.info('Created new chained_request %s' % cr_id)

        # update history with the submission details
        req.update_history({'action': 'created'})

        return self.save_request(db, req)

    def save_request(self, db, req):
        if not db.document_exists(req.get_attribute('_id')):
            if db.save(req.json()):
                self.logger.info('new chained_request successfully saved.')
                return {"results":True, "prepid": req.get_attribute('prepid')}
            else:
                self.logger.error('Could not save new chained_request to database')
                return {"results":False}
        else:
            if db.update(req.json()):
                self.logger.info('new chained_request successfully saved.')
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

        self.logger.info('Updating chained_request %s' % (req.get_attribute('_id')))
        self.logger.info('wtf %s'%(str(req.get_attribute('approval'))))
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
                    return {"results":False, "message" : "the request %s, not in status new, at the root of the chain will not be chained anymore"% rid}
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
                             "Request {0} has successfuly left chain {1}".format(
                                    mcm_r.get_attribute('prepid'), crid))

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
            self.logger.info(args)
            reserve = args[1]=='reserve'
            if len(args)>2:
                reserve = args[2]

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

        self.logger.info('Attempting to flow to next step for chained_request %s' %  (
                creq.get_attribute('_id')))

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
            reserve = vdata["reserve"]
            return creq.reserve(limit = reserve)
        return creq.flow_trial( inputds,  inblack,  inwhite, check_stats)

    def flow(self, chainid, check_stats=True, reserve=False):
        try:
            db = database('chained_requests')
            creq = chained_request(json_input=db.get(chainid))
        except Exception as ex:
            self.logger.error('Could not initialize chained_request object. Reason: %s' % (ex))
            return {"results":str(ex)}

        #TO-DO check if chained_request is in settings forceflow_list and remove it!
        # if the chained_request can flow, do it
        if reserve:
            self.logger.info('Attempting to reserve to next step for chained_request %s' % (
                    creq.get_attribute('_id')))

            return creq.reserve( limit = reserve )

        self.logger.info('Attempting to flow to next step for chained_request %s' % (
                creq.get_attribute('_id')))

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
                self.logger.error('%s is after the current request and is not new: %s' % (
                        next, mcm_r.get_attribute('status')))

                return {"results":False, "message":"%s is not new" % (next), "prepid" : crid}

        ##get the one to be reset
        current_id=mcm_cr.get_attribute('chain')[current_step]
        mcm_r = request( rdb.get( current_id ))
        mcm_r.reset()
        saved = rdb.update( mcm_r.json() )
        if not saved:
            {"results":False, "message":"could not save the last request of the chain","prepid" : crid}
        ## the current chained request has very likely been updated :
        ## reload it as you have not changed anything to it yet
        mcm_cr = chained_request( crdb.get( crid) )

        mcm_cr.set_attribute('step',current_step -1 )
        # set status, last status
        mcm_cr.set_last_status()
        mcm_cr.set_attribute('status','processing')

        saved = crdb.update( mcm_cr.json())
        if saved:
            return {"results":True,"prepid" : crid}
        else:
            return {"results" : False,
                "message" : "could not save chained requests. the DB is going to be inconsistent !",
                "prepid" : crid}

class ApproveRequest(RESTResource):
    def __init__(self):
        self.acces_limit = 3

    def GET(self,  *args):
        """
        move the chained request approval to the next step
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results" : 'Error: No arguments were given'})
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
            return {"prepid":rid, "results":False ,
                'message': 'unable to save the updated chained request'}

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
        crlist = crid.rsplit(',')
        res = []
        crdb = database('chained_requests')
        for cr in crlist:
            if crdb.document_exists( cr):
                mcm_cr = chained_request( crdb.get( cr) )
                res.append( mcm_cr.inspect() )
            else:
                res.append( {"prepid": cr, "results":False, 'message' : '%s does not exist' % cr})

        if len(res) > 1:
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
            all_requests = rdb.get_all()

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
        self.access_limit = access_rights.generator_contact

    def GET(self, *args):
        """
        Perform test for chained requests
        """

        if not len(args):
            return dumps({"results" : False, "message" : "no argument provided"})

        from tools.handlers import RunChainValid, validation_pool
        ## now in the core of the api
        runtest = RunChainValid(crid=args[0], lock=locker.lock(args[0]))

        crdb = database('chained_requests')
        rdb = database('requests')
        settingsDB = database('settings')
        mcm_cr = chained_request(crdb.get(args[0]))
        mcm_rs = []
        if settingsDB.get('validation_stop')['value'] == True:
            return dumps({"results" : False,
                    'message': ('validation jobs are halted to allow forthcoming mcm '
                            'restart - try again later'),
                    "prepid" : args[0]})

        for rid in mcm_cr.get_attribute('chain')[mcm_cr.get_attribute('step'):]:
            mcm_r = request( rdb.get( rid ) )
            if mcm_r.get_attribute('status') in ['approved','submitted','done']:
                return dumps({"results" : False, "prepid" : args[0],
                        "message" : "request %s is in status %s" % (
                                rid, mcm_r.get_attribute('status'))})

        for rid in mcm_cr.get_attribute('chain')[mcm_cr.get_attribute('step'):]:
            mcm_r = request(rdb.get(rid))
            next = 'validation'
            if not mcm_r.is_root:  next = 'approve'
            try:
                if mcm_r.get_attribute('approval')  == 'none':
                    ## no need to try and move it along if already further than that
                    getattr(mcm_r,'ok_to_move_to_approval_%s' % next)(for_chain=True)
                    mcm_r.update_history({'action' : 'approve', 'step' : next})
                    mcm_r.set_attribute('approval', next)
                    mcm_r.reload()
                else:
                    pass
                    ## fail this for the moment. there is no way to handle this yet
                    #text="It is not supported for the moment to test a chain of requests which are partially not new. Please contact an administrator"
                    #runtest.reset_all( text  , notify_one = rid )
                    #return dumps({"results" : False, "message" : text, "prepid" : args[0]})

                text = 'Within chain %s \n'% mcm_cr.get_attribute('prepid')
                text += mcm_r.textified()
                mcm_r.notify('Approval %s in chain %s for request %s' % (next,
                        mcm_cr.get_attribute('prepid'), mcm_r.get_attribute('prepid')),
                        text, accumulate=True)

            except Exception as e:
                runtest.reset_all(str(e), notify_one=rid)
                return dumps({"results" : False, "message" : str(e),"prepid" : args[0]})

        validation_pool.add_task(runtest.internal_run)
        #runtest.start()
        return dumps({"results" : True, "message" : "run test started","prepid" : args[0]})

class SoftResetChainedRequest(RESTResource):
    def __init__(self, mode='show'):
        self.access_limit = access_rights.production_manager

    def GET(self, *args):
        """
        Does a soft reset to all relevant request in the chain
        """
        if not len(args):
            return dumps({"results" : False, "message" : "no argument provided"})

        arg0 = args[0]
        crdb = database('chained_requests')
        rdb = database('requests')

        mcm_cr = chained_request(crdb.get(arg0))
        for rid in reversed(mcm_cr.get_attribute('chain')[:mcm_cr.get_attribute('step')+1]):
            ## from the current one to the first one REVERSED
            mcm_r = request(rdb.get(rid))
            try:
                mcm_r.reset(hard=False)
            except Exception as e:
                return dumps({'prepid' : arg0, 'results' : False, 'message' : str(e)})

            mcm_r.reload()
            mcm_cr = chained_request(crdb.get(arg0))
            mcm_cr.set_attribute('step', max(0, mcm_cr.get_attribute('chain').index(rid)-1))
            mcm_cr.reload()

        return dumps({'prepid' : arg0, 'results':True})

class InjectChainedRequest(RESTResource):
    def __init__(self, mode='show'):
        self.access_limit = access_rights.production_manager
        self.mode = mode
        if self.mode not in ['inject','show']:
            raise Exception("%s not allowed" % (self.mode))

    def GET(self, *args):
        """
        Provides the injection command and does the injection.
        """

        if not len(args):
            return dumps({"results" : False, "message" : "no argument was passe"})

        pid = args[0]

        from tools.handlers import ChainRequestInjector, submit_pool

        _q_lock = locker.thread_lock(pid)
        if not locker.thread_acquire(pid, blocking=False):
            return dumps({"prepid": pid, "results": False,
                    "message": "The request {0} request is being handled already".format(
                        pid)})

        thread = ChainRequestInjector(prepid=pid, lock=locker.lock(pid), queue_lock=_q_lock,
                check_approval=False)

        if self.mode == 'show':
            cherrypy.response.headers['Content-Type'] = 'text/plain'
            return thread.make_command()
        else:
            submit_pool.add_task(thread.internal_run)
            #thread.start()
            return dumps({"results" : True,
                    "message" : "chain submission for %s will be forked unless same request is being handled already" % pid,
                    "prepid" : pid})

class TaskChainDict(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self, *args, **argv):
        """
        Provide the taskchain dictionnary for uploading to request manager
        """
        if not len(args):
            return dumps({})

        arg0 = args[0]
        crdb = database('chained_requests')
        rdb = database('requests')
        settingsDB = database('settings')

        __DT_prio = settingsDB.get('datatier_input')["value"]

        def get_list_of_steps(in_string):
            if isinstance(in_string, basestring):
                ##in case sequence is defined as string -> legacy support
                return [el.split(":")[0] for el in in_string.split(",")]
            else:
                return [el.split(":")[0] for el in in_string]

        def do_datatier_selection(possible_inputs, __prev_outputs):
            ##we check for every possible tier in prioritised possible inputs
            ## we iterate on all generated unique previous outputs
            ## if its a match -> we return
            self.logger.debug("do_datatier_selection input:\n%s %s" % (
                possible_inputs, __prev_outputs))

            __in_taskName = ""
            __in_InputModule = ""
            for possible in possible_inputs:
                 for taskName, tier in reversed(__prev_outputs):
                    for t in tier:
                        if t == possible:
                            return "%soutput" % (t), taskName
            ##return empty values if nothing found
            return "", ""

        def request_to_tasks(r,base,depend):
            ts = []
            for si in range(len(r.get_attribute('sequences'))):
                task_dict = {"TaskName": "%s_%d" % (r.get_attribute('prepid'), si),
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
                           "FilterEfficiency" : r.get_efficiency(),
                           "PrepID" : r.get_attribute('prepid')
                           }
                ##check if we have multicore an it's not an empty string
                if 'nThreads' in r.get_attribute('sequences')[si] and r.get_attribute('sequences')[si]['nThreads']:
                    task_dict["Multicore"] = int(r.get_attribute('sequences')[si]['nThreads'])

                __list_of_steps = get_list_of_steps(r.get_attribute('sequences')[si]['step'])

                if len(r.get_attribute('config_id')) > si:
                    task_dict["ConfigCacheID"] = r.get_attribute('config_id')[si]

                if len(r.get_attribute('keep_output')) > si:
                    task_dict["KeepOutput"] = r.get_attribute('keep_output')[si]

                if r.get_attribute('pileup_dataset_name'):
                    task_dict["MCPileup"] = r.get_attribute('pileup_dataset_name')

                if si == 0:
                    if base:
                        task_dict.update({"SplittingAlgo"  : "EventBased",
                                          "RequestNumEvents" : r.get_attribute('total_events'),
                                          "Seeding" : "AutomaticSeeding",
                                          "EventsPerLumi" : r.get_events_per_lumi(task_dict.get("Multicore", None)),
                                          "LheInputFiles" : r.get_attribute('mcdb_id') > 0
                                          })

                        ## temporary work-around for request manager not creating enough jobs
                        ## https://github.com/dmwm/WMCore/issues/5336
                        ## inflate requestnumevents by the efficiency to create enough output
                        max_forward_eff = r.get_forward_efficiency()
                        task_dict["EventsPerLumi"] /= task_dict["FilterEfficiency"] #should stay nevertheless as it's in wmcontrol for now
                        task_dict["EventsPerLumi"] /= max_forward_eff #this does not take its own efficiency

                    else:
                        if depend:
                            task_dict.update({"SplittingAlgo"  : "EventAwareLumiBased",
                                              "InputFromOutputModule" : None,
                                              "InputTask" : None})
                        else:
                            task_dict.update({"SplittingAlgo"  : "EventAwareLumiBased",
                                              "InputDataset" : r.get_attribute('input_dataset'),
                                              "RequestNumEvents" : r.get_attribute("total_events")})
                else:
                    ##here we select the appropriate DATATier from previous step
                    # in case -step tier1,tier2,tier3 and
                    __curr_first_step = __list_of_steps[0]
                    __prev_tiers = [(ts[-1]["TaskName"], ts[-1]["_output_tiers_"])]
                    tModule = tName = ""

                    if __curr_first_step in __DT_prio:
                        ##if 1st step is defined in DataTier priority dictionary
                        tModule, tName = do_datatier_selection(
                                __DT_prio[__curr_first_step], __prev_tiers)

                    if tModule != "" and tName != "":
                        task_dict.update({"SplittingAlgo"  : "EventAwareLumiBased",
                                "InputFromOutputModule" : tModule,
                                "InputTask" : tName})
                    else:
                        ##fallback solution
                        task_dict.update({"SplittingAlgo"  : "EventAwareLumiBased",
                                "InputFromOutputModule" : ts[-1]['output_'],
                                "InputTask" : ts[-1]['TaskName']})

                task_dict['_first_step_'] = __list_of_steps[0]
                task_dict['_output_tiers_'] = r.get_attribute('sequences')[si]["eventcontent"]
                task_dict['output_'] = "%soutput" % (r.get_attribute('sequences')[si]['eventcontent'][0])
                task_dict['priority_'] = r.get_attribute('priority')
                task_dict['request_type_'] = r.get_wmagent_type()
                ts.append(task_dict)

            return ts

        if not crdb.document_exists(arg0):
            ## it's a request actually, pick up all chains containing it
            mcm_r = rdb.get(arg0)
            #mcm_crs = crdb.query(query="root_request==%s"% arg0) ## not only when its the root of
            mcm_crs = crdb.query(query="contains==%s" % arg0)
            task_name = 'task_' + arg0
        else:
            mcm_crs = [crdb.get(arg0)]
            ##here name should be task_chain's[curr_step] request_prepid
            # so it would be task_prepid-of-current-request same as in top
            __req_id = mcm_crs[0]['chain'][mcm_crs[0]['step']]
            task_name = 'task_' + __req_id

        if len(mcm_crs) == 0:  return dumps({})

        tasktree = {}
        ignore_status = False

        if 'scratch' in argv:
            ignore_status = True

        veto_point = None
        if 'upto' in argv:
            veto_point = int(argv['upto'])

        for mcm_cr in mcm_crs:
            starting_point = mcm_cr['step']
            if ignore_status: starting_point = 0
            for (ir, r) in enumerate(mcm_cr['chain']):
                if (ir < starting_point) :
                    continue ## ad no task for things before what is already done
                if veto_point and (ir > veto_point):
                    continue
                mcm_r = request(rdb.get( r ))
                if mcm_r.get_attribute('status') == 'done' and not ignore_status:
                    continue

                if not r in tasktree:
                    tasktree[r] = {'next' : [], 'dict' : [], 'rank' : ir}

                base = (ir == 0) ## there is only one that needs to start from scratch
                depend = (ir > starting_point) ## all the ones later than the starting point depend on a previous task
                if ir < (len(mcm_cr['chain']) - 1):
                    tasktree[r]['next'].append( mcm_cr['chain'][ir + 1])

                tasktree[r]['dict'] = request_to_tasks( mcm_r, base, depend)

        for (r, item) in tasktree.items():
            ##here we should generate unique list of steps+output tiers
            #as we iterate over requests in tasktree
            __uniq_tiers = []
            for el in item['dict']:
                ##map of tiers and taskID in order of steps
                __uniq_tiers.append((el['TaskName'], el['_output_tiers_']))

            item['unique_tiers_'] = __uniq_tiers
            for n in item['next']:
                ##here we should take input from datatier selection;
                #have a map of tiers -> taskNames and select appropriate one
                __input_tier = tasktree[n]['dict'][0]['_first_step_']
                tModule = tName = ""
                if __input_tier in __DT_prio:
                    ##in case there is a possible DataTier in global_dict
                    tModule, tName = do_datatier_selection(__DT_prio[__input_tier], __uniq_tiers)

                if tModule != "" and tName != "":
                    tasktree[n]['dict'][0].update({"InputFromOutputModule" : tModule,
                            "InputTask" : tName})
                else:
                    ##default & fallback solution
                    tasktree[n]['dict'][0].update({"InputFromOutputModule" : item['dict'][-1]['output_'],
                            "InputTask" : item['dict'][-1]['TaskName']})

        wma = {
            "RequestType" : "TaskChain",
            "inputMode" : "couchDB",
            "Group" : "ppd",
            "Requestor": "pdmvserv",
            "TaskChain" : 0,
            "ProcessingVersion": 1,
            "RequestPriority" : 0,
            "SubRequestType" : "MC",
            ##we default to 1 in multicore global
            "Multicore" : 1,
            }

        task = 1
        for (r, item) in sorted(tasktree.items(), key=lambda d: d[1]['rank']):
            for d in item['dict']:
                if d['priority_'] > wma['RequestPriority']:  wma['RequestPriority'] = d['priority_']
                if d['request_type_'] in ['ReDigi']:  wma['SubRequestType'] = 'ReDigi'
                for k in d.keys():
                    if k.endswith('_'):
                        d.pop(k)
                wma['Task%d'%task] = d
                task += 1

        wma['TaskChain'] = task-1

        if wma['TaskChain'] == 0:
            return dumps({})

        for item in ['CMSSWVersion','ScramArch','TimePerEvent','SizePerEvent','GlobalTag','Memory']:
            wma[item] = wma['Task%d'% wma['TaskChain']][item]

        ##since 2016-11, processingString and AcquisitionEra is mandatory in global params
        wma['AcquisitionEra'] = wma['Task1']['AcquisitionEra']
        wma['ProcessingString'] = wma['Task1']['ProcessingString']
        wma['PrepID'] = task_name
        wma['RequestString'] = wma['PrepID']
        cherrypy.response.headers['Content-Type'] = 'text/plain'
        return dumps(wma, indent=4)

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
            return dumps({"results": False,
                    "message": "Chained request with prepid {0} does not exist".format(args[0])})

        cr = chained_request(crdb.get(args[0]))
        events = None
        run = False
        valid = False
        directory = ''
        __scratch = False

        if 'scratch' in kwargs:
            __scratch = kwargs["scratch"]
        if self.opt == 'test' or self.opt == 'valid':
            run = True
        if self.opt == 'valid':
            valid = True

        if 'events' in kwargs:
            events = int(kwargs['events'])
        if 'directory' in kwargs:
            directory = kwargs['directory']

        cherrypy.response.headers['Content-Type'] = 'text/plain'
        return cr.get_setup(directory=directory, run=run, events=events,
                validation=valid, scratch=__scratch)

class TestOutputDSAlgo(RESTResource):
    def __init__(self, mode='setup'):
        self.access_limit = access_rights.user


    def GET(self, *args, **kwargs):
        if not len(args):
            return dumps({"results": False, "message": "Chained request prepid not given"})

        crdb = database('chained_requests')
        if not crdb.document_exists(args[0]):
            return dumps({"results": False,
                    "message": "Chained request with prepid {0} does not exist".format(args[0])})

        cr = chained_request(crdb.get(args[0]))

        cherrypy.response.headers['Content-Type'] = 'text/plain'
        return cr.test_output_ds()

class ForceChainReqToDone(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager
        self.crdb = database('chained_requests')

    def GET(self, *args, **kwargs):
        """
        Force chained_request to set status to done
        """
        if not len(args):
            return dumps({"results": False, "message": "Chained request prepid not given"})

        cherrypy.response.headers['Content-Type'] = 'text/plain'

        if ',' in args[0]:
            rlist = args[0].rsplit(',')
            res = []
            for r in rlist:
                res.append(self.force_status_done(r))
            return dumps(res)
        else:
            return dumps([self.force_status_done(args[0])])

    def force_status_done(self, prepid):
        if not self.crdb.document_exists(prepid):
            return dumps({"results": False,
                    "message": "Chained request with prepid {0} does not exist".format(prepid)})

        cr = chained_request(self.crdb.get(prepid))

        if not (cr.get_attribute("status") in ["done", "force_done"]):
            cr.set_status(to_status="force_done")
            self.logger.debug("forcing chain_req status to done. cr status:%s" %(
                    cr.get_attribute("status")))

            ret = self.crdb.save(cr.json())
            return {'prepid': prepid, 'message': ret, 'results' : True}
        else:
            ret = "Chained request already in status done"
            return {'prepid': prepid, 'message': ret, 'results': False}

class ForceStatusDoneToProcessing(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager
        self.crdb = database('chained_requests')

    def GET(self, *args, **kwargs):
        """
        Move chained_request from force_done to processing
        """
        if not len(args):
            return dumps({"results": False, "message": "Chained request prepid not given"})

        cherrypy.response.headers['Content-Type'] = 'text/plain'

        if ',' in args[0]:
            rlist = args[0].rsplit(',')
            res = []
            for r in rlist:
                res.append(self.force_status(r))
            return dumps(res)
        else:
            return dumps([self.force_status(args[0])])

    def force_status(self, prepid):
        if not self.crdb.document_exists(prepid):
            return dumps({"results": False,
                    "message": "Chained request with prepid {0} does not exist".format(prepid)})

        cr = chained_request(self.crdb.get(prepid))

        if cr.get_attribute("status") == "force_done":
            cr.set_status(to_status="processing")
            self.logger.debug("Moving chain_req back to satus 'processing'. cr status:%s" %(
                    cr.get_attribute("status")))

            ret = self.crdb.save(cr.json())
            return {'prepid': prepid, 'message': ret, 'results': True}
        else:
            ret = "Chained request not in status force_done"
            return {'prepid': prepid, 'message': ret, 'results': False}

class ToForceFlowList(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.generator_contact
        self.sdb = database('settings')

    def GET(self, *args, **kwargs):
        """
        Add selected prepid's to global force complete list for later action
        """
        if not len(args):
            return dumps({"results": False, "message": "Chained request prepid not given"})

        if ',' in args[0]:
            rlist = args[0].rsplit(',')
        else:
            rlist = [args[0]]
        res = []

        forceflow_list = self.sdb.get("list_of_forceflow")
        ##TO-DO check if prepid exists!
        ##TO-DO check the status of chain_req!
        for el in rlist:
            if el not in forceflow_list["value"]:
                forceflow_list["value"].append(el)
                res.append({"prepid": el, 'results': True, 'message': 'OK'})
            else:
                res.append({"prepid": el, 'results': False, 'message': 'Chained request already in forceflow list'})

        ##TO-DO check the update return value
        ret = self.sdb.update(forceflow_list)

        return dumps(res)
