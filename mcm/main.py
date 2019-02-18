from rest_api.ControlActions import Search, MultiSearch, RenewCertificate, Communicate, ChangeVerbosity, CacheInfo, CacheClear
from rest_api.RestAPIMethod import RESTResourceIndex, RESTResource
from rest_api.RequestActions import ImportRequest, ManageRequest, DeleteRequest, GetRequest, GetRequestByDataset, UpdateRequest, GetCmsDriverForRequest, GetFragmentForRequest, GetSetupForRequest, ApproveRequest, InjectRequest, ResetRequestApproval, SetStatus, GetStatus, GetStatusAndApproval, GetEditable, GetDefaultGenParams, CloneRequest, RegisterUser, GetActors, NotifyUser, InspectStatus, UpdateStats, RequestsFromFile, TestRequest, StalledReminder, RequestsReminder, SearchableRequest, UpdateMany, GetAllRevisions, ListRequestPrepids, OptionResetForRequest, GetRequestOutput, GetInjectCommand, GetUploadCommand, GetUniqueValues, PutToForceComplete, ForceCompleteMethods, Reserve_and_ApproveChain, TaskChainRequestDict, RequestsPriorityChange, UpdateEventsFromWorkflow, PPDTags
from rest_api.CampaignActions import CreateCampaign, DeleteCampaign, UpdateCampaign, GetCampaign, ToggleCampaignStatus, ApproveCampaign, GetCmsDriverForCampaign, ListAllCampaigns, InspectRequests, InspectCampaigns, HoldCampaigns
from rest_api.ChainedCampaignActions import ChainedCampaignsPriorityChange, CreateChainedCampaign, DeleteChainedCampaign, GetChainedCampaign, UpdateChainedCampaign, InspectChainedRequests, InspectChainedCampaigns, SelectNewChainedCampaigns
from rest_api.ChainedRequestActions import ForceChainReqToDone, ForceStatusDoneToProcessing, CreateChainedRequest, ChainsFromTicket, ChainedRequestsPriorityChange, UpdateChainedRequest, DeleteChainedRequest, GetChainedRequest,  FlowToNextStep, ApproveChainedRequest, InspectChain, RewindToPreviousStep, SearchableChainedRequest, TestChainedRequest, GetSetupForChains, TaskChainDict, InjectChainedRequest, SoftResetChainedRequest, ToForceFlowList, RemoveFromForceFlowList, GetUniqueChainedRequestValues
from rest_api.FlowActions import CreateFlow,  UpdateFlow,  DeleteFlow,  GetFlow,  ApproveFlow
from rest_api.RequestPrepId import RequestPrepId
from rest_api.ChainedRequestPrepId import ChainedRequestPrepId
from rest_api.LogActions import ReadInjectionLog, GetVerbosities
from rest_api.UserActions import GetUserRole, AddRole, AskRole, ChangeRole, GetUser, SaveUser, GetUserPWG, NotifyPWG
from rest_api.BatchActions import HoldBatch, GetBatch, AnnounceBatch, InspectBatches, ResetBatch, NotifyBatch
from rest_api.InvalidationActions import GetInvalidation, DeleteInvalidation, AnnounceInvalidations, ClearInvalidations, AcknowledgeInvalidation, PutHoldtoNewInvalidations, PutOnHoldInvalidation
from rest_api.DashboardActions import GetLocksInfo, GetBjobs, GetLogFeed, GetLogs, GetRevision, GetStartTime, GetQueueInfo
from rest_api.MccmActions import GetMccm, UpdateMccm, CreateMccm, DeleteMccm, CancelMccm, GetEditableMccmFields, GenerateChains, MccMReminderProdManagers, MccMReminderGenContacts, CalculateTotalEvts, CheckIfAllApproved
from rest_api.SettingsActions import GetSetting, UpdateSetting, SaveSetting
from rest_api.TagActions import GetTags, AddTag, RemoveTag
from rest_api.NotificationActions import CheckNotifications, FetchNotifications, SaveSeen, FetchActionObjects, FetchGroupActionObjects, SearchNotifications, MarkAsSeen
from rest_api.ListActions import GetList, UpdateList

from json_layer.sequence import sequence  # to get campaign sequences
from tools.communicator import communicator
from tools.logger import UserFilter, MemoryFilter
from flask_restful import Api
from flask import Flask, send_from_directory, request, g
from simplejson import dumps
from urllib2 import unquote
from tools.ssh_executor import ssh_executor

import signal
import logging
import logging.handlers
import shelve
import datetime
import sys


RESTResource.counter = shelve.open('.mcm_rest_counter')
start_time = datetime.datetime.now().strftime("%c")
app = Flask(__name__)
app.config.update(LOGGER_NAME="mcm_error")
api = Api(app)
app.url_map.strict_slashes = False

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
    return dumps(tmpSeq)

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

@app.route('/lists')
def stalled_html():
    return send_from_directory('HTML', 'lists.html')

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
    '/restapi/lists',
    '/public',
    '/public/restapi',
    '/public/restapi/requests',
    '/public/restapi/chained_requests'
)
#
# create a restriction-free urls, with limited capabilities
api.add_resource(
    GetFragmentForRequest,
    '/public/restapi/requests/get_fragment/<string:request_id>',
    '/public/restapi/requests/get_fragment/<string:request_id>/<int:version>')  # for legacy support

api.add_resource(
    GetSetupForRequest,
    '/public/restapi/requests/get_test/<string:prepid>/<int:events>',
    '/public/restapi/requests/get_test/<string:prepid>',
    '/public/restapi/requests/get_setup/<string:prepid>/<int:events>',
    '/public/restapi/requests/get_setup/<string:prepid>',
    '/public/restapi/requests/get_valid/<string:prepid>/<int:events>',
    '/public/restapi/requests/get_valid/<string:prepid>')
api.add_resource(GetStatus, '/public/restapi/requests/get_status/<string:request_ids>')
api.add_resource(GetStatusAndApproval, '/public/restapi/requests/get_status_and_approval/<string:prepid>')
api.add_resource(
    GetActors,
    '/public/restapi/requests/get_actors/<string:request_id>',
    '/public/restapi/requests/get_actors/<string:request_id>/<string:what>')
api.add_resource(GetRequestByDataset, '/public/restapi/requests/produces/<path:dataset>')
api.add_resource(
    GetRequestOutput,
    '/public/restapi/requests/output/<string:prepid>',
    '/public/restapi/requests/output/<string:prepid>/<string:is_chain>')
api.add_resource(
    GetSetupForChains,
    '/public/restapi/chained_requests/get_setup/<string:chained_request_id>',
    '/public/restapi/chained_requests/get_test/<string:chained_request_id>',
    '/public/restapi/chained_requests/get_valid/<string:chained_request_id>')
api.add_resource(TaskChainDict, '/public/restapi/chained_requests/get_dict/<string:chained_request_id>')
api.add_resource(TaskChainRequestDict, '/public/restapi/requests/get_dict/<string:request_id>')
# REST User actions
api.add_resource(GetUserRole, '/restapi/users/get_role')
api.add_resource(
    GetUserPWG,
    '/restapi/users/get_pwg',
    '/restapi/users/get_pwg/<string:user_id>')
api.add_resource(AddRole, '/restapi/users/add_role')
api.add_resource(AskRole, '/restapi/users/ask_role/<string:pwgs>')
api.add_resource(ChangeRole, '/restapi/users/change_role/<string:user_id>/<string:action>')
api.add_resource(GetUser, '/restapi/users/get/<string:user_id>')
api.add_resource(
    SaveUser,
    '/restapi/users/save',
    '/restapi/users/update')
api.add_resource(NotifyPWG, '/restapi/users/notify_pwg')
# REST request actions
api.add_resource(ImportRequest, '/restapi/requests/save')
api.add_resource(UpdateRequest, '/restapi/requests/update')
api.add_resource(ManageRequest, '/restapi/requests/manage')
api.add_resource(DeleteRequest, '/restapi/requests/delete/<string:request_id>')
api.add_resource(
    CloneRequest,
    '/restapi/requests/clone',
    '/restapi/requests/clone/<string:request_id>')
api.add_resource(
    GetRequest,
    '/restapi/requests/get/<string:request_id>',
    '/public/restapi/requests/get/<string:request_id>')
api.add_resource(GetCmsDriverForRequest, '/restapi/requests/get_cmsDrivers/<string:request_id>')
api.add_resource(
    ApproveRequest,
    '/restapi/requests/approve',
    '/restapi/requests/approve/<string:request_id>',
    '/restapi/requests/approve/<string:request_id>/<int:step>')
api.add_resource(
    ResetRequestApproval,
    '/restapi/requests/reset/<string:request_id>',
    '/restapi/requests/soft_reset/<string:request_id>')
api.add_resource(
    SetStatus,
    '/restapi/requests/status/<string:request_ids>',
    '/restapi/requests/status/<string:request_ids>/<int:step>')
api.add_resource(InjectRequest, '/restapi/requests/inject/<string:request_ids>')
api.add_resource(
    ReadInjectionLog,
    '/restapi/requests/injectlog/<string:request_id>',
    '/restapi/requests/injectlog/<string:request_id>/<int:lines>')
api.add_resource(GetEditable, '/restapi/requests/editable/<string:request_id>')
api.add_resource(GetDefaultGenParams, '/restapi/requests/default_generator_params/<string:request_id>')
api.add_resource(RegisterUser, '/restapi/requests/register/<string:request_ids>')
api.add_resource(NotifyUser, '/restapi/requests/notify')
api.add_resource(
    InspectStatus,
    '/restapi/requests/inspect/<string:request_ids>',
    '/restapi/requests/inspect/<string:request_ids>/<string:force>')
api.add_resource(
    UpdateStats,
    '/restapi/requests/update_stats/<string:request_id>',
    '/restapi/requests/update_stats/<string:request_id>/<string:refresh>',
    '/restapi/requests/update_stats/<string:request_id>/<string:refresh>/<string:forced>')
api.add_resource(UpdateEventsFromWorkflow, '/restapi/requests/fetch_stats_by_wf/<string:wf_id>')
api.add_resource(RequestsFromFile, '/restapi/requests/listwithfile')
api.add_resource(TestRequest, '/restapi/requests/test/<string:request_id>')
api.add_resource(SearchableRequest, '/restapi/requests/searchable')
api.add_resource(
    RequestsReminder,
    '/restapi/requests/reminder',
    '/restapi/requests/reminder/<string:what>',
    '/restapi/requests/reminder/<string:what>/<string:who>')
api.add_resource(
    StalledReminder,
    '/restapi/requests/stalled',
    '/restapi/requests/stalled/<int:time_since>',
    '/restapi/requests/stalled/<int:time_since>/<int:time_remaining>',
    '/restapi/requests/stalled/<int:time_since>/<int:time_remaining>/<float:below_completed>')
api.add_resource(UpdateMany, '/restapi/requests/update_many')
api.add_resource(GetAllRevisions, '/restapi/requests/all_revs/<string:request_id>')
api.add_resource(ListRequestPrepids, '/restapi/requests/search_view')
api.add_resource(OptionResetForRequest, '/restapi/requests/option_reset/<string:request_ids>')
api.add_resource(GetInjectCommand, '/restapi/requests/get_inject/<string:request_id>')
api.add_resource(GetUploadCommand, '/restapi/requests/get_upload/<string:request_id>')
api.add_resource(GetUniqueValues, '/restapi/requests/unique_values/<string:field_name>')
api.add_resource(PutToForceComplete, '/restapi/requests/add_forcecomplete')
api.add_resource(ForceCompleteMethods, '/restapi/requests/forcecomplete')
api.add_resource(Reserve_and_ApproveChain, '/restapi/requests/reserveandapprove/<string:chain_id>')
api.add_resource(RequestsPriorityChange, '/restapi/requests/priority_change')
api.add_resource(PPDTags, '/restapi/requests/ppd_tags/<string:request_id>')
# REST Campaign Actions
api.add_resource(CreateCampaign, '/restapi/campaigns/save')
api.add_resource(UpdateCampaign, '/restapi/campaigns/update')
api.add_resource(DeleteCampaign, '/restapi/campaigns/delete/<string:campaign_id>')
api.add_resource(GetCampaign, '/restapi/campaigns/get/<string:campaign_id>')
api.add_resource(
    ApproveCampaign,
    '/restapi/campaigns/approve/<string:campaign_ids>',
    '/restapi/campaigns/approve/<string:campaign_ids>/<int:index>')
api.add_resource(ToggleCampaignStatus, '/restapi/campaigns/status/<string:campaign_id>')
api.add_resource(GetCmsDriverForCampaign, '/restapi/campaigns/get_cmsDrivers/<string:campaign_id>')
api.add_resource(ListAllCampaigns, '/restapi/campaigns/listall')
api.add_resource(InspectRequests, '/restapi/campaigns/inspect/<string:campaign_id>')
api.add_resource(InspectCampaigns, '/restapi/campaigns/inspectall/<string:group>')
api.add_resource(HoldCampaigns, '/restapi/campaigns/on_hold')
# REST Chained Campaign Actions
api.add_resource(CreateChainedCampaign, '/restapi/chained_campaigns/save')
api.add_resource(
    DeleteChainedCampaign,
    '/restapi/chained_campaigns/delete/<string:chained_campaign_id>',
    '/restapi/chained_campaigns/delete/<string:chained_campaign_id>/<string:force>')
api.add_resource(GetChainedCampaign, '/restapi/chained_campaigns/get/<string:chained_campaign_id>')
api.add_resource(UpdateChainedCampaign, '/restapi/chained_campaigns/update')
api.add_resource(InspectChainedRequests, '/restapi/chained_campaigns/inspect/<string:chained_campaign_ids>')
api.add_resource(InspectChainedCampaigns, '/restapi/chained_campaigns/inspectall/<string:action>')
api.add_resource(SelectNewChainedCampaigns, '/restapi/chained_campaigns/select/<string:flow_id>')
api.add_resource(ChainedCampaignsPriorityChange, '/restapi/chained_campaigns/priority_change')
# REST Chained Request Actions
api.add_resource(CreateChainedRequest, '/restapi/chained_requests/save')
api.add_resource(UpdateChainedRequest, '/restapi/chained_requests/update')
api.add_resource(DeleteChainedRequest, '/restapi/chained_requests/delete/<string:chained_request_id>')
api.add_resource(GetChainedRequest, '/restapi/chained_requests/get/<string:chained_request_id>')
api.add_resource(
    FlowToNextStep,
    '/restapi/chained_requests/flow',
    '/restapi/chained_requests/flow/<string:chained_request_id>',
    '/restapi/chained_requests/flow/<string:chained_request_id>/<string:action>',
    '/restapi/chained_requests/flow/<string:chained_request_id>/<string:action>/<string:reserve_campaign>')
api.add_resource(RewindToPreviousStep, '/restapi/chained_requests/rewind/<string:chained_request_ids>')
api.add_resource(
    ApproveChainedRequest,
    '/restapi/chained_requests/approve/<string:chained_request_id>',
    '/restapi/chained_requests/approve/<string:chained_request_id>/<int:step>')
api.add_resource(InspectChain, '/restapi/chained_requests/inspect/<string:chained_request_id>')
api.add_resource(
    SearchableChainedRequest,
    '/restapi/chained_requests/searchable',
    '/restapi/chained_requests/searchable/<string:action>')
api.add_resource(
    InjectChainedRequest,
    '/restapi/chained_requests/inject/<string:chained_request_id>',
    '/restapi/chained_requests/get_inject/<string:chained_request_id>')
api.add_resource(SoftResetChainedRequest, '/restapi/chained_requests/soft_reset/<string:chained_request_id>')
api.add_resource(TestChainedRequest, '/restapi/chained_requests/test/<string:chained_request_id>')
api.add_resource(ForceChainReqToDone, '/restapi/chained_requests/force_done/<string:chained_request_ids>')
api.add_resource(ForceStatusDoneToProcessing, '/restapi/chained_requests/back_forcedone/<string:chained_request_ids>')
api.add_resource(ToForceFlowList, '/restapi/chained_requests/force_flow/<string:chained_request_ids>')
api.add_resource(RemoveFromForceFlowList, '/restapi/chained_requests/remove_force_flow/<string:chained_request_ids>')
api.add_resource(ChainedRequestsPriorityChange, '/restapi/chained_requests/priority_change')
api.add_resource(ChainsFromTicket, '/restapi/chained_requests/from_ticket')
api.add_resource(GetUniqueChainedRequestValues, '/restapi/chained_requests/unique_values/<string:field_name>')
# REST Flow Actions
api.add_resource(GetFlow, '/restapi/flows/get/<string:flow_id>')
api.add_resource(CreateFlow, '/restapi/flows/save')
api.add_resource(UpdateFlow, '/restapi/flows/update')
api.add_resource(DeleteFlow, '/restapi/flows/delete/<string:flow_id>')
api.add_resource(
    ApproveFlow,
    '/restapi/flows/approve/<string:flow_ids>',
    '/restapi/flows/approve/<string:flow_ids>/<int:step>')
# REST Batches Actions
api.add_resource(GetBatch, '/restapi/batches/get/<string:prepid>')
api.add_resource(AnnounceBatch, '/restapi/batches/announce')
api.add_resource(
    InspectBatches,
    '/restapi/batches/inspect',
    '/restapi/batches/inspect/<string:batch_id>/<int:n_to_go>',
    '/restapi/batches/inspect/<string:batch_id>')
api.add_resource(ResetBatch, '/restapi/batches/reset/<string:batch_ids>')
api.add_resource(HoldBatch, '/restapi/batches/hold/<string:batch_ids>')
api.add_resource(NotifyBatch, '/restapi/batches/notify')
# REST invalidation Actions
api.add_resource(GetInvalidation, '/restapi/invalidations/get/<string:invalidation_id>')
api.add_resource(DeleteInvalidation, '/restapi/invalidations/delete/<string:invalidation_id>')
api.add_resource(AnnounceInvalidations, '/restapi/invalidations/announce')
api.add_resource(ClearInvalidations, '/restapi/invalidations/clear')
api.add_resource(AcknowledgeInvalidation, '/restapi/invalidations/acknowledge/<string:invalidation_id>')
api.add_resource(PutOnHoldInvalidation, '/restapi/invalidations/new_to_hold')
api.add_resource(PutHoldtoNewInvalidations, '/restapi/invalidations/hold_to_new')
# REST dashboard Actions
api.add_resource(GetBjobs, '/restapi/dashboard/get_bjobs/<string:options>')
api.add_resource(
    GetLogFeed,
    '/restapi/dashboard/get_log_feed/<string:filename>',
    '/restapi/dashboard/get_log_feed/<string:filename>/<int:lines>')
api.add_resource(GetLogs, '/restapi/dashboard/get_logs')
api.add_resource(GetRevision, '/restapi/dashboard/get_revision')
api.add_resource(GetStartTime, '/restapi/dashboard/get_start_time', resource_class_kwargs={'start_time': start_time})
api.add_resource(GetVerbosities, '/restapi/dashboard/get_verbosities')
api.add_resource(GetLocksInfo, '/restapi/dashboard/lock_info')
api.add_resource(GetQueueInfo, '/restapi/dashboard/queue_info')
# REST mccms Actions
api.add_resource(GetMccm, '/restapi/mccms/get/<string:mccm_id>')
api.add_resource(UpdateMccm, '/restapi/mccms/update')
api.add_resource(CreateMccm, '/restapi/mccms/save')
api.add_resource(DeleteMccm, '/restapi/mccms/delete/<string:mccm_id>')
api.add_resource(CancelMccm, '/restapi/mccms/cancel/<string:mccm_id>')
api.add_resource(GetEditableMccmFields, '/restapi/mccms/editable/<string:mccm_id>')
api.add_resource(
    GenerateChains,
    '/restapi/mccms/generate/<string:mccm_id>/<string:reserve_input>/<string:limit_campaign_id>',
    '/restapi/mccms/generate/<string:mccm_id>/<string:reserve_input>',
    '/restapi/mccms/generate/<string:mccm_id>')
api.add_resource(
    MccMReminderProdManagers,
    '/restapi/mccms/reminder',
    '/restapi/mccms/reminder/<int:block_threshold>')
api.add_resource(MccMReminderGenContacts, '/restapi/mccms/reminder_gen_contacts')
api.add_resource(CalculateTotalEvts, '/restapi/mccms/update_total_events/<string:mccm_id>')
api.add_resource(CheckIfAllApproved, '/restapi/mccms/check_all_approved/<string:mccm_id>')
# REST settings Actions
api.add_resource(GetSetting, '/restapi/settings/get/<string:setting_id>')
api.add_resource(UpdateSetting, '/restapi/settings/update')
api.add_resource(SaveSetting, '/restapi/settings/save')
# REST list Actions
api.add_resource(GetList, '/restapi/lists/get/<string:list_id>')
api.add_resource(UpdateList, '/restapi/lists/update')
# REST tags Actions
api.add_resource(GetTags, '/restapi/tags/get_all')
api.add_resource(AddTag, '/restapi/tags/add')
api.add_resource(RemoveTag, '/restapi/tags/remove')
# REST control Actions
api.add_resource(RenewCertificate, '/restapi/control/renew_cert')
api.add_resource(ChangeVerbosity, '/restapi/control/set_verbosity/<int:level>')
api.add_resource(
    Communicate,
    '/restapi/control/communicate',
    '/restapi/control/communicate/<string:message_number>')
api.add_resource(CacheInfo, '/restapi/control/cache_info')
api.add_resource(CacheClear, '/restapi/control/cache_clear')
# REST notification Actions
api.add_resource(CheckNotifications, '/restapi/notifications/check')
api.add_resource(FetchNotifications, '/restapi/notifications/fetch')
api.add_resource(SaveSeen, '/restapi/notifications/seen')
api.add_resource(FetchActionObjects, '/restapi/notifications/fetch_actions')
api.add_resource(FetchGroupActionObjects, '/restapi/notifications/fetch_group_actions')
api.add_resource(SearchNotifications, '/restapi/notifications/search')
api.add_resource(MarkAsSeen, '/restapi/notifications/mark_as_seen')
# Define loggers
error_logger = app.logger
max_bytes = getattr(error_logger, "rot_maxBytes", 10000000)
backup_count = getattr(error_logger, "rot_backupCount", 1000)
logger = logging.getLogger()
logger.setLevel(0)
user_filter = UserFilter()
memory_filter = MemoryFilter()
logging.getLogger('werkzeug').disabled = True
console_logging = False
console_handler = logging.StreamHandler(sys.stdout)
# Error logger
if console_logging:
    error_handler = console_handler
else:
    error_log_filename = getattr(error_logger, "rot_error_file", "logs/error.log")
    error_handler = logging.handlers.RotatingFileHandler(error_log_filename, 'a', max_bytes, backup_count)

error_formatter = logging.Formatter(fmt='[%(asctime)s][%(user)s][%(levelname)s] %(message)s', datefmt='%d/%b/%Y:%H:%M:%S')
error_handler.setFormatter(error_formatter)
error_handler.addFilter(user_filter)
error_logger.addHandler(error_handler)

# Injection logger
# due to LogAdapter empty space for message will be added inside of it
injection_logger = logging.getLogger("mcm_inject")
if console_logging:
    injection_handler = console_handler
else:
    injection_handler = logging.FileHandler('logs/inject.log', 'a')

injection_formatter = logging.Formatter(fmt='[%(asctime)s][%(levelname)s]%(message)s', datefmt='%d/%b/%Y:%H:%M:%S')
injection_handler.setFormatter(injection_formatter)
injection_logger.addHandler(injection_handler)

# Access log file
access_logger = logging.getLogger("access_log")
access_log_filename = getattr(access_logger, "rot_access_file", "logs/access.log")
if console_logging:
    access_handler = console_handler
else:
    access_handler = logging.handlers.RotatingFileHandler(access_log_filename, 'a', max_bytes, backup_count)

access_formatter = logging.Formatter(fmt='{%(mem)s} [%(asctime)s][%(user)s][%(levelname)s] %(message)s', datefmt='%d/%b/%Y:%H:%M:%S')
access_handler.setLevel(logging.DEBUG)
access_handler.setFormatter(access_formatter)
access_handler.addFilter(user_filter)
access_handler.addFilter(memory_filter)
access_logger.addHandler(access_handler)

# Log accesses
def after_this_request(f):
    if not hasattr(g, 'after_request_callbacks'):
        g.after_request_callbacks = []
    g.after_request_callbacks.append(f)
    return f

@app.after_request
def call_after_request_callbacks(response):
    for callback in getattr(g, 'after_request_callbacks', ()):
        callback(response)
    return response

@app.before_request
def log_access():
    query = "?" + request.query_string if request.query_string else ""
    full_url = request.path + unquote(query).decode('utf-8').encode('ascii', 'ignore')
    message = "%s %s %s %s" % (request.method, full_url, "%s", request.headers['User-Agent'])
    @after_this_request
    def after_request(response):
        g.message = g.message % response.status_code
        access_logger.info(g.message)
    g.message = message


def run_flask():
    print('Will do dummy ssh connection in order to initialize ssh_executor. Wait!')
    ssh_executor().execute('echo pippo')
    print('Finished ssh, McM will start shortly...')
    app.run(host='0.0.0.0', port=443, threaded=True, ssl_context=('/etc/pki/tls/certs/localhost.crt', '/etc/pki/tls/private/localhost.key'))

# Execute this function when stopping flask
def at_flask_exit(*args):
    RESTResource.counter.close()
    com = communicator()
    com.flush(0)

signal.signal(signal.SIGTERM, at_flask_exit)
if __name__ == '__main__':
    run_flask()
