from json_base import json_base
from json_layer.request import request
from json_layer.campaign import campaign
from flow import flow

from couchdb_layer.mcm_database import database
import json
from tools.priority import priority
from tools.locker import locker
from tools.locator import locator
from tools.settings import settings

class chained_request(json_base):
    class CampaignAlreadyInChainException(Exception):
        def __init__(self, campaign):
            self.c = campaign
            chained_request.logger.error('Campaign %s is already member of the chain.' % self.c)

        def __str__(self):
            return 'Error: Campaign', self.c, 'already represented in the chain.'

    class ChainedRequestCannotFlowException(Exception):
        def __init__(self, crname, message='cannot flow any further'):
            self.name = str(crname)
            self.message = message
            chained_request.logger.error('Chained request %s %s.' % (self.name, self.message))

        def __str__(self):
            return 'Chained request %s %s.' % (self.name, self.message)

    class NotApprovedException(Exception):
        def __init__(self, oname, alevel, allowed):
            self.name = str(oname)
            self.level = str(alevel)
            self.allowed = ' or '.join(map(lambda s: '"%s"' % s, allowed))
            chained_request.logger.error(
                '%s has not been approved for any of %s levels : "%s"' % (self.name, self.allowed, self.level))

        def __str__(self):
            return 'Error: ' + self.name + ' is "' + self.level + '" approved. requires ' + self.allowed

    class NotInProperStateException(Exception):
        def __init__(self, oname, alevel, allowed):
            self.name = str(oname)
            self.level = str(alevel)
            self.allowed = ' or '.join(map(lambda s: '"%s"' % s, allowed))
            chained_request.logger.error('%s has not reached status %s : "%s"' % (self.name, self.allowed, self.level))

        def __str__(self):
            return 'Error: ' + self.name + ' is in"' + self.level + '" status. requires ' + self.allowed

    class CampaignStoppedException(NotApprovedException):
        def __init__(self, oname):
            self.name = str(oname)
            chained_request.logger.error('Campaign %s is stopped' % self.name)

        def __str__(self):
            return 'Error: ' + self.name + ' is stopped.'

    _json_base__approvalsteps = ['none', 'flow', 'submit']

    _json_base__status = ['new', 'processing', 'done']

    _json_base__schema = {
        '_id': '',
        'chain': [],
        'approval': str(''),
        'step': 0,
        'analysis_id': [],
        'pwg': '',
        #'generators':'', #prune
        #'priority':-1, #prune
        'prepid': '',
        #'alias':'', #prune
        'dataset_name': '',
        #'total_events': -1,
        'history': [],
        'member_of_campaign': '',
        #'generator_parameters':[], #prune
        #'request_parameters':{} # json with user prefs #prune
        'last_status': 'new',
        'status': ''
    }

    def __init__(self, json_input=None):

        json_input = json_input if json_input else {}

        # create all chained request in flow
        self._json_base__schema['approval'] = self.get_approval_steps()[1]
        self._json_base__schema['status'] = self.get_status_steps()[0]

        # update self according to json_input
        self.setup()
        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()

    def get_actors(self, N=-1, what='author_username', Nchild=-1):
        rdb = database('requests')
        last_r = request(rdb.get(self.get_attribute('chain')[-1]))
        return last_r.get_actors(N,what,Nchild)

    def flow_trial(self, input_dataset='', block_black_list=None, block_white_list=None, check_stats=True, reserve=False):
        if not block_black_list: block_black_list = []
        if not block_white_list: block_white_list = []
        chainid = self.get_attribute('prepid')
        try:
            if self.flow(check_stats=check_stats):
                db = database('chained_requests')
                db.update(self.json())
                ## toggle the last request forward
                self.toggle_last_request()
                return {"prepid": chainid, "results": True}
            return {"prepid": chainid, "results": False, "message": "Failed to flow."}
        except Exception as ex:
            return {"prepid": chainid, "results": False, "message": str(ex)}
            #return {"prepid":chainid,"results":False, "message":str(ex)+'\n'+traceback.format_exc()}
            #except chained_request.NotInProperStateException as ex:
            #    return {"prepid":chainid,"results":False, "message":str(ex)}
            #except chained_request.ChainedRequestCannotFlowException as ex:
            #    return {"prepid":chainid,"results":False, "message":str(ex)}

    def request_join(self, req):
        with locker.lock(req.get_attribute('prepid')):
            chain = req.get_attribute("member_of_chain")
            chain.append(self.get_attribute('_id'))
            req.set_attribute("member_of_chain", chain)
        loc = locator()
        req.notify("Request {0} joined chain".format(req.get_attribute('prepid')), 
                   "Request {0} has successfully joined chain {1}\n\n{2}\n".format(req.get_attribute('prepid'),
                                                                                          self.get_attribute('_id'),
                                                                                          "/".join([loc.baseurl(), "requests?prepid={0}".format(req.get_attribute('prepid'))])),
                   accumulate=True)
        req.update_history({'action': 'join chain', 'step': self.get_attribute('_id')})
        if not req.get_attribute('prepid') in self.get_attribute('chain'):
            chain = self.get_attribute('chain')
            chain.append(req.get_attribute('prepid'))
            self.set_attribute("chain", chain)
            self.update_history({'action': 'add request', 'step': req.get_attribute('prepid')})

    def reserve(self):
        while True:
            try:
                if not self.flow_to_next_step(check_stats=False, reserve=True):
                    break
                saved = self.reload()
                if not saved: return {"prepid": self.get_attribute("prepid"), "results": False, "message": "Failed to save chained request to database"}
            except Exception as ex:
                return {"prepid": self.get_attribute("prepid"), "results": False, "message": str(ex)}
        return {"prepid": self.get_attribute("prepid"), "results": True}


    def flow(self, input_dataset='', block_black_list=None, block_white_list=None, check_stats=True):
        if not block_black_list: block_black_list = []
        if not block_white_list: block_white_list = []
        return self.flow_to_next_step(input_dataset, block_black_list, block_white_list, check_stats)
        #return self.flow_to_next_step_clean(input_dataset,  block_black_list,  block_white_list)

    def flow_to_next_step(self, input_dataset='', block_black_list=None, block_white_list=None, check_stats=True, reserve=False):
        if not block_white_list: block_white_list = []
        if not block_black_list: block_black_list = []
        self.logger.log('Flowing chained_request %s to next step...' % (self.get_attribute('_id')))
        if not self.get_attribute('chain'):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'chained_request %s has got no root' % (
                                                             self.get_attribute('_id')))

        # check on the approval of the chained request before all
        ## let it be flowing regardless
        #if self.get_attribute('approval') == 'none':
        #    raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
        #                                                 'The approval of the chained request is none, and therefore flow cannot happen')

        #this operation requires to access all sorts of objects
        rdb = database('requests')
        cdb = database('campaigns')
        ccdb = database('chained_campaigns')
        crdb = database('chained_requests')
        fdb = database('flows')
        adb = database('actions')

        l_type=locator()

        current_step = len(self.get_attribute('chain'))-1 if reserve else self.get_attribute('step')
        current_id = self.get_attribute('chain')[current_step]
        next_step = current_step + 1

        if not rdb.document_exists(current_id):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'the request %s does not exist' % current_id)

        current_request = request(rdb.get(current_id))
        current_campaign = campaign(cdb.get(current_request.get_attribute('member_of_campaign')))

        if not ccdb.document_exists(self.get_attribute('member_of_campaign')):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'the chain request %s is member of %s that does not exist' % (
                                                             self.get_attribute('_id'),
                                                             self.get_attribute('member_of_campaign')))
        mcm_cc = ccdb.get(self.get_attribute('member_of_campaign'))
        if next_step >= len(mcm_cc['campaigns']):
            if reserve: return False
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'chained_campaign %s does not allow any further flowing.' % (
                                                             self.get_attribute('member_of_campaign')))

        if not reserve:
            ## is the current request in the proper approval
            allowed_request_approvals = ['submit']
            if current_request.get_attribute('approval') not in allowed_request_approvals:
                raise self.NotApprovedException(current_request.get_attribute('prepid'),
                                                current_request.get_attribute('approval'), allowed_request_approvals)
            ## is the current request in the proper status
            allowed_request_statuses = ['submitted', 'done']
            if current_request.get_attribute('status') not in allowed_request_statuses:
                raise self.NotInProperStateException(current_request.get_attribute('prepid'),
                                                     current_request.get_attribute('status'),
                                                     allowed_request_statuses)

        original_action_id = self.get_attribute('chain')[0]

        original_action_item = self.retrieve_original_action_item(adb, original_action_id)

        ## what is the campaign to go to next and with which flow
        (next_campaign_id, flow_name) = mcm_cc['campaigns'][next_step]
        if not fdb.document_exists(flow_name):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The flow %s does not exist' % flow_name )

        mcm_f = flow(fdb.get(flow_name))
        if not 'sequences' in mcm_f.get_attribute('request_parameters'):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The flow %s does not contain sequences information.' % (
                                                             flow_name))

        if not cdb.document_exists(next_campaign_id):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The next campaign %s does not exist' % next_campaign_id)

        next_campaign = campaign(cdb.get(next_campaign_id))
        if len(next_campaign.get_attribute('sequences')) != len(mcm_f.get_attribute('request_parameters')['sequences']):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'the sequences changes in flow %s are not consistent with the next campaign %s' % (
                                                             flow_name, next_campaign_id))

        if next_campaign.get_attribute('energy') != current_campaign.get_attribute('energy'):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'cannot flow any further. Request {0} has inconsistent energy.'.format(next_campaign.get_attribute("prepid")))

        if not next_campaign.is_release_greater_or_equal_to(current_campaign.get_attribute('cmssw_release')):
            raise self.ChainedRequestCannotFlowException(self.get_attribute("_id"), 'cannot flow any further. Request {0} has lower release version.'.format(next_campaign.get_attribute("prepid")))

        if next_campaign.get_attribute('type') == 'MCReproc' and (not 'time_event' in mcm_f.get_attribute('request_parameters')):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'the flow is getting into a MCReproc campaign but not time per event is specified')

        if next_campaign.get_attribute('type') == 'MCReproc' and (not 'size_event' in mcm_f.get_attribute('request_parameters')):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'the flow is getting into a MCReproc campaign but not size per event is specified')


        
        ## check that it is allowed to flow
        allowed_flow_approvals = ['flow', 'submit']
        ###### cascade of checks
        """
        if not reserve and not mcm_f.get_attribute('approval') in allowed_flow_approvals:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The flow (%s) is not in proper approval state (%s)'%( 
                                                            mcm_f.get_attribute('prepid'),
                                                            mcm_f.get_attribute('approval')))

        if not reserve and not self.get_attribute('approval') in allowed_flow_approvals:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The chained request (%s) is not in the proper approval state (%s)'% (
                                                            self.get_attribute('_id'),
                                                            self.get_attribute('approval')))
        """
        if not reserve and not mcm_f.get_attribute('approval') in allowed_flow_approvals:
            if not self.get_attribute('approval') in allowed_flow_approvals:
                raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                             'Neither the flow (%s) nor the chained request (%s) approvals allow for flowing' % (
                                                               mcm_f.get_attribute('approval'),
                                                               self.get_attribute('approval')))

        if next_campaign.get_attribute('status') == 'stopped':
            raise self.CampaignStoppedException(next_campaign_id)

        #what is going to be the required number of events for the next request
        #update the stats to its best
        if not reserve:
            current_request.get_stats()
            next_total_events=current_request.get_attribute('completed_events')
            ## get the original expected events and allow a margin of 5% less statistics
            statistics_fraction = settings().get_value('statistics_fraction')
            current_eff_error = 1. - current_request.get_efficiency_error()
            statistics_fraction = min( statistics_fraction, current_eff_error )
            completed_events_to_pass = int(current_request.get_attribute('total_events') * statistics_fraction )

            notify_on_fail=True ## to be tuned according to the specific cases
            if current_request.get_attribute('completed_events') <= 0:
                raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                             'The number of events completed is negative or null')
            else:
                allowed_request_statuses = ['done']
                ## determine if this is a root -> non-root transition to potentially apply staged number
                at_a_transition=(current_campaign.get_attribute('root') != 1 and next_campaign.get_attribute('root') == 1)
                if ('staged' in original_action_item or 'threshold' in original_action_item) and at_a_transition:
                    allowed_request_statuses.append('submitted')
                ##check status
                if not current_request.get_attribute('status') in allowed_request_statuses:
                    raise self.NotInProperStateException(current_request.get_attribute('prepid'),
                                                         current_request.get_attribute('status'),
                                                         allowed_request_statuses)
                ##special check at transition that the statistics is good enough
                if at_a_transition:
                    # at a root -> non-root transition only does the staged/threshold functions !
                    if 'staged' in original_action_item:
                        next_total_events = int(original_action_item['staged'])
                        completed_events_to_pass = next_total_events
                    if 'threshold' in original_action_item:
                        next_total_events = int(current_request.get_attribute('total_events') * float(original_action_item['threshold'] / 100.))
                        completed_events_to_pass = next_total_events


            if check_stats and (current_request.get_attribute('completed_events') < completed_events_to_pass):
                if notify_on_fail:
                    current_request.notify('Flowing %s with not enough statistics'%( current_request.get_attribute('prepid')),
                                           'For the request %s, the completed statistics %s is not enough to fullfill the requirement to the next level : need at least %s in chain %s \n\n Please report to the operation HN or at the next MccM what action should be taken.\n\n %srequests?prepid=%s\n%schained_requests?contains=%s\n%schained_requests?prepid=%s '%( 
                            current_request.get_attribute('prepid'),
                            current_request.get_attribute('completed_events'),
                            completed_events_to_pass,
                            self.get_attribute('prepid'),
                            l_type.baseurl(),
                            current_request.get_attribute('prepid'),
                            l_type.baseurl(),
                            current_request.get_attribute('prepid'),
                            l_type.baseurl(),
                            self.get_attribute('prepid')
                            ),
                                           accumulate=True)
                raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                             'The number of events completed (%s) is not enough for the requirement (%s)'%(current_request.get_attribute('completed_events'), completed_events_to_pass))

        ## select what is to happened : [create, patch, use]
        next_id = None
        approach = None
        next_request = None
        if next_step != len(self.get_attribute('chain')):
            #not at the end
            next_id = self.get_attribute('chain')[next_step]
            if not rdb.document_exists(next_id):
                raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                             'The next request (%s) according to the step (%s) does not exist' % (
                                                                 next_id, next_step))
            next_request = request(rdb.get(next_id))
            if next_request.get_attribute('status') == 'new':
                #most likely a rewind + resub
                approach = 'patch'
            else:
                ##this is always the case in chains reserved from existing things: so use the next request
                approach = 'use'
                #raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                #'This should never happen. (%s) is next according to step (%s), but is not in new status (%s)' % (
                #next_id, next_step, next_request.get_attribute('status')))
        else:
            ## look in *other* chained campaigns whether you can suck in an existing request
            ## look up all chained requests that start from the same root request
            ## remove <pwg>-chain_ and the -serial number, replacing _ with a .
            toMatch = '.'.join(self.get_attribute('prepid').split('_')[1:][0:next_step + 1]).split('-')[0]
            ## make sure they get ordered by prepid
            related_crs = sorted(crdb.queries(['root_request==%s' % original_action_id]), key=lambda cr : cr['prepid'])
            
            

            vetoed_last=[]
            for existing_cr in related_crs:
                ## exclude itself
                if existing_cr['prepid']==self.get_attribute('prepid'):
                    continue
                ## prevent from using a request from within the same exact chained_campaigns
                if existing_cr['member_of_campaign'] == self.get_attribute('member_of_campaign'):
                    mcm_cr = chained_request(crdb.get(existing_cr['prepid']))
                    if len(mcm_cr.get_attribute('chain')) > next_step:
                        ## one existing request in the very same chained campaign has already something used, make sure it is not going to be used
                        vetoed_last.append( mcm_cr.get_attribute('chain')[next_step])
                    continue
                else:
                    continue
            for existing_cr in related_crs:
                ## exclude itself
                if existing_cr['prepid']==self.get_attribute('prepid'):
                    continue
                ## prevent from using a request from within the same exact chained_campaigns
                if existing_cr['member_of_campaign'] == self.get_attribute('member_of_campaign'):
                    continue
                truncated = '.'.join(existing_cr['prepid'].split('_')[1:][0:next_step + 1]).split('-')[0]
                self.logger.error('to match : %s , this one %s' % ( toMatch, truncated ))
                if truncated == toMatch:
                    #we found a chained request that starts with all same steps          
                    mcm_cr = chained_request(crdb.get(existing_cr['prepid']))
                    if len(mcm_cr.get_attribute('chain')) <= next_step:
                        #found one, but it has not enough content either
                        continue
                    if mcm_cr.get_attribute('chain')[next_step] in vetoed_last:
                        continue
                    next_id = mcm_cr.get_attribute('chain')[next_step]
                    break
            if next_id:
                approach = 'use'
            else:
                approach = 'create'

        if approach == 'create':
            from rest_api.RequestPrepId import RequestPrepId

            next_id = RequestPrepId().next_prepid(current_request.get_attribute('pwg'), next_campaign_id)
            next_request = request(rdb.get(next_id))
            request.transfer( current_request, next_request)
            self.request_join(next_request)
        elif approach == 'use':
            ## there exists a request in another chained campaign that can be re-used here.
            # take this one. advance and go on
            next_request = request(rdb.get(next_id))
            if not reserve:
                self.set_attribute('step', next_step)
                self.set_attribute('last_status', next_request.get_attribute('status'))
                self.update_history({'action': 'flow', 'step': str(next_id)})
                self.set_attribute('status', 'processing')

            if not self.get_attribute("prepid") in next_request.get_attribute("member_of_chain"):
                ## register the chain to the next request
                self.request_join(next_request)
                saved = rdb.update(next_request.json())
                if not saved:
                    raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                                 'Unable to save %s with updated member_of_chains' % next_id)
            return True
        elif approach == 'patch':
            ## there exists already a request in the chain (step!=last) and it is usable for the next stage
            next_request = request( next_campaign.add_request( rdb.get(next_id)))
            ## propagate again some of the fields of the previous request.
            request.transfer( current_request, next_request )
        else:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'Unrecognized approach %s' %  approach )

        #current_request -> next_request
        #current_campaign -> next_campaign

        ##determine whether we have an input dataset for the next request
        if len(current_request.get_attribute('output_dataset')):
            input_dataset = current_request.get_attribute('output_dataset')[-1]
        elif len(current_request.get_attribute('reqmgr_name')):
            ## the later check pre-dates the inclusion of output_dataset as a member of request object
            last_wma = current_request.get_attribute('reqmgr_name')[-1]
            if 'content' in last_wma and 'pdmv_dataset_name' in last_wma['content']:
                input_dataset = last_wma['content']['pdmv_dataset_name']
            else:
                statsDB = database('stats', url='http://cms-pdmv-stats.cern.ch:5984/')
                if statsDB.document_exists(last_wma['name']):
                    latestStatus = statsDB.get(last_wma['name'])
                    input_dataset = latestStatus['pdmv_dataset_name']
        if input_dataset:
            next_request.set_attribute('input_dataset', input_dataset)



        ## set blocks restriction if any
        if block_black_list:
            next_request.set_attribute('block_black_list', block_black_list)
        if block_white_list:
            next_request.set_attribute('block_white_list', block_white_list)

        ## register the flow to the request
        next_request.set_attribute('flown_with', flow_name)

        ##assemble the campaign+flow => request
        request.put_together(next_campaign, mcm_f, next_request)
        if not reserve:
            #already taking stage and threshold into account
            next_request.set_attribute('total_events', next_total_events)

            next_request.update_history({'action': 'flow', 'step': self.get_attribute('prepid')})
        request_saved = rdb.save(next_request.json())

        if not request_saved:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'Could not save the new request %s' % (
                                                             next_request.get_attribute('prepid')))

        ## inspect priority
        self.set_priority(original_action_item['block_number'])
        if not reserve:
            # sync last status
            self.set_attribute('last_status', next_request.get_attribute('status'))
            # we can only be processing at this point
            self.set_attribute('status', 'processing')
            # set to next step
            self.set_attribute('step', next_step)
            self.update_history({'action': 'flow', 'step': next_request.get_attribute('prepid')})

        if not reserve:
            notification_subject = 'Flow for request %s in %s' % (current_request.get_attribute('prepid'), next_campaign_id)
            notification_text = 'The request %s has been flown within:\n \t %s \n into campaign:\n \t %s \n using:\n \t %s \n creating the new request:\n \t %s \n as part of:\n \t %s \n and from the produced dataset:\n %s \n\n%srequests?prepid=%s \n%srequests?prepid=%s \n' % (
                current_request.get_attribute('prepid'),
                self.get_attribute('member_of_campaign'),
                next_campaign_id,
                flow_name,
                next_request.get_attribute('prepid'),
                self.get_attribute('prepid'),
                next_request.get_attribute('input_dataset'),
                l_type.baseurl(),
                current_request.get_attribute('prepid'),
                l_type.baseurl(),
                next_request.get_attribute('prepid')
            )
            current_request.notify(notification_subject, notification_text, accumulate=True)
        else:
            notification_subject = 'Reservation of request {0}'.format(next_request.get_attribute('prepid'))
            notification_text = 'The request {0} of campaign \n\t{2}\nhas been reserved as part of \n\t{1}\nas the next step for {4}\n\n{3}requests?prepid={4}\n{5}requests?prepid={6}\n'.format(
                next_request.get_attribute('prepid'),
                self.get_attribute('prepid'),
                next_campaign_id,
                l_type.baseurl(), current_request.get_attribute('prepid'),
                l_type.baseurl(), next_request.get_attribute('prepid'),
                )
            next_request.notify(notification_subject, notification_text, accumulate=True)
        return True

    def retrieve_original_action_item(self, adb, original_action_id=None):
        if not original_action_id:
            original_action_id = self.get_attribute('chain')[0]

        if not adb.document_exists(original_action_id):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'the chained request spawned from %s which does not exist' % original_action_id)
        ## retrieve what is the action the chained request started with
        original_action = adb.get(original_action_id)
        original_action_item = original_action['chains'][self.get_attribute('member_of_campaign')]['chains']
        if not self.get_attribute('prepid') in original_action_item:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'has no valid action in %s' %  original_action_id)

        original_action_item = original_action_item[self.get_attribute('prepid')]
        if 'flag' not in original_action_item:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The action %s is malformated' %  original_action_id)
        if not original_action_item['flag']:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'The action is disabled')
        if not 'block_number' in original_action_item or not original_action_item['block_number']:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The action has no valid block number')
        return original_action_item


    def toggle_last_request(self):

        ## let it toggle the last request to a given approval only if the chained request allows it
        if self.get_attribute('approval') == 'none':
            return 

        ccdb = database('chained_campaigns')
        mcm_cc = ccdb.get(self.get_attribute('member_of_campaign'))
        (next_campaign_id, flow_name) = mcm_cc['campaigns'][self.get_attribute('step')]
        fdb = database('flows')
        mcm_f = flow(fdb.get(flow_name))
        # check whether we have to do something even more subtle with the request
        if mcm_f.get_attribute('approval') == 'submit' or self.get_attribute('approval') == 'submit':
            rdb = database('requests')
            next_request = request(rdb.get(self.get_attribute('chain')[self.get_attribute('step')]))

            current_r_approval = next_request.get_attribute('approval')
            time_out = 0
            #self.logger.error('Trying to move %s from %s to submit'% (next_request.get_attribute('prepid'), current_r_approval))
            while current_r_approval != 'submit' and time_out <= 10:
                time_out += 1
                #get it back from db to avoid _red issues
                next_request = request(rdb.get(next_request.get_attribute('prepid')))
                with locker.lock('{0}-wait-for-approval'.format( next_request.get_attribute('prepid') )):
                    next_request.approve()
                    request_saved = rdb.save(next_request.json())
                    if not request_saved:
                        raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                                     'Could not save the new request %s while trying to move to submit approval' % (
                                next_request.get_attribute('prepid')))
                current_r_approval = next_request.get_attribute('approval')
                pass

        return True

    def set_last_status(self, status=None):
        if not status:
            rdb = database('requests')
            step_r = rdb.get(self.get_attribute('chain')[self.get_attribute('step')])
            new_last_status = step_r['status']
        else:
            new_last_status = status
        if new_last_status != self.get_attribute('last_status'):
            self.update_history({'action': 'set last status', 'step': new_last_status})
            self.set_attribute('last_status', new_last_status)
            return True
        else:
            return False

    def set_processing_status(self, pid=None, status=None):
        if not pid or not status:
            rdb = database('requests')
            step_r = rdb.get(self.get_attribute('chain')[self.get_attribute('step')])
            pid = step_r['prepid']
            status = step_r['status']

        if pid == self.get_attribute('chain')[self.get_attribute('step')]:
            expected_end = max(0, self.get_attribute('prepid').count('_') - 1)
            current_status = self.get_attribute('status')
            ## the current request is the one the status has just changed
            self.logger.log('processing status %s given %s and at %s and stops at %s ' % (
                current_status, status, self.get_attribute('step'), expected_end))
            if self.get_attribute('step') == expected_end and status == 'done' and current_status == 'processing':
                ## you're supposed to be in processing status
                self.set_status()
                return True
                ##only when updating with a submitted request status do we change to processing
            if status in ['submitted'] and current_status == 'new':
                self.set_status()
                return True
            return False
        else:
            return False

    def set_priority(self, level):
        rdb = database('requests')
        okay = True
        for r in self.get_attribute('chain'):
            req = request(rdb.get(r))
            ##only those that can still be changed
            #set to the maximum priority
            if not req.change_priority(priority().priority(level)):
                self.logger.log('Could not save updated priority for %s' % r)
                okay = False
        return okay

    def inspect(self):
        not_good = {"prepid": self.get_attribute('prepid'), "results": False}

        if self.get_attribute('last_status') == 'done':
            return self.inspect_done()

        not_good.update({
            'message': 'Nothing to inspect on chained request in %s last status' % ( self.get_attribute('last_status'))})
        return not_good

    def inspect_done(self):
        return self.flow_trial()

    def get_timeout(self, scratch=False):
        if scratch:
            req_ids = self.get_attribute('chain')
        else:
            req_ids = self.get_attribute('chain')[ self.get_attribute('step'):]
        rdb = database('requests')
        t=0
        for (index,req_id) in enumerate(req_ids):
            mcm_r = request(rdb.get(req_id))
            if not mcm_r.is_root: continue
            onet = mcm_r.get_timeout()
            if onet>t:
                t=onet
        #get the max and apply to all as a conservative estimation
        #this should probably be a bit more subtle
        return t*len(req_ids)
            
    def get_setup(self, directory='', events=None, run=False, validation=False, scratch=False):
        if scratch:
            req_ids = self.get_attribute('chain')
        else:
            req_ids = self.get_attribute('chain')[ self.get_attribute('step'):]
        rdb = database('requests')
        setup_file = ''
        for (index,req_id) in enumerate(req_ids):
            req = request(rdb.get(req_id))
            ev = events
            if not ev and index!=0 and not req.is_root:
                ev = -1
            setup_file += req.get_setup_file(directory=directory, events=ev, run=run, do_valid=validation)
        return setup_file
