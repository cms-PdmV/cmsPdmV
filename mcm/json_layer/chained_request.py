from json_base import json_base
from json_layer.request import request
from json_layer.campaign import campaign
from flow import flow

from couchdb_layer.prep_database import database
import json
from tools.priority import priority
import traceback


class chained_request(json_base):
    class CampaignAlreadyInChainException(Exception):
        def __init__(self, campaign):
            self.c = campaign
            chained_request.logger.error('Campaign %s is already member of the chain.' % (self.c))

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
            chained_request.logger.error('Campaign %s is stopped' % (self.name))

        def __str__(self):
            return 'Error: ' + self.name + ' is stopped.'

    class EnergyInconsistentException(NotApprovedException):
        def __init__(self, oname):
            self.name = str(oname)
            chained_request.logger.error('Campaign %s has inconsistent energy' % (self.name))

        def __str__(self):
            return 'Error: Campaign ' + self.name + ' has inconsistent energy.'

    def __init__(self, json_input={}):

        self._json_base__approvalsteps = ['none', 'flow', 'submit']
        #self._json_base__status = ['new','started','done']

        self._json_base__status = ['new', 'processing', 'done']

        self._json_base__schema = {
            '_id': '',
            'chain': [],
            'approval': self.get_approval_steps()[0],
            'step': 0,
            'analysis_id': [],
            'pwg': '',
            #'generators':'', #prune
            #'priority':-1, #prune
            'prepid': '',
            #'alias':'', #prune
            'dataset_name': '',
            'total_events': -1,
            'history': [],
            'member_of_campaign': '',
            #'generator_parameters':[], #prune
            #'request_parameters':{} # json with user prefs #prune
            'last_status': 'new',
            'status': self.get_status_steps()[0]
        }
        # update self according to json_input
        self.update(json_input)
        self.validate()


    def flow_trial(self, input_dataset='', block_black_list=[], block_white_list=[]):
        chainid = self.get_attribute('prepid')
        try:
            if self.flow():
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

    def flow(self, input_dataset='', block_black_list=[], block_white_list=[]):
        return self.flow_to_next_step(input_dataset, block_black_list, block_white_list)
        #return self.flow_to_next_step_clean(input_dataset,  block_black_list,  block_white_list)

    def flow_to_next_step(self, input_dataset='', block_black_list=[], block_white_list=[]):
        self.logger.log('Flowing chained_request %s to next step...' % (self.get_attribute('_id')))
        if not self.get_attribute('chain'):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'chained_request %s has got no root' % (
                                                             self.get_attribute('_id')))

        #this operation requires to access all sorts of objects
        rdb = database('requests')
        cdb = database('campaigns')
        ccdb = database('chained_campaigns')
        crdb = database('chained_requests')
        fdb = database('flows')
        adb = database('actions')

        current_step = self.get_attribute('step')
        current_id = self.get_attribute('chain')[current_step]
        next_step = current_step + 1

        if not rdb.document_exists(current_id):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'the current request %s does not exist' % ( current_id))

        current_request = request(rdb.get(current_id))
        current_campaign = campaign(cdb.get(current_request.get_attribute('member_of_campaign')))

        if not ccdb.document_exists(self.get_attribute('member_of_campaign')):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'the chain rqeuest %s is member of %s that does not exist' % (
                                                             self.get_attribute('_id'),
                                                             self.get_attribute('member_of_campaign')))
        mcm_cc = ccdb.get(self.get_attribute('member_of_campaign'))
        if next_step >= len(mcm_cc['campaigns']):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'chained_campaign %s does not allow any further flowing.' % (
                                                             self.get_attribute('member_of_campaign')))
            ## is the current request in the proper approval
        allowed_request_approvals = ['submit']
        if current_request.get_attribute('approval') not in allowed_request_approvals:
            raise self.NotApprovedException(current_request.get_attribute('prepid'),
                                            current_request.get_attribute('approval'), allowed_request_approvals)
            ## is the current request in the proper status
        allowed_request_statuses = ['submitted', 'done']
        if current_request.get_attribute('status') not in allowed_request_statuses:
            raise self.NotInProperStateException(current_request.get_attribute('prepid'), allowed_request_statuses)

        original_action_id = self.get_attribute('chain')[0]
        root_request_id = original_action_id
        if not adb.document_exists(original_action_id):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'the chained request spawned from %s which does not exist' % (
                                                             original_action_id))

        ## retrieve what is the action the chained request started with
        original_action = adb.get(original_action_id)
        original_action_item = original_action['chains'][self.get_attribute('member_of_campaign')]['chains']
        if not self.get_attribute('prepid') in original_action_item:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'has no valid action in %s' % ( original_action_id))

        original_action_item = original_action_item[self.get_attribute('prepid')]
        if 'flag' not in original_action_item:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The action %s is malformated' % ( original_action_id))
        if not original_action_item['flag']:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'), 'The action is disabled')
        if not 'block_number' in original_action_item or not original_action_item['block_number']:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The action has no valid block number')

        if current_request.get_attribute('completed_events') <= 0:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The number of events completed is negative or null')

        ## what is the campaign to go to next and with which flow
        (next_campaign_id, flow_name) = mcm_cc['campaigns'][next_step]
        if not fdb.document_exists(flow_name):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The flow %s does not exist' % ( flow_name ))
        if not cdb.document_exists(next_campaign_id):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The next campaign %s does not exist' % ( next_campaign_id))
        mcm_f = flow(fdb.get(flow_name))
        if not 'sequences' in mcm_f.get_attribute('request_parameters'):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'The flow %s does not contain sequences information.' % (
                                                             flow_name))
        next_campaign = campaign(cdb.get(next_campaign_id))
        if len(next_campaign.get_attribute('sequences')) != len(mcm_f.get_attribute('request_parameters')['sequences']):
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'the sequences changes in flow %s are not consistent with the next campaign %s' % (
                                                             flow_name, next_campaign_id))

        if next_campaign.get_attribute('energy') != current_campaign.get_attribute('energy'):
            raise self.EnergyInconsistentException(next_campaign.get_attribute('prepid'))

        ## check that it is allowed to flow
        allowed_flow_approvals = ['flow', 'submit']
        ###### cascade of checks
        # if flow allows -> do it
        ## else if chained_request allows -> do it
        # check all approvals (if flow say yes -> allowing policy)
        if not mcm_f.get_attribute('approval') in allowed_flow_approvals:
            if not self.get_attribute('approval') in allowed_flow_approvals:
                raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                             'Neither the flow (%s) nor the chained request (%s) approvals allow for flowing' % (
                                                                 mcm_f.get_attribute('approval'),
                                                                 self.get_attribute('approval')))

        if next_campaign.get_attribute('status') == 'stopped':
            raise self.CampaignStoppedException(next_campaign_id)

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
                raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                             'This should never happen. (%s) is next according to step (%s), but is not in new status (%s)' % (
                                                                 next_id, next_step, next_request.get_attribute('status')))
        else:
            ## look in *other* chained campaigns whether you can suck in an existing request
            ## look up all chained requests that start from the same root request
            ## remove <pwg>-chain_ and the -serial number, replacing _ with a .
            toMatch = '.'.join(self.get_attribute('prepid').split('_')[1:][0:next_step + 1]).split('-')[0]
            related_crs = crdb.queries(['root_request==%s' % (root_request_id)])
            for existing_cr in related_crs:
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
                    else:
                        next_id = mcm_cr.get_attribute('chain')[next_step]
                        break
            if next_id:
                approach = 'use'
            else:
                approach = 'create'

        if approach == 'create':
            from rest_api.RequestPrepId import RequestPrepId

            next_id = RequestPrepId().next_prepid(current_request.get_attribute('pwg'), next_campaign_id)
            next_request = request(next_campaign.add_request({"prepid": next_id, "_id": next_id}))
            to_be_transfered = ['pwg', 'dataset_name', 'generators', 'process_string', 'analysis_id', 'mcdb_id']
            for key in to_be_transfered:
                next_request.set_attribute(key, current_request.get_attribute(key))
            next_request.set_attribute("member_of_chain", [self.get_attribute('_id')])
            next_request.update_history({'action': 'join chain', 'step': self.get_attribute('_id')})
            chain = self.get_attribute('chain')
            chain.append(next_id)
            self.set_attribute("chain", chain)
            self.update_history({'action': 'add request', 'step': next_id})

        elif approach == 'use':
            ## there exists a request in another chained campaign that can be re-used here.
            # take this one. advance and go on
            if not next_id in self.get_attribute('chain'):
                #join to the chain
                chain = self.get_attribute('chain')
                chain.append(next_id)
                self.set_attribute("chain", chain)
                self.update_history({'action': 'flow', 'step': str(next_step)})
            self.set_attribute('step', next_step)
            next_request = request(rdb.get(next_id))
            if not self.get_attribute("prepid") in next_request.get_attribute("member_of_chain"):
                ## register the chain to the next request
                chains = next_request.get_attribute("member_of_chain")
                chains.append(self.get_attribute("prepid"))
                next_request.set_attribute("member_of_chain", chains)
                next_request.update_history({'action': 'join chain', 'step': self.get_attribute('_id')})
                saved = rdb.update(next_request.json())
                if not saved:
                    raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                                 'Unable to save %s with updated member_of_chains' % (
                                                                     next_id))
                return True
        elif approach == 'patch':
            ## there exists already a request in the chain (step!=last) and it is usable for the next stage
            next_request = request(rdb.get(next_id))
            next_request.set_attribute('version', next_request.get_attribute('version') + 1)
        else:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'Unrecognized approach %s' % ( approach ))

        #current_request -> next_request
        #current_campaign -> next_campaign

        ##determine whether we have an input dataset for the next request
        if len(current_request.get_attribute('reqmgr_name')):
            last_wma = current_request.get_attribute('reqmgr_name')[-1]
            if 'content' in last_wma and 'pdmv_dataset_name' in last_wma['content']:
                input_dataset = last_wma['content']['pdmv_dataset_name']
            else:
                statsDB = database('stats', url='http://cms-pdmv-stats.cern.ch:5984/')
                if statsDB.document_exists(last_wma['name']):
                    latestStatus = statsDB.get(last_wma['name'])
                    input_dataset = latestStatus['pdmv_dataset_name']
        if input_dataset:
            next_request.set_attribute('input_filename', input_dataset)

        ## transfer the number of events to process (could be revised later on)
        next_request.set_attribute('total_events', current_request.get_attribute('completed_events'))

        ## determine if this is a root -> non-root transition to potentially apply staged number
        if 'staged' in original_action_item or 'threshold' in original_action_item:
            if current_campaign.get_attribute('root') != 1 and next_campaign.get_attribute('root') == 1:
                if 'staged' in original_action_item:
                    next_request.set_attribute('total_events', original_action_item['staged'])
                elif 'threshold' in original_action_item:
                    next_request.set_attribute('total_events', int(
                        current_request.get_attribute('completed_events') * float(
                            original_action_item['threshold']) / 100.))

        ## set blocks restriction if any
        if block_black_list:
            next_request.set_attribute('block_black_list', block_black_list)
        if block_white_list:
            next_request.set_attribute('block_white_list', block_white_list)

        ## register the flow to the request
        next_request.set_attribute('flown_with', flow_name)

        ## setup the keep output parameter
        keep = []
        for s in next_request.get_attribute('sequences'):
            keep.append(False)
        keep[-1] = True
        next_request.set_attribute('keep_output', keep)

        ## another copy/paste
        def put_together(nc, fl, new_req):
            # copy the sequences of the flow
            sequences = []
            for i, step in enumerate(nc.get_attribute('sequences')):
                flag = False # states that a sequence has been found
                for name in step:
                    if name in fl.get_attribute('request_parameters')['sequences'][i]:
                        # if a seq name is defined, store that in the request
                        sequences.append(step[name])

                        # if the flow contains any parameters for the sequence,
                        # then override the default ones inherited from the campaign
                        if fl.get_attribute('request_parameters')['sequences'][i][name]:
                            for key in fl.get_attribute('request_parameters')['sequences'][i][name]:
                                sequences[-1][key] = fl.get_attribute('request_parameters')['sequences'][i][name][key]
                                # to avoid multiple sequence selection
                            # continue to the next step (if a valid seq is found)
                        flag = True
                        break

                # if no sequence has been found, use the default
                if not flag:
                    sequences.append(step['default'])

            new_req.set_attribute('sequences', sequences)
            # override request's parameters
            for key in fl.get_attribute('request_parameters'):
                if key == 'sequences':
                    continue
                else:
                    if key in new_req.json():
                        new_req.set_attribute(key, fl.get_attribute('request_parameters')[key])

        ##assemble the campaign+flow => request
        put_together(next_campaign, mcm_f, next_request)


        next_request.update_history({'action': 'flow', 'step': self.get_attribute('prepid')})
        request_saved = rdb.save(next_request.json())

        if not request_saved:
            raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                         'Could not save the new request %s' % (
                                                             next_request.get_attribute('prepid')))

        ## inspect priority
        self.set_priority(original_action_item['block_number'])

        # sync last status
        self.set_attribute('last_status', next_request.get_attribute('status'))
        # we can only be processing at this point
        self.set_attribute('status', 'processing')
        # set to next step
        self.set_attribute('step', next_step)

        notification_subject = 'Flow for request %s in %s' % (current_request.get_attribute('prepid'), next_campaign_id)
        notification_text = 'The request %s has been flown within:\n \t %s \n into campaign:\n \t %s \n using:\n \t %s \n creating the new request:\n \t %s \n as part of:\n \t %s \n and from the produced dataset:\n %s \n ' % (
            current_request.get_attribute('prepid'),
            self.get_attribute('member_of_campaign'),
            next_campaign_id,
            flow_name,
            next_request.get_attribute('prepid'),
            self.get_attribute('prepid'),
            next_request.get_attribute('input_filename')
        )
        current_request.notify(notification_subject, notification_text)
        return True

    def toggle_last_request(self):
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
                next_request.approve()
                request_saved = rdb.save(next_request.json())
                if not request_saved:
                    raise self.ChainedRequestCannotFlowException(self.get_attribute('_id'),
                                                                 'Could not save the new request %s while trying to move to submit approval' % (
                                                                     next_request.get_attribute('prepid')))
                current_r_approval = next_request.get_attribute('approval')
                pass

        return True

    # add a new request to the chain
    def add_request(self, data={}):
        self.logger.log('Adding new request to chained_request %s' % (self.get_attribute('_id')))

        # import prep-id generator
        try:
            from rest_api.RequestPrepId import RequestPrepId
        except ImportError as ex:
            self.logger.error('Could not import prep-id generator class. Reason: %s' % (ex), level='critical')
            return {}
        try:
            req = request(json_input=data)
        except Exception as ex:
            self.logger.error('Could not build request object. Reason: %s' % (ex))
            return {}

        #chain_specific = ['threshold',  'block_number',  'staged']

        ## JR remove from schema
        ##this was removed as part of cleaning things up
        #if len(self.get_attribute('request_parameters')) > 0:
        #    changes = self.get_attribute('request_parameters')
        #    for key in changes:
        #        if key not in chain_specific:
        #            req.set_attribute(key, changes[key])

        # get the chain and inherit
        #req.set_attribute("generators", self.get_attribute("generators"))
        #req.set_attribute("total_events", self.get_attribute("total_events")) ## this was taken earlier, with staged number in consideration
        req.set_attribute("dataset_name", self.get_attribute("dataset_name"))
        req.set_attribute("pwg", self.get_attribute("pwg"))
        #JR removed from schema req.set_attribute("priority", self.get_attribute("priority") )
        #JR clear the fragment in flowing: always
        req.set_attribute('name_of_fragment', '')
        req.set_attribute('cvs_tag', '')
        req.set_attribute('fragment_tag', '')
        req.set_attribute('fragment', '')
        req.set_attribute('history', [])
        req.set_attribute('reqmgr_name', [])

        #JR
        #clean the mcdbid in the flown request
        #if req.get_attribute('mcdbid')>=0:
        #    req.set_attribute('mcdbid',0)

        # get the new prepid and append it to the chain
        prepid = \
            json.loads(RequestPrepId().generate_prepid(req.get_attribute("pwg"), req.get_attribute('member_of_campaign')))[
                "prepid"]
        chain = self.get_attribute("chain")
        if not chain or chain is None:
            chain = []
        flag = False
        for pid in chain:
            #if req.get_attribute('member_of_campaign') in pid:
            if pid.split('-')[1] == req.get_attribute('member_of_campaign'):
                flag = True
                break

        if not flag:
            chain.append(prepid)
            self.set_attribute("chain", chain)
            #self.logger.log('Adding %s to the chain %s'%(prepid,chain))
        else:
            raise self.CampaignAlreadyInChainException(req.get_attribute('member_of_campaign'))

        req.set_attribute('_id', prepid)
        req.set_attribute('prepid', prepid)
        ## JR: add what the request is member of N.B: that breaks down if a digi-reco request has to be member of two chains (R1,R4)
        req.set_attribute('member_of_chain', [self.get_attribute('_id')])

        ## reset the status and approval chain
        req.set_status(0)
        req.approve(0)

        ### mode the approval of the new request to the approval of the chained request
        if not req.is_root:
            self.logger.log('The newly created request %s is not root, the chained request has approval %s' % (
                req.get_attribute('prepid'),
                self.get_attribute('approval')
            ))

            #if self.get_attribute('approval') == 'approve':
            #toggle the request approval to 'approved'?

            if self.get_attribute('approval') == 'submit':
                req.set_status(to_status='approved')
                req.approve(to_approval='submit')


        # update history
        req.update_history({'action': 'join chain', 'step': self.get_attribute('_id')})
        self.update_history({'action': 'add request', 'step': req.get_attribute('_id')})

        # set request approval status to new
        #req.approve(0)
        return req.json()

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
        for r in self.get_attribute('chain'):
            req = request(rdb.get(r))
            ##only those that can still be changed
            if not req.get_attribute('status') in ['submitted', 'done']:
                #set to the maximum priority
                req.set_attribute('priority', max(req.get_attribute('priority'), priority().priority(level)))
                saved = rdb.update(req.json())
                if not saved:
                    self.logger.log('Could not save updated priority for %s' % ( r))
                    raise Exception('Could not save updated priority for %s' % ( r))

    def inspect(self):
        not_good = {"prepid": self.get_attribute('prepid'), "results": False}

        if self.get_attribute('last_status') == 'done':
            return self.inspect_done()

        not_good.update({
            'message': 'Nothing to inspect on chained request in %s last status' % ( self.get_attribute('last_status'))})
        return not_good

    def inspect_done(self):
        return self.flow_trial()
        

        
        
