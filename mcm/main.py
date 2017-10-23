from rest_api.ControlActions import Search, MultiSearch, RenewCertificate, Communicate
from rest_api.RestAPIMethod import RESTResourceIndex, RESTResource
from rest_api.RequestActions import ImportRequest, ManageRequest, DeleteRequest, GetRequest, GetRequestByDataset, UpdateRequest, GetCmsDriverForRequest, GetFragmentForRequest, GetSetupForRequest, ApproveRequest, UploadConfig, InjectRequest, ResetRequestApproval, SetStatus, GetStatus, GetEditable, GetDefaultGenParams, CloneRequest, RegisterUser, MigrateRequest, MigratePage, GetActors, NotifyUser, InspectStatus, UpdateStats, RequestsFromFile, TestRequest, StalledReminder, RequestsReminder, RequestPerformance, SearchableRequest, UpdateMany, GetAllRevisions, ListRequestPrepids, OptionResetForRequest, GetRequestOutput, GetInjectCommand, GetUploadCommand, GetUniqueValues, PutToForceComplete, ForceCompleteMethods, Reserve_and_ApproveChain, TaskChainRequestDict, RequestsPriorityChange
from rest_api.CampaignActions import CreateCampaign, DeleteCampaign, UpdateCampaign, GetCampaign, ToggleCampaignStatus, ApproveCampaign, GetCmsDriverForCampaign, ListAllCampaigns, InspectRequests, InspectCampaigns
from rest_api.ChainedCampaignActions import ChainedCampaignsPriorityChange, CreateChainedCampaign, DeleteChainedCampaign, GetChainedCampaign, UpdateChainedCampaign, InspectChainedRequests, InspectChainedCampaigns, SelectNewChainedCampaigns
from rest_api.ChainedRequestActions import ChainsFromTicket, ChainedRequestsPriorityChange, UpdateChainedRequest, DeleteChainedRequest, GetChainedRequest,  FlowToNextStep,  ApproveRequest as ApproveChainedRequest, InspectChain, RewindToPreviousStep, SearchableChainedRequest, TestChainedRequest, GetSetupForChains, TaskChainDict, InjectChainedRequest, SoftResetChainedRequest, ToForceFlowList, RemoveFromForceFlowList
from rest_api.FlowActions import CreateFlow,  UpdateFlow,  DeleteFlow,  GetFlow,  ApproveFlow
from rest_api.RequestPrepId import RequestPrepId
from rest_api.ChainedRequestPrepId import ChainedRequestPrepId
from rest_api.LogActions import ReadInjectionLog, GetVerbosities
from rest_api.UserActions import GetUserRole, GetAllRoles, GetAllUsers, AddRole, AskRole, ChangeRole, GetUser, SaveUser, GetUserPWG, FillFullNames, NotifyPWG
from rest_api.BatchActions import HoldBatch, GetBatch, AnnounceBatch, InspectBatches, ResetBatch, NotifyBatch
from rest_api.InvalidationActions import GetInvalidation, DeleteInvalidation, AnnounceInvalidations, ClearInvalidations, AcknowledgeInvalidation
from rest_api.DashboardActions import GetBjobs, GetLogFeed, GetLogs, GetRevision, GetStartTime, GetQueueInfo
from rest_api.MccmActions import GetMccm, UpdateMccm, CreateMccm, DeleteMccm, CancelMccm, GetEditableMccmFields, GenerateChains, MccMReminderProdManagers, MccMReminderGenContacts, CalculateTotalEvts
from rest_api.SettingsActions import GetSetting, UpdateSetting, SaveSetting
from rest_api.TagActions import GetTags, AddTag, RemoveTag
from rest_api.NotificationActions import CheckNotifications, FetchNotifications, SaveSeen, FetchActionObjects, FetchGroupActionObjects, SearchNotifications

from json_layer.sequence import sequence #to get campaign sequences
from tools.settings import settings
from tools.communicator import communicator
from tools.logger import UserFilter, MemoryFilter
from flask_restful import Api
from flask import Flask, send_from_directory, make_response

import logging
import logging.handlers
import json
import cherrypy
import os
import shelve
import subprocess
import imp
import datetime

start_time = datetime.datetime.now().strftime("%c")
app = Flask(__name__)
api = Api(app)
app.url_map.strict_slashes = False
start_time = datetime.datetime.now().strftime("%c")

@app.route('/campaigns')
def campaigns_html():
    return send_from_directory('HTML', 'campaigns.html')
@app.route('/requests')
def requests_html():
    return send_from_directory('HTML', 'requests.html')
@app.route('/edit')
def edit_html():
    return send_from_directory('HTML', 'edit.html')
@app.route('/flows')
def flows_html():
    return send_from_directory('HTML', 'flows.html')
@app.route('/chained_campaigns')
def chained_campaigns_html():
    return send_from_directory('HTML', 'chained_campaigns.html')
@app.route('/chained_requests')
def chained_requests_html():
    return send_from_directory('HTML', 'chained_requests.html')
@app.route('/priority_change')
def priority_change_html():
    return send_from_directory('HTML', 'priority_change.html')
@app.route('/')
def index_html():
    return send_from_directory('HTML', 'index.html')
@app.route('/create')
def create_html():
    return send_from_directory('HTML', 'create.html')
@app.route('/injectAndLog')
def injectAndLog_html():
    return send_from_directory('HTML', 'injectAndLog.html')
@app.route('/users')
def users_html():
    return send_from_directory('HTML', 'users.html')
@app.route('/batches')
def batches_html():
    return send_from_directory('HTML', 'batches.html')
@app.route('/getDefaultSequences')
def getDefaultSequences():
    tmpSeq = sequence()._json_base__schema
    return json.dumps(tmpSeq)
@app.route('/injection_status')
def injection_status_html():
    return send_from_directory('HTML', 'injection_status.html')
@app.route('/mccms')
def mccms_html():
    return send_from_directory('HTML', 'mccms.html')
@app.route('/settings')
def settings_html():
    return send_from_directory('HTML', 'settings.html')
@app.route('/invalidations')
def invalidations_html():
    return send_from_directory('HTML', 'invalidations.html')
@app.route('/edit_many')
def edit_many_html():
    return send_from_directory('HTML', 'edit_many.html')
@app.route('/dashboard')
def dashboard_html():
    return send_from_directory('HTML', 'dashboard.html')
@app.route('/graph_painter')
def graph_painter_html():
    return send_from_directory('HTML', 'graph_painter.html')
@app.route('/graph_representation')
def graph_representation_html():
    return send_from_directory('HTML', 'graph.html')
@app.route('/scripts/<path:path>')
def send_static(path):
    return send_from_directory('scripts', path)
@app.route('/HTML/<path:path>')
def send_HTML(path):
    return send_from_directory('HTML', path)

api.add_resource(Search, '/search')
api.add_resource(MultiSearch, '/multi_search')

# REST API - RESTResourceIndex is the directory of available commands
api.add_resource(
    RESTResourceIndex,
    '/restapi',
    '/restapi/requests',
    '/restapi/campaigns',
    '/restapi/chained_requests',
    '/restapi/chained_campaigns',
    '/restapi/actions',
    '/restapi/flows',
    '/restapi/users',
    '/restapi/batches',
    '/restapi/invalidations',
    '/restapi/dashboard',
    '/restapi/mccms',
    '/restapi/settings',
    '/restapi/tags',
    '/restapi/control',
    '/restapi/notifications',
    '/public',
    '/public/restapi',
    '/public/restapi/requests'
)
#
### create a restriction-free urls, with limited capabilities
api.add_resource(GetRequest, '/public/restapi/requests/get')
#api.add_resource(GetFragmentForRequest, '/public/restapi/requests/get_fragment')
api.add_resource(
    GetSetupForRequest,
    '/public/restapi/requests/get_test/<string:prepid>/<int:events>',
    '/public/restapi/requests/get_test/<string:prepid>',
    '/public/restapi/requests/get_setup/<string:prepid>/<int:events>',
    '/public/restapi/requests/get_setup/<string:prepid>',
    '/public/restapi/requests/get_valid/<string:prepid>/<int:events>',
    '/public/restapi/requests/get_valid/<string:prepid>'
)
#api.add_resource(GetStatus, '/public/restapi/requests/get_status')
#api.add_resource(GetActors, '/public/restapi/requests/get_actors')
#api.add_resource(GetRequestByDataset, '/public/restapi/requests/produces')
#api.add_resource(GetRequestOutput, '/public/restapi/requests/output')
#api.add_resource(RESTResourceIndex, '/public/restapi/chained_requests')
api.add_resource(
    GetSetupForChains,
    '/public/restapi/chained_requests/get_setup/<string:chained_request_id>',
    '/public/restapi/chained_requests/get_test/<string:chained_request_id>',
    '/public/restapi/chained_requests/get_valid/<string:chained_request_id>'
)
api.add_resource(TaskChainDict, '/public/restapi/chained_requests/get_dict/<string:chained_request_id>')
#api.add_resource(TaskChainRequestDict, '/public/restapi/requests/get_dict')
#
## REST User actions
api.add_resource(GetUserRole, '/restapi/users/get_role')
api.add_resource(
    GetUserPWG,
    '/restapi/users/get_pwg',
    '/restapi/users/get_pwg/<string:user_id>'
)
#api.add_resource(GetAllRoles, '/restapi/users/get_all_roles')
#api.add_resource(GetAllUsers, '/restapi/users/get_all_users')
#api.add_resource(AddRole, '/restapi/users/add_role')
#api.add_resource(AskRole, '/restapi/users/ask_role')
#api.add_resource(ChangeRole, '/restapi/users/change_role')
#api.add_resource(GetUser, '/restapi/users/get')
#api.add_resource(SaveUser, '/restapi/users/save')
#api.add_resource(SaveUser, '/restapi/users/update')
#api.add_resource(FillFullNames, '/restapi/users/fill_full_names')
#api.add_resource(NotifyPWG, '/restapi/users/notify_pwg')
#
## REST request actions
#api.add_resource(ImportRequest, '/restapi/requests/save')
#api.add_resource(UpdateRequest, '/restapi/requests/update')
#api.add_resource(ManageRequest, '/restapi/requests/manage')
#api.add_resource(DeleteRequest, '/restapi/requests/delete')
#api.add_resource(CloneRequest, '/restapi/requests/clone')
#api.add_resource(GetRequest, '/restapi/requests/get')
#api.add_resource(GetCmsDriverForRequest, '/restapi/requests/get_cmsDrivers')
#api.add_resource(ApproveRequest, '/restapi/requests/approve')
#api.add_resource(ResetRequestApproval, '/restapi/requests/reset')
#api.add_resource(ResetRequestApprovalhard, '/restapi/requests/soft_reset')
#api.add_resource(SetStatus, '/restapi/requests/status')
#api.add_resource(UploadConfig, '/restapi/requests/upload')
#api.add_resource(InjectRequest, '/restapi/requests/inject')
#api.add_resource(ReadInjectionLog, '/restapi/requests/injectlog')
#api.add_resource(GetEditable, '/restapi/requests/editable')
#api.add_resource(GetDefaultGenParams, '/restapi/requests/default_generator_params')
#api.add_resource(RegisterUser, '/restapi/requests/register')
#api.add_resource(NotifyUser, '/restapi/requests/notify')
#api.add_resource(MigrateRequest, '/restapi/requests/migrate')
#api.add_resource(InspectStatus, '/restapi/requests/inspect')
#api.add_resource(UpdateStats, '/restapi/requests/update_stats')
#api.add_resource(RequestsFromFile, '/restapi/requests/listwithfile')
#api.add_resource(TestRequest, '/restapi/requests/test')
#api.add_resource(SearchableRequest, '/restapi/requests/searchable')
#api.add_resource(RequestsReminder, '/restapi/requests/reminder')
#api.add_resource(StalledReminder, '/restapi/requests/stalled')
#api.add_resource(RequestPerformance, '/restapi/requests/perf_report')
#api.add_resource(UpdateMany, '/restapi/requests/update_many')
#api.add_resource(GetAllRevisions, '/restapi/requests/all_revs')
#api.add_resource(ListRequestPrepids, '/restapi/requests/search_view')
#api.add_resource(OptionResetForRequest, '/restapi/requests/option_reset')
#api.add_resource(GetInjectCommand, '/restapi/requests/get_inject')
#api.add_resource(GetUploadCommand, '/restapi/requests/get_upload')
#api.add_resource(GetUniqueValues, '/restapi/requests/unique_values')
#api.add_resource(PutToForceComplete, '/restapi/requests/add_forcecomplete')
#api.add_resource(ForceCompleteMethods, '/restapi/requests/forcecomplete')
#api.add_resource(Reserve_and_ApproveChain, '/restapi/requests/reserveandapprove')
#api.add_resource(RequestsPriorityChange, '/restapi/requests/priority_change')
#
## REST Campaign Actions
api.add_resource(CreateCampaign, '/restapi/campaigns/save')
api.add_resource(UpdateCampaign, '/restapi/campaigns/update')
api.add_resource(DeleteCampaign, '/restapi/campaigns/delete/<string:campaign_id>')
api.add_resource(GetCampaign, '/restapi/campaigns/get/<string:campaign_id>')
api.add_resource(
    ApproveCampaign,
    '/restapi/campaigns/approve/<string:campaign_ids>',
    '/restapi/campaigns/approve/<string:campaign_ids>/<int:index>'
)
#api.add_resource(GetAllCampaigns, '/restapi/campaigns/get_all')
api.add_resource(ToggleCampaignStatus, '/restapi/campaigns/status/<string:campaign_id>')
api.add_resource(GetCmsDriverForCampaign, '/restapi/campaigns/get_cmsDrivers/<string:campaign_id>')
#api.add_resource(MigratePage, '/restapi/campaigns/migrate')
api.add_resource(ListAllCampaigns, '/restapi/campaigns/listall')
api.add_resource(InspectRequests, '/restapi/campaigns/inspect/<string:campaign_id>')
api.add_resource(InspectCampaigns, '/restapi/campaigns/inspectall/<string:group>')
#
## REST Chained Campaign Actions
api.add_resource(CreateChainedCampaign, '/restapi/chained_campaigns/save')
api.add_resource(
    DeleteChainedCampaign,
    '/restapi/chained_campaigns/delete/<string:chained_campaign_id>',
    '/restapi/chained_campaigns/delete/<string:chained_campaign_id>/<string:force>'
)
api.add_resource(GetChainedCampaign, '/restapi/chained_campaigns/get/<string:chained_campaign_id>')
api.add_resource(UpdateChainedCampaign, '/restapi/chained_campaigns/update')
api.add_resource(InspectChainedRequests, '/restapi/chained_campaigns/inspect/<string:chained_campaign_ids>')
api.add_resource(InspectChainedCampaigns, '/restapi/chained_campaigns/inspectall/<string:action>')
api.add_resource(SelectNewChainedCampaigns, '/restapi/chained_campaigns/select/<string:flow_id>')
#api.add_resource(ListChainCampaignPrepids, '/restapi/chained_campaigns/search_view')
api.add_resource(ChainedCampaignsPriorityChange, '/restapi/chained_campaigns/priority_change')
#
## REST Chained Request Actions
#api.add_resource(ChainedRequestPrepId, '/restapi/chained_requests/request_chainid')
#api.add_resource(CreateChainedRequest, '/restapi/chained_requests/save')
api.add_resource(UpdateChainedRequest, '/restapi/chained_requests/update')
api.add_resource(DeleteChainedRequest, '/restapi/chained_requests/delete/<string:chained_request_id>')
api.add_resource(GetChainedRequest, '/restapi/chained_requests/get/<string:chained_request_id>')
api.add_resource(
    FlowToNextStep,
    '/restapi/chained_requests/flow',
    '/restapi/chained_requests/flow/<string:chained_request_id>',
    '/restapi/chained_requests/flow/<string:chained_request_id>/<string:action>',
    '/restapi/chained_requests/flow/<string:chained_request_id>/<string:action>/<string:reserve_campaign>'
)
api.add_resource(RewindToPreviousStep, '/restapi/chained_requests/rewind/<string:chained_request_ids>')
api.add_resource(
    ApproveChainedRequest,
    '/restapi/chained_requests/approve/<string:chained_request_id>',
    '/restapi/chained_requests/approve/<string:chained_request_id>/<int:step>'
)
api.add_resource(InspectChain, '/restapi/chained_requests/inspect/<string:chained_request_id>')
#api.add_resource(GetConcatenatedHistory, '/restapi/chained_requests/fullhistory')
api.add_resource(
    SearchableChainedRequest,
    '/restapi/chained_requests/searchable',
    '/restapi/chained_requests/searchable/<string:action>'
)
api.add_resource(
    InjectChainedRequest,
    '/restapi/chained_requests/inject/<string:chained_request_id>',
    '/restapi/chained_requests/get_inject/<string:chained_request_id>'
)
api.add_resource(SoftResetChainedRequest, '/restapi/chained_requests/soft_reset/<string:chained_request_id>')
api.add_resource(TestChainedRequest, '/restapi/chained_requests/test/<string:chained_request_id>')
#api.add_resource(TestOutputDSAlgo, '/restapi/chained_requests/test_ds_output')
#api.add_resource(ForceChainReqToDone, '/restapi/chained_requests/force_done')
#api.add_resource(ForceStatusDoneToProcessing, '/restapi/chained_requests/back_forcedone')
api.add_resource(ToForceFlowList, '/restapi/chained_requests/force_flow/<string:chained_request_ids>')
api.add_resource(RemoveFromForceFlowList, '/restapi/chained_requests/remove_force_flow/<string:chained_request_ids>')
api.add_resource(ChainedRequestsPriorityChange, '/restapi/chained_requests/priority_change')
api.add_resource(ChainsFromTicket, '/restapi/chained_requests/from_ticket')
#
## REST Flow Actions
api.add_resource(GetFlow, '/restapi/flows/get/<string:flow_id>')
api.add_resource(CreateFlow, '/restapi/flows/save')
api.add_resource(UpdateFlow, '/restapi/flows/update')
api.add_resource(DeleteFlow, '/restapi/flows/delete/<string:flow_id>')
api.add_resource(
    ApproveFlow,
    '/restapi/flows/approve/<string:flow_ids>',
    '/restapi/flows/approve/<string:flow_ids>/<int:step>'
)
#
## REST Batches Actions
api.add_resource(GetBatch, '/restapi/batches/get/<string:prepid>')
api.add_resource(AnnounceBatch, '/restapi/batches/announce')
api.add_resource(
    InspectBatches,
    '/restapi/batches/inspect',
    '/restapi/batches/inspect/<string:batch_id>/<int:n_to_go>',
    '/restapi/batches/inspect/<string:batch_id>'
)
api.add_resource(ResetBatch, '/restapi/batches/reset/<string:batch_ids>')
api.add_resource(HoldBatch, '/restapi/batches/hold/<string:batch_ids>')
api.add_resource(NotifyBatch, '/restapi/batches/notify')
# update, save, redirect, get all
#
## REST invalidation Actions
api.add_resource(GetInvalidation, '/restapi/invalidations/get/<string:invalidation_id>')
#api.add_resource(DeleteInvalidation, '/restapi/invalidations/delete')
#api.add_resource(AnnounceInvalidations, '/restapi/invalidations/announce')
#api.add_resource(ClearInvalidations, '/restapi/invalidations/clear')
#api.add_resource(AcknowledgeInvalidation, '/restapi/invalidations/acknowledge')
#api.add_resource(PutOnHoldInvalidation, '/restapi/invalidations/new_to_hold')
#api.add_resource(PutHoldtoNewInvalidations, '/restapi/invalidations/hold_to_new')
#
## REST dashboard Actions
api.add_resource(GetBjobs, '/restapi/dashboard/get_bjobs/<string:options>')
api.add_resource(
    GetLogFeed,
    '/restapi/dashboard/get_log_feed/<string:filename>',
    '/restapi/dashboard/get_log_feed/<string:filename>/<int:lines>'
)
api.add_resource(GetLogs, '/restapi/dashboard/get_logs')
api.add_resource(GetRevision, '/restapi/dashboard/get_revision')
api.add_resource(GetStartTime, '/restapi/dashboard/get_start_time')
#api.add_resource(GetVerbosities, '/restapi/dashboard/get_verbosities')
#api.add_resource(TestConnection, '/restapi/dashboard/get_connection')
#api.add_resource(ListReleases, '/restapi/dashboard/get_releases')
#api.add_resource(GetLocksInfo, '/restapi/dashboard/lock_info')
api.add_resource(GetQueueInfo, '/restapi/dashboard/queue_info')
#
## REST mccms Actions
#api.add_resource(GetMccm, '/restapi/mccms/get')
#api.add_resource(UpdateMccm, '/restapi/mccms/update')
#api.add_resource(CreateMccm, '/restapi/mccms/save')
#api.add_resource(DeleteMccm, '/restapi/mccms/delete')
#api.add_resource(CancelMccm, '/restapi/mccms/cancel')
#api.add_resource(GetEditableMccmFields, '/restapi/mccms/editable')
#api.add_resource(GenerateChains, '/restapi/mccms/generate')
#api.add_resource(MccMReminderProdManagers, '/restapi/mccms/reminder')
#api.add_resource(MccMReminderGenContacts, '/restapi/mccms/reminder_gen_contacts')
#api.add_resource(CalculateTotalEvts, '/restapi/mccms/update_total_events')
#
## REST settings Actions
#api.add_resource(GetSetting, '/restapi/settings/get')
#api.add_resource(UpdateSetting, '/restapi/settings/update')
#api.add_resource(SaveSetting, '/restapi/settings/save')
#
## REST tags Actions
#api.add_resource(GetTags, '/restapi/tags/get_all')
#api.add_resource(AddTag, '/restapi/tags/add')
#api.add_resource(RemoveTag, '/restapi/tags/remove')
#
## REST control Actions
api.add_resource(RenewCertificate, '/restapi/control/renew_cert')
#api.add_resource(ChangeVerbosity, '/restapi/control/set_verbosity')
#api.add_resource(TurnOffServer, '/restapi/control/turn_off')
#api.add_resource(ResetRESTCounters, '/restapi/control/reset_rest_counter')
api.add_resource(
    Communicate,
    '/restapi/control/communicate',
    '/restapi/control/communicate/<string:message_number>'
)
#
# REST notification Actions
api.add_resource(CheckNotifications, '/restapi/notifications/check')
api.add_resource(FetchNotifications, '/restapi/notifications/fetch')
api.add_resource(SaveSeen, '/restapi/notifications/seen')
api.add_resource(FetchActionObjects, '/restapi/notifications/fetch_actions')
api.add_resource(FetchGroupActionObjects, '/restapi/notifications/fetch_group_actions')
api.add_resource(SearchNotifications, '/restapi/notifications/search')

app.run(debug=True, host='0.0.0.0', port=4443, threaded=True, ssl_context=('/etc/pki/tls/certs/localhost.crt','/etc/pki/tls/private/localhost.key'))
#
###Define loggers
#
#log = cherrypy.log
#log.error_file = None
#log.access_file = None
#
##ERROR log file
#maxBytes = getattr(log, "rot_maxBytes", 10000000)
#backupCount = getattr(log, "rot_backupCount", 1000)
#fname = getattr(log, "rot_error_file", "logs/error.log")
#
#logger = logging.getLogger()
#logger.setLevel(0)
#
#ha = logging.handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
#error_formatter = logging.Formatter(fmt='[%(asctime)s][%(user)s][%(levelname)s] %(message)s',
#        datefmt='%d/%b/%Y:%H:%M:%S')
#
#usr_filt = UserFilter()
#ha.setFormatter(error_formatter)
#ha.addFilter(usr_filt)
#log.error_log.addHandler(ha)
#error_logger = logging.getLogger("mcm_error")
#error_logger.addHandler(ha)
#
## set up injection logger
###due to LogAdapter empty space for message will be added inside of it
#inject_formatter = logging.Formatter(fmt='[%(asctime)s][%(levelname)s]%(message)s',
#        datefmt='%d/%b/%Y:%H:%M:%S')
#inject_logger = logging.getLogger("mcm_inject")
#hi = logging.FileHandler('logs/inject.log', 'a')
#hi.setFormatter(inject_formatter)
#inject_logger.addHandler(hi)
#
##Access log file
#fname = getattr(log, "rot_access_file", "logs/access.log")
#h = logging.handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
#rest_formatter = logging.Formatter(fmt='{%(mem)s} [%(asctime)s][%(user)s][%(levelname)s] %(message)s',
#        datefmt='%d/%b/%Y:%H:%M:%S')
#
#mem_filt = MemoryFilter()
#h.setLevel(logging.DEBUG)
#h.setFormatter(rest_formatter)
#h.addFilter(usr_filt)
#h.addFilter(mem_filt)
#log.access_log.addHandler(h)
#
#def start():
#    error_logger.info(".mcm_rest_counter persistence opening")
#    error_logger.info("CherryPy version:%s" % (cherrypy.__version__))
#    RESTResource.counter = shelve.open('.mcm_rest_counter')
#
#def stop():
#    error_logger.info(".mcm_rest_counter persistence closing")
#    RESTResource.counter.close()
#    error_logger.info("Flushing communications")
#    com = communicator()
#    com.flush(0)
#
#def maintain():
#    if not cherrypy.engine.execv:
#        error_logger.info("going to maintenance")
#        subprocess.call("python2.6 main_tenance.py &", shell=True)
#
#cherrypy.engine.subscribe('start', start)
#cherrypy.engine.subscribe('stop', stop)
#cherrypy.engine.subscribe('exit', maintain)
#cherrypy.engine.signal_handler.handlers['SIGINT'] = cherrypy.engine.exit
#
##START the engine
#cherrypy.quickstart(root, config='configuration/cherrypy.conf')