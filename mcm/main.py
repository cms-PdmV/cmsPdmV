from rest_api.ControlActions import Search, Communicate, CacheInfo, CacheClear
from rest_api.RestAPIMethod import RESTResourceIndex, RESTResource
from rest_api.RequestActions import ImportRequest, ManageRequest, DeleteRequest, GetRequest, GetRequestByDataset, UpdateRequest, GetCmsDriverForRequest, GetFragmentForRequest, GetSetupForRequest, ApproveRequest, ResetRequestApproval, SetStatus, GetStatus, GetStatusAndApproval, GetEditable, GetDefaultGenParams, CloneRequest, RegisterUser, GetActors, NotifyUser, InspectStatus, UpdateStats, RequestsFromFile, StalledReminder, RequestsReminder, SearchableRequest, UpdateMany, ListRequestPrepids, OptionResetForRequest, GetRequestOutput, GetInjectCommand, GetUploadCommand, GetUniqueValues, PutToForceComplete, ForceCompleteMethods, Reserve_and_ApproveChain, TaskChainRequestDict, RequestsPriorityChange, UpdateEventsFromWorkflow, PPDTags, GENLogOutput, RequestsFromDataset
from rest_api.CampaignActions import CreateCampaign, DeleteCampaign, UpdateCampaign, GetCampaign, ToggleCampaignStatus, GetCmsDriverForCampaign, InspectCampaigns
from rest_api.ChainedCampaignActions import CreateChainedCampaign, DeleteChainedCampaign, GetChainedCampaign, UpdateChainedCampaign
from rest_api.ChainedRequestActions import ForceChainReqToDone, ForceStatusDoneToProcessing, CreateChainedRequest, ChainsFromTicket, ChainedRequestsPriorityChange, UpdateChainedRequest, DeleteChainedRequest, GetChainedRequest,  FlowToNextStep, ApproveChainedRequest, InspectChain, RewindToPreviousStep, RewindToRoot, SearchableChainedRequest, TestChainedRequest, GetSetupForChains, TaskChainDict, InjectChainedRequest, SoftResetChainedRequest, ToForceFlowList, RemoveFromForceFlowList, GetUniqueChainedRequestValues
from rest_api.FlowActions import CreateFlow, UpdateFlow, DeleteFlow, GetFlow, ApproveFlow, CloneFlow
from rest_api.UserActions import GetUserRole, AddRole, AskRole, ChangeRole, GetUser, SaveUser, GetUserPWG, NotifyPWG
from rest_api.BatchActions import HoldBatch, GetBatch, AnnounceBatch, InspectBatches, ResetBatch, NotifyBatch
from rest_api.InvalidationActions import GetInvalidation, DeleteInvalidation, AnnounceInvalidations, ClearInvalidations, AcknowledgeInvalidation, PutHoldtoNewInvalidations, PutOnHoldInvalidation
from rest_api.DashboardActions import GetLocksInfo, GetBjobs, GetLogFeed, GetLogs, GetRevision, GetStartTime, GetQueueInfo
from rest_api.MccmActions import GetMccm, UpdateMccm, CreateMccm, DeleteMccm, CancelMccm, GetEditableMccmFields, GenerateChains, MccMReminderProdManagers, MccMReminderGenConveners, MccMReminderGenContacts, CalculateTotalEvts, CheckIfAllApproved, NotifyMccm
from rest_api.SettingsActions import GetSetting, UpdateSetting, SaveSetting
from rest_api.TagActions import GetTags, AddTag, RemoveTag
from rest_api.ListActions import GetList, UpdateList

from json_layer.sequence import sequence  # to get campaign sequences
from tools.communicator import communicator
from tools.logger import UserFilter
from tools.locator import locator
from flask_restful import Api
from flask import Flask, send_from_directory, request, g

import json
import signal
import logging
import logging.handlers
import sys
import os
import time


app = Flask(__name__)
app.config.update(LOGGER_NAME="mcm_error")
api = Api(app)
app.url_map.strict_slashes = False
# Set flask logging to warning
logging.getLogger('werkzeug').setLevel(logging.WARNING)
# Set paramiko logging to warning
logging.getLogger('paramiko').setLevel(logging.WARNING)


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

@app.route('/users')
def users_html():
    return send_from_directory('HTML', 'users.html')

@app.route('/batches')
def batches_html():
    return send_from_directory('HTML', 'batches.html')

@app.route('/getDefaultSequences')
def getDefaultSequences():
    return json.dumps(sequence()._json_base__schema)

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

# REST API - RESTResourceIndex is the directory of available commands
api.add_resource(
    RESTResourceIndex,
    '/restapi',
    '/restapi/requests',
    '/restapi/campaigns',
    '/restapi/chained_requests',
    '/restapi/chained_campaigns',
    '/restapi/flows',
    '/restapi/users',
    '/restapi/batches',
    '/restapi/invalidations',
    '/restapi/dashboard',
    '/restapi/mccms',
    '/restapi/settings',
    '/restapi/tags',
    '/restapi/control',
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
api.add_resource(RequestsFromDataset, '/public/restapi/requests/from_dataset_name/<string:dataset_name>')
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
api.add_resource(
    RequestsFromFile,
    '/restapi/requests/listwithfile',
    '/public/restapi/requests/listwithfile')
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
api.add_resource(GENLogOutput, '/restapi/requests/gen_log/<string:request_id>')
# REST Campaign Actions
api.add_resource(CreateCampaign, '/restapi/campaigns/save')
api.add_resource(UpdateCampaign, '/restapi/campaigns/update')
api.add_resource(DeleteCampaign, '/restapi/campaigns/delete/<string:campaign_id>')
api.add_resource(GetCampaign, '/restapi/campaigns/get/<string:campaign_id>')
api.add_resource(ToggleCampaignStatus, '/restapi/campaigns/status/<string:campaign_id>')
api.add_resource(GetCmsDriverForCampaign, '/restapi/campaigns/get_cmsDrivers/<string:campaign_id>')
api.add_resource(InspectCampaigns, '/restapi/campaigns/inspect/<string:campaign_id>')
# REST Chained Campaign Actions
api.add_resource(CreateChainedCampaign, '/restapi/chained_campaigns/save')
api.add_resource(DeleteChainedCampaign, '/restapi/chained_campaigns/delete/<string:chained_campaign_id>')
api.add_resource(GetChainedCampaign, '/restapi/chained_campaigns/get/<string:chained_campaign_id>')
api.add_resource(UpdateChainedCampaign, '/restapi/chained_campaigns/update')
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
api.add_resource(RewindToRoot, '/restapi/chained_requests/rewind_to_root/<string:chained_request_ids>')
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
api.add_resource(TestChainedRequest,
                 '/restapi/chained_requests/test/<string:chained_request_id>',
                 '/restapi/chained_requests/validate/<string:chained_request_id>')
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
api.add_resource(ApproveFlow, '/restapi/flows/approve/<string:flow_id>')
api.add_resource(CloneFlow, '/restapi/flows/clone')
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
api.add_resource(GetStartTime, '/restapi/dashboard/get_start_time')
api.add_resource(GetLocksInfo, '/restapi/dashboard/lock_info')
api.add_resource(GetQueueInfo, '/restapi/dashboard/queue_info')
# REST mccms Actions
api.add_resource(
    GetMccm,
    '/restapi/mccms/get/<string:mccm_id>',
    '/public/restapi/mccms/get/<string:mccm_id>')
api.add_resource(UpdateMccm, '/restapi/mccms/update')
api.add_resource(CreateMccm, '/restapi/mccms/save')
api.add_resource(DeleteMccm, '/restapi/mccms/delete/<string:mccm_id>')
api.add_resource(CancelMccm, '/restapi/mccms/cancel/<string:mccm_id>')
api.add_resource(GetEditableMccmFields, '/restapi/mccms/editable/<string:mccm_id>')
api.add_resource(GenerateChains, '/restapi/mccms/generate/<string:mccm_id>')
api.add_resource(MccMReminderProdManagers, '/restapi/mccms/reminder_prod_managers')
api.add_resource(MccMReminderGenConveners, '/restapi/mccms/reminder_gen_conveners')
api.add_resource(MccMReminderGenContacts, '/restapi/mccms/reminder_gen_contacts')
api.add_resource(CalculateTotalEvts, '/restapi/mccms/update_total_events/<string:mccm_id>')
api.add_resource(CheckIfAllApproved, '/restapi/mccms/check_all_approved/<string:mccm_id>')
api.add_resource(NotifyMccm, '/restapi/mccms/notify')
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
api.add_resource(
    Communicate,
    '/restapi/control/communicate',
    '/restapi/control/communicate/<string:message_number>')
api.add_resource(CacheInfo, '/restapi/control/cache_info')
api.add_resource(CacheClear, '/restapi/control/cache_clear')


def setup_error_logger(debug):
    """
    Setup the main logger
    Log to file and rotate for production or log to console in debug mode
    Automatically log user email
    """
    l_type = locator()
    logs_folder = l_type.logs_folder()
    logger = logging.getLogger('mcm_error')
    if debug:
        # If debug - log to console
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
    else:
        # If not debug - log to files
        if not os.path.isdir(logs_folder):
            os.mkdir(logs_folder)

        log_size = 10 * 1024 * 1024  # 10MB
        log_count = 500  # 500 files
        log_name = os.path.join(logs_folder, "error.log")
        handler = logging.handlers.RotatingFileHandler(log_name, 'a', log_size, log_count)
        handler.setLevel(logging.INFO)

    formatter = logging.Formatter(fmt='[%(asctime)s][%(user)s][%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    handler.addFilter(UserFilter())
    # del logger.handlers[:]  # Clear the list
    logger.addHandler(handler)
    return logger


def setup_injection_logger(debug):
    """
    Setup logger for injection operations
    It will have an additional handle that shows prepid of item being injected
    """
    l_type = locator()
    logs_folder = l_type.logs_folder()
    logger = logging.getLogger('mcm_inject')
    if debug:
        # If debug - log to console
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
    else:
        # If not debug - log to files
        if not os.path.isdir(logs_folder):
            os.mkdir(logs_folder)

        log_size = 10 * 1024 * 1024  # 10MB
        log_count = 500  # 500 files
        log_name = os.path.join(logs_folder, "inject.log")
        handler = logging.handlers.RotatingFileHandler(log_name, 'a', log_size, log_count)
        handler.setLevel(logging.INFO)

    formatter = logging.Formatter(fmt='[%(asctime)s][%(levelname)s]%(message)s')
    handler.setFormatter(formatter)
    # del logger.handlers[:]  # Clear the list
    logger.addHandler(handler)
    return logger


def setup_access_logger(debug):
    """
    Setup logger to log all accesses to the tool
    Automatically log user email
    """
    l_type = locator()
    logs_folder = l_type.logs_folder()
    logger = logging.getLogger('access_log')
    if debug:
        # If debug - log to console
        handler = logging.StreamHandler(sys.stdout)
    else:
        # If not debug - log to files
        if not os.path.isdir(logs_folder):
            os.mkdir(logs_folder)

        log_size = 10 * 1024 * 1024  # 10MB
        log_count = 500  # 500 files
        log_name = os.path.join(logs_folder, "access.log")
        handler = logging.handlers.RotatingFileHandler(log_name, 'a', log_size, log_count)

    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(fmt='[%(asctime)s][%(user)s] %(message)s')
    handler.setFormatter(formatter)
    handler.addFilter(UserFilter())
    # del logger.handlers[:]  # Clear the list
    logger.addHandler(handler)
    return logger


def setup_access_logging(app, logger, debug):
    """
    Setup logging of access to the logger
    Log path, status code, time taken and user agent
    """
    def before():
        g.request_start_time = time.time()

    def after(response):
        try:
            if hasattr(g, 'request_start_time'):
                time_taken = (time.time() - g.request_start_time)
                time_taken = '%.2fms' % (float(time_taken) * 1000.0)
            else:
                time_taken = ' '

            code = response.status_code
            method = request.method
            user_agent = request.headers.get('User-Agent', '<unknown user agent>')
            url = '%s' % (request.path)
            if request.query_string:
                url += '?%s' % (request.query_string)

            if not debug or not url.endswith(('.html', '.css', '.js')):
                # During debugging suppress html, css and js file access logging
                logger.info('%s %s %s %s %s', method, url, code, time_taken, user_agent)
        except:
            # Do not crash everything because of failing logger
            pass

        return response

    app.before_request(before)
    app.after_request(after)


def main():
    l_type = locator()
    port = l_type.port()
    host = l_type.host()
    debug = l_type.debug()
    # Setup loggers
    logging.root.setLevel(logging.DEBUG if debug else logging.INFO)
    error_logger = setup_error_logger(debug)
    setup_injection_logger(debug)
    access_logger = setup_access_logger(debug)
    setup_access_logging(app, access_logger, debug)
    # Write McM PID to a file
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        # Do only once, before the reloader
        pid = os.getpid()
        error_logger.info('PID: %s', pid)
        with open('mcm.pid', 'w') as pid_file:
            pid_file.write(str(pid))

    error_logger.info('Starting McM, host=%s, port=%s, debug=%s', host, port, debug)
    error_logger.info('Running in production mode: %s', l_type.isProd())
    # Run flask
    app.run(host=host, port=port, threaded=True, debug=debug)


# Execute this function when stopping flask
def at_flask_exit(*args):
    RESTResource.counter.close()
    com = communicator()
    com.flush(0)


signal.signal(signal.SIGTERM, at_flask_exit)
if __name__ == '__main__':
    main()
