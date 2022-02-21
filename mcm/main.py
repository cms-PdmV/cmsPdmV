from rest_api.ControlActions import Search, CacheClear
from rest_api.campaign_actions import (CreateCampaign,
                                       GetCampaign,
                                       UpdateCampaign,
                                       DeleteCampaign,
                                       CloneCampaign,
                                       GetEditableCampaign,
                                       ToggleCampaignStatus,
                                       GetCmsDriverForCampaign,
                                       GetUniqueCampaignValues,
                                       GetDefaultCampaignSequence,
                                       InspectCampaign)

from rest_api.flow_actions import (CreateFlow,
                                   GetFlow,
                                   UpdateFlow,
                                   DeleteFlow,
                                   CloneFlow,
                                   GetEditableFlow,
                                   ToggleFlowType)

from rest_api.chained_campaign_actions import (CreateChainedCampaign,
                                               GetChainedCampaign,
                                               UpdateChainedCampaign,
                                               DeleteChainedCampaign,
                                               GetEditableChainedCampaign)

from rest_api.batch_actions import GetBatch, DeleteBatch, AnnounceBatch

from rest_api.chained_request_actions import (GetChainedRequest,
                                              UpdateChainedRequest,
                                              DeleteChainedRequest,
                                              GetEditableChainedRequest,
                                              ChainedRequestFlow,
                                              ChainedRequestRewind,
                                              ChainedRequestRewindToRoot,
                                              SoftResetChainedRequest,
                                              InspectChainedRequest)

from rest_api.RequestActions import (RequestImport,
                                     RequestClone,
                                     RequestDelete,
                                     GetRequest,
                                     UpdateRequest,
                                     GetEditableRequest,
                                     RequestOptionReset,
                                     RequestNextStatus,
                                     RequestReset,
                                     RequestSoftReset,
                                     GetUniqueRequestValues,
                                     GetSetupFileForRequest,
                                     GetTestFileForRequest,
                                     GetValidationFileForRequest,
                                     GetCmsDriverForRequest,
                                     GetFragmentForRequest,
                                     #GetSetupForRequest,
                                     #ApproveRequest,
                                     #SetStatus,
                                     #GetStatus,
                                     GetStatusAndApproval,
                                     #GetDefaultGenParams,
                                     #RegisterUser,
                                     #GetActors,
                                     #NotifyUser,
                                     #InspectStatus,
                                     #UpdateStats,
                                     #RequestsFromFile,
                                     #StalledReminder,
                                     #RequestsReminder,
                                     #SearchableRequest,
                                     #UpdateMany,
                                     #GetRequestOutput,
                                     #GetInjectCommand,
                                     #GetUploadCommand,
                                     #GetUniqueValues,
                                     #Reserve_and_ApproveChain,
                                     #TaskChainRequestDict,
                                     #RequestsPriorityChange,
                                     #UpdateEventsFromWorkflow,
                                     GENLogOutput)



from rest_api.UserActions import GetUserInfo, AddCurrentUser, GetUser, UpdateUser, GetEditableUser
from rest_api.InvalidationActions import (GetInvalidation,
                                          DeleteInvalidation,
                                          AnnounceInvalidation,
                                          AcknowledgeInvalidation,
                                          HoldInvalidation,
                                          ResetInvalidation)
from rest_api.DashboardActions import GetLocksInfo, GetValidationInfo, GetStartTime, GetQueueInfo
from rest_api.MccmActions import GetMccM, UpdateMccm, CreateMccm, DeleteMccm, GetEditableMccM, GetUniqueMccMValues, GenerateChains, MccMReminderProdManagers, MccMReminderGenConveners, MccMReminderGenContacts, CalculateTotalEvts, CheckIfAllApproved, NotifyMccm
from rest_api.SettingsActions import GetSetting, SetSetting
# from rest_api.TagActions import GetTags, AddTag, RemoveTag
# from rest_api.ListActions import GetList, UpdateList

from json_layer.sequence import Sequence  # to get campaign sequences
from tools.logger import UserFilter
from tools.config_manager import Config
from flask_restful import Api
from flask import Flask, send_from_directory, request, g, render_template_string
from jinja2.exceptions import TemplateNotFound
from tools.utils import get_api_documentation

import json
import signal
import logging
import logging.handlers
import sys
import os
import argparse
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
    return json.dumps(Sequence.schema())

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

def setup_api_docs(flask_app):
    """
    Setup an enpoint for getting API documentation
    """
    with open('HTML/api.html') as template_file:
        api_template = template_file.read()

    def _api_documentation(api_path=None):
        """
        Endpoint for API documentation HTML
        """
        docs = get_api_documentation(flask_app, api_path)
        try:
            return render_template_string(api_template, docs=docs)
        except TemplateNotFound:
            return json.dumps(docs, indent=2, sort_keys=True)

    flask_app.add_url_rule('/restapi', None, _api_documentation)
    flask_app.add_url_rule('/restapi/<path:api_path>', None, _api_documentation)


# REST Campaign Actions
api.add_resource(CreateCampaign, '/restapi/campaigns/save')
api.add_resource(GetCampaign, '/restapi/campaigns/get/<string:prepid>')
api.add_resource(UpdateCampaign, '/restapi/campaigns/update')
api.add_resource(DeleteCampaign, '/restapi/campaigns/delete/<string:prepid>')
api.add_resource(CloneCampaign, '/restapi/campaigns/clone')
api.add_resource(GetEditableCampaign, '/restapi/campaigns/get_editable/<string:prepid>')
api.add_resource(ToggleCampaignStatus, '/restapi/campaigns/status')
api.add_resource(GetCmsDriverForCampaign, '/restapi/campaigns/get_drivers/<string:prepid>')
api.add_resource(GetUniqueCampaignValues, '/restapi/campaigns/unique_values')
api.add_resource(GetDefaultCampaignSequence, '/restapi/campaigns/get_default_sequence')
api.add_resource(InspectCampaign, '/restapi/campaigns/inspect/<string:prepid>')


# REST Flow Actions
api.add_resource(CreateFlow, '/restapi/flows/save')
api.add_resource(GetFlow, '/restapi/flows/get/<string:prepid>')
api.add_resource(UpdateFlow, '/restapi/flows/update')
api.add_resource(DeleteFlow, '/restapi/flows/delete/<string:prepid>')
api.add_resource(CloneFlow, '/restapi/flows/clone')
api.add_resource(GetEditableFlow, '/restapi/flows/get_editable/<string:prepid>')
api.add_resource(ToggleFlowType, '/restapi/flows/type')


# REST Chained campaign Actions
api.add_resource(CreateChainedCampaign, '/restapi/chained_campaigns/save')
api.add_resource(GetChainedCampaign, '/restapi/chained_campaigns/get/<string:prepid>')
api.add_resource(UpdateChainedCampaign, '/restapi/chained_campaigns/update')
api.add_resource(DeleteChainedCampaign, '/restapi/chained_campaigns/delete/<string:prepid>')
api.add_resource(GetEditableChainedCampaign,
                 '/restapi/chained_campaigns/get_editable/<string:prepid>')


# REST Batches Actions
api.add_resource(GetBatch, '/restapi/batches/get/<string:prepid>')
api.add_resource(DeleteBatch, '/restapi/batches/delete/<string:prepid>')
api.add_resource(AnnounceBatch, '/restapi/batches/announce')


# REST Chained Request Actions
api.add_resource(GetChainedRequest, '/restapi/chained_requests/get/<string:prepid>')
api.add_resource(UpdateChainedRequest, '/restapi/chained_requests/update')
api.add_resource(DeleteChainedRequest, '/restapi/chained_requests/delete/<string:prepid>')
api.add_resource(GetEditableChainedRequest,
                 '/restapi/chained_requests/get_editable/<string:prepid>')
api.add_resource(ChainedRequestFlow, '/restapi/chained_requests/flow')
api.add_resource(ChainedRequestRewind, '/restapi/chained_requests/rewind')
api.add_resource(ChainedRequestRewindToRoot, '/restapi/chained_requests/rewind_to_root')
api.add_resource(SoftResetChainedRequest, '/restapi/chained_requests/soft_reset')
api.add_resource(InspectChainedRequest, '/restapi/chained_requests/inspect')


# REST User actions
api.add_resource(AddCurrentUser, '/restapi/users/add')
api.add_resource(GetUserInfo, '/restapi/users/get')
api.add_resource(UpdateUser, '/restapi/users/update')
api.add_resource(GetEditableUser, '/restapi/users/get_editable/<string:prepid>')
api.add_resource(GetUser, '/restapi/users/get/<string:username>')


# create a restriction-free urls, with limited capabilities


# api.add_resource(
#     GetSetupForRequest,
#     '/public/restapi/requests/get_test/<string:prepid>/<int:events>',
#     '/public/restapi/requests/get_test/<string:prepid>',
#     '/public/restapi/requests/get_setup/<string:prepid>/<int:events>',
#     '/public/restapi/requests/get_setup/<string:prepid>',
#     '/public/restapi/requests/get_valid/<string:prepid>/<int:events>',
#     '/public/restapi/requests/get_valid/<string:prepid>')
# api.add_resource(GetStatus, '/public/restapi/requests/get_status/<string:request_ids>')
api.add_resource(GetStatusAndApproval, '/public/restapi/requests/get_status_and_approval/<string:prepid>')
# api.add_resource(
#     GetActors,
#     '/public/restapi/requests/get_actors/<string:request_id>',
#     '/public/restapi/requests/get_actors/<string:request_id>/<string:what>')
# api.add_resource(GetRequestByDataset, '/public/restapi/requests/produces/<path:dataset>')
# api.add_resource(
#     GetRequestOutput,
#     '/public/restapi/requests/output/<string:prepid>',
#     '/public/restapi/requests/output/<string:prepid>/<string:is_chain>')
# api.add_resource(
#     GetSetupForChains,
#     '/public/restapi/chained_requests/get_setup/<string:chained_request_id>',
#     '/public/restapi/chained_requests/get_test/<string:chained_request_id>',
#     '/public/restapi/chained_requests/get_valid/<string:chained_request_id>')
# api.add_resource(TaskChainDict, '/public/restapi/chained_requests/get_dict/<string:chained_request_id>')
# api.add_resource(TaskChainRequestDict, '/public/restapi/requests/get_dict/<string:request_id>')

# REST Request actions
api.add_resource(RequestImport, '/restapi/requests/save')
api.add_resource(RequestClone, '/restapi/requests/clone')
api.add_resource(UpdateRequest, '/restapi/requests/update')
api.add_resource(RequestDelete, '/restapi/requests/delete/<string:prepid>')
api.add_resource(GetRequest,
                 '/restapi/requests/get/<string:prepid>',
                 '/public/restapi/requests/get/<string:prepid>')
api.add_resource(GetEditableRequest, '/restapi/requests/get_editable/<string:prepid>')
api.add_resource(RequestOptionReset, '/restapi/requests/option_reset')
api.add_resource(RequestNextStatus, '/restapi/requests/next_status')
api.add_resource(RequestReset, '/restapi/requests/reset')
api.add_resource(RequestSoftReset, '/restapi/requests/soft_reset')
api.add_resource(GetUniqueRequestValues, '/restapi/requests/unique_values')
api.add_resource(GetCmsDriverForRequest, '/restapi/requests/get_drivers/<string:prepid>')
# Request public APIs
api.add_resource(GetSetupFileForRequest, '/public/restapi/requests/get_setup/<string:prepid>')
api.add_resource(GetTestFileForRequest, '/public/restapi/requests/get_test/<string:prepid>')
api.add_resource(GetValidationFileForRequest, '/public/restapi/requests/get_valid/<string:prepid>')
api.add_resource(GetFragmentForRequest, '/public/restapi/requests/get_fragment/<string:prepid>')
# api.add_resource(
#     ResetRequestApproval,
#     '/restapi/requests/reset/<string:request_id>',
#     '/restapi/requests/soft_reset/<string:request_id>')
# api.add_resource(
#     SetStatus,
#     '/restapi/requests/status/<string:request_ids>',
#     '/restapi/requests/status/<string:request_ids>/<int:step>')
# api.add_resource(RegisterUser, '/restapi/requests/register/<string:request_ids>')
# api.add_resource(NotifyUser, '/restapi/requests/notify')
# api.add_resource(
#     InspectStatus,
#     '/restapi/requests/inspect/<string:request_ids>',
#     '/restapi/requests/inspect/<string:request_ids>/<string:force>')
# api.add_resource(
#     UpdateStats,
#     '/restapi/requests/update_stats/<string:request_id>',
#     '/restapi/requests/update_stats/<string:request_id>/<string:refresh>',
#     '/restapi/requests/update_stats/<string:request_id>/<string:refresh>/<string:forced>')
# api.add_resource(UpdateEventsFromWorkflow, '/restapi/requests/fetch_stats_by_wf/<string:wf_id>')
# api.add_resource(
#     RequestsFromFile,
#     '/restapi/requests/listwithfile',
#     '/public/restapi/requests/listwithfile')
# api.add_resource(SearchableRequest, '/restapi/requests/searchable')
# api.add_resource(
#     RequestsReminder,
#     '/restapi/requests/reminder',
#     '/restapi/requests/reminder/<string:what>',
#     '/restapi/requests/reminder/<string:what>/<string:who>')
# api.add_resource(
#     StalledReminder,
#     '/restapi/requests/stalled',
#     '/restapi/requests/stalled/<int:time_since>',
#     '/restapi/requests/stalled/<int:time_since>/<int:time_remaining>',
#     '/restapi/requests/stalled/<int:time_since>/<int:time_remaining>/<float:below_completed>')
# api.add_resource(UpdateMany, '/restapi/requests/update_many')
# api.add_resource(GetInjectCommand, '/restapi/requests/get_inject/<string:request_id>')
# api.add_resource(GetUploadCommand, '/restapi/requests/get_upload/<string:request_id>')
# api.add_resource(Reserve_and_ApproveChain, '/restapi/requests/reserveandapprove/<string:chain_id>')
# api.add_resource(RequestsPriorityChange, '/restapi/requests/priority_change')
api.add_resource(GENLogOutput, '/restapi/requests/gen_log/<string:request_id>')



# REST invalidation Actions
api.add_resource(GetInvalidation, '/restapi/invalidations/get/<string:prepid>')
api.add_resource(DeleteInvalidation, '/restapi/invalidations/delete/<string:prepid>')
api.add_resource(AnnounceInvalidation, '/restapi/invalidations/announce')
api.add_resource(AcknowledgeInvalidation,
                 '/restapi/invalidations/acknowledge/<string:prepid>',
                 '/restapi/invalidations/acknowledge')
api.add_resource(HoldInvalidation, '/restapi/invalidations/hold')
api.add_resource(ResetInvalidation, '/restapi/invalidations/reset')

# REST dashboard Actions
api.add_resource(GetValidationInfo, '/restapi/dashboard/get_validation_info')
api.add_resource(GetStartTime, '/restapi/dashboard/get_start_time')
api.add_resource(GetLocksInfo, '/restapi/dashboard/get_lock_info')
api.add_resource(GetQueueInfo, '/restapi/dashboard/get_submission_info')
# REST mccms Actions
api.add_resource(
    GetMccM,
    '/restapi/mccms/get/<string:prepid>',
    '/public/restapi/mccms/get/<string:prepid>')
api.add_resource(UpdateMccm, '/restapi/mccms/update')
api.add_resource(CreateMccm, '/restapi/mccms/save')
api.add_resource(DeleteMccm, '/restapi/mccms/delete/<string:prepid>')
api.add_resource(GetEditableMccM, '/restapi/mccms/get_editable/<string:prepid>')
api.add_resource(GetUniqueMccMValues, '/restapi/mccms/unique_values')
api.add_resource(GenerateChains, '/restapi/mccms/generate')
api.add_resource(CalculateTotalEvts, '/restapi/mccms/recalculate')
api.add_resource(CheckIfAllApproved, '/restapi/mccms/check_all_approved/<string:prepid>')
api.add_resource(NotifyMccm, '/restapi/mccms/notify')
api.add_resource(MccMReminderProdManagers, '/restapi/mccms/reminder_prod_managers')
api.add_resource(MccMReminderGenConveners, '/restapi/mccms/reminder_gen_conveners')
api.add_resource(MccMReminderGenContacts, '/restapi/mccms/reminder_gen_contacts')
# REST settings Actions
api.add_resource(GetSetting, '/restapi/settings/get/<string:key>')
api.add_resource(SetSetting, '/restapi/settings/set')
# REST list Actions
# api.add_resource(GetList, '/restapi/lists/get/<string:list_id>')
# api.add_resource(UpdateList, '/restapi/lists/update')
# REST tags Actions
# api.add_resource(GetTags, '/restapi/tags/get_all')
# api.add_resource(AddTag, '/restapi/tags/add')
# api.add_resource(RemoveTag, '/restapi/tags/remove')
# REST control Actions
api.add_resource(CacheClear, '/restapi/control/cache_clear')


def setup_error_logger(debug):
    """
    Setup the main logger
    Log to file and rotate for production or log to console in debug mode
    Automatically log user email
    """
    logger = logging.getLogger('mcm_error')
    if debug:
        # If debug - log to console
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
    else:
        # If not debug - log to files
        if not os.path.isdir('logs'):
            os.mkdir('logs')

        log_size = 1024 ** 3  # 10MB
        log_count = 500  # 500 files
        log_name = 'logs/error.log'
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
    logger = logging.getLogger('mcm_inject')
    if debug:
        # If debug - log to console
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
    else:
        # If not debug - log to files
        if not os.path.isdir('logs'):
            os.mkdir('logs')

        log_size = 1024 ** 3  # 10MB
        log_count = 500  # 500 files
        log_name = 'logs/inject.log'
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
    logger = logging.getLogger('access_log')
    if debug:
        # If debug - log to console
        handler = logging.StreamHandler(sys.stdout)
    else:
        # If not debug - log to files
        if not os.path.isdir('logs'):
            os.mkdir('logs')

        log_size = 1024 ** 3  # 10MB
        log_count = 500  # 500 files
        log_name = 'logs/access.log'
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
                time_taken = '%.2fms' % (float(time.time() - g.request_start_time) * 1000.0)
            else:
                time_taken = ' '

            code = response.status_code
            method = request.method
            user_agent = request.headers.get('User-Agent', '<unknown user agent>')
            url = '%s' % (request.path)
            if request.query_string:
                url += '?%s' % (request.query_string.decode('ascii'))

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
    parser = argparse.ArgumentParser(description='The McM - Monte Carlo Management tool')
    parser.add_argument('--port', help='Port, default is 8000', type=int)
    parser.add_argument('--host', help='Host IP, default is 0.0.0.0')
    parser.add_argument('--debug', help='Run McM in debug mode', action='store_true')
    parser.add_argument('--prod', help='Run McM in production mode', action='store_true')
    args = vars(parser.parse_args())
    debug = args.get('debug')
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

    # Read config
    prod = args.get('prod')
    Config.load('config.cfg', 'production' if prod else 'development')
    # Run flask
    port = args.get('port') or Config.getint('port')
    host = args.get('host') or Config.get('host')
    setup_api_docs(app)
    error_logger.info('Starting McM, host=%s, port=%s, debug=%s, prod=%s', host, port, debug, prod)
    app.run(host=host, port=port, threaded=True, debug=debug)


if __name__ == '__main__':
    main()
