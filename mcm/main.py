from rest_api.search_actions import Search
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
                                               GetEditableChainedCampaign,
                                               ToggleChainedCampaignEnabled)

from rest_api.batch_actions import GetBatch, DeleteBatch, AnnounceBatch

from rest_api.chained_request_actions import (GetChainedRequest,
                                              UpdateChainedRequest,
                                              DeleteChainedRequest,
                                              GetEditableChainedRequest,
                                              ToggleChainedRequestEnabled,
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
                                     GetSubmittedTogetherForRequest,
                                     UpdateStats,
                                     GetStatusAndApproval,
                                     GENLogOutput)

from rest_api.user_actions import GetUserInfo, AddCurrentUser, GetUser, UpdateUser, GetEditableUser
from rest_api.InvalidationActions import (GetInvalidation,
                                          DeleteInvalidation,
                                          AnnounceInvalidation,
                                          AcknowledgeInvalidation,
                                          HoldInvalidation,
                                          ResetInvalidation)
from rest_api.system_actions import (GetLocksInfo,
                                     GetValidationInfo,
                                     GetStartTime,
                                     GetQueueInfo,
                                     CacheClear)
from rest_api.mccm_actions import (GetMccM,
                                  UpdateMccm,
                                  CreateMccm,
                                  DeleteMccm,
                                  GetEditableMccM,
                                  GetUniqueMccMValues,
                                  GenerateChains,
                                  MccMReminderProdManagers,
                                  MccMReminderGenConveners,
                                  MccMReminderGenContacts,
                                  CalculateTotalEvts,
                                  CheckIfAllApproved,
                                  NotifyMccm)
from rest_api.settings_actions import GetSetting, SetSetting

from tools.logger import UserFilter
from tools.config_manager import Config
from flask_restful import Api
from flask import Flask, render_template, request, g, render_template_string
from jinja2.exceptions import TemplateNotFound
from tools.utils import get_api_documentation

import json
import logging
import logging.handlers
import sys
import os
import argparse
import time


app = Flask(__name__,
            static_folder='./frontend/dist/static',
            template_folder='./frontend/dist')
app.config.update(LOGGER_NAME='')
api = Api(app)
app.url_map.strict_slashes = False

# Set flask logging to warning
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Set paramiko logging to warning
logging.getLogger('paramiko').setLevel(logging.WARNING)


@app.route('/', defaults={'_path': ''})
@app.route('/<path:_path>')
def catch_all(_path):
    """
    Return index.html for all paths except API
    """
    try:
        return render_template('index.html')
    except TemplateNotFound:
        response = '<script>setTimeout(function() {location.reload();}, 5000);</script>'
        response += 'Webpage is starting, please wait a few minutes...'
        return response


def setup_api_docs(flask_app):
    """
    Setup an enpoint for getting API documentation
    """
    try:
        with open('frontend/dist/api.html') as template_file:
            api_template = template_file.read()
    except:
        api_template = '<html>No template</html>'

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


# REST Search Actions
api.add_resource(Search, '/search')


# REST Campaign Actions
api.add_resource(CreateCampaign, '/restapi/campaigns/save')
api.add_resource(GetCampaign, '/restapi/campaigns/get/<string:prepid>')
api.add_resource(UpdateCampaign, '/restapi/campaigns/update')
api.add_resource(DeleteCampaign, '/restapi/campaigns/delete/<string:prepid>')
api.add_resource(CloneCampaign, '/restapi/campaigns/clone')
api.add_resource(GetEditableCampaign,
                 '/restapi/campaigns/get_editable',
                 '/restapi/campaigns/get_editable/<string:prepid>')
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
api.add_resource(GetEditableFlow,
                 '/restapi/flows/get_editable',
                 '/restapi/flows/get_editable/<string:prepid>')
api.add_resource(ToggleFlowType, '/restapi/flows/type')


# REST Chained campaign Actions
api.add_resource(CreateChainedCampaign, '/restapi/chained_campaigns/save')
api.add_resource(GetChainedCampaign, '/restapi/chained_campaigns/get/<string:prepid>')
api.add_resource(UpdateChainedCampaign, '/restapi/chained_campaigns/update')
api.add_resource(DeleteChainedCampaign, '/restapi/chained_campaigns/delete/<string:prepid>')
api.add_resource(GetEditableChainedCampaign,
                 '/restapi/chained_campaigns/get_editable',
                 '/restapi/chained_campaigns/get_editable/<string:prepid>')
api.add_resource(ToggleChainedCampaignEnabled, '/restapi/chained_campaigns/toggle_enabled')


# REST Batches Actions
api.add_resource(GetBatch, '/restapi/batches/get/<string:prepid>')
api.add_resource(DeleteBatch, '/restapi/batches/delete/<string:prepid>')
api.add_resource(AnnounceBatch, '/restapi/batches/announce')


# REST Chained Request Actions
api.add_resource(GetChainedRequest, '/restapi/chained_requests/get/<string:prepid>')
api.add_resource(UpdateChainedRequest, '/restapi/chained_requests/update')
api.add_resource(DeleteChainedRequest, '/restapi/chained_requests/delete/<string:prepid>')
api.add_resource(GetEditableChainedRequest,
                 '/restapi/chained_requests/get_editable',
                 '/restapi/chained_requests/get_editable/<string:prepid>')
api.add_resource(ToggleChainedRequestEnabled, '/restapi/chained_requests/toggle_enabled')
api.add_resource(ChainedRequestFlow, '/restapi/chained_requests/flow')
api.add_resource(ChainedRequestRewind, '/restapi/chained_requests/rewind')
api.add_resource(ChainedRequestRewindToRoot, '/restapi/chained_requests/rewind_to_root')
api.add_resource(SoftResetChainedRequest, '/restapi/chained_requests/soft_reset')
api.add_resource(InspectChainedRequest, '/restapi/chained_requests/inspect')


# REST User actions
api.add_resource(AddCurrentUser, '/restapi/users/add')
api.add_resource(GetUserInfo, '/restapi/users/get')
api.add_resource(UpdateUser, '/restapi/users/update')
api.add_resource(GetEditableUser,
                 '/restapi/users/get_editable',
                 '/restapi/users/get_editable/<string:prepid>')
api.add_resource(GetUser, '/restapi/users/get/<string:username>')


# REST System Actions
api.add_resource(GetValidationInfo, '/restapi/system/validation_info')
api.add_resource(GetStartTime, '/restapi/system/start_time')
api.add_resource(GetLocksInfo, '/restapi/system/locks_info')
api.add_resource(GetQueueInfo, '/restapi/system/submission_info')
api.add_resource(CacheClear, '/restapi/control/cache_clear')


# REST Request actions
api.add_resource(RequestImport, '/restapi/requests/save')
api.add_resource(RequestClone, '/restapi/requests/clone')
api.add_resource(UpdateRequest, '/restapi/requests/update')
api.add_resource(RequestDelete, '/restapi/requests/delete/<string:prepid>')
api.add_resource(GetRequest,
                 '/restapi/requests/get/<string:prepid>',
                 '/public/restapi/requests/get/<string:prepid>')
api.add_resource(GetEditableRequest,
                 '/restapi/requests/get_editable',
                 '/restapi/requests/get_editable/<string:prepid>')
api.add_resource(RequestOptionReset, '/restapi/requests/option_reset')
api.add_resource(RequestNextStatus, '/restapi/requests/next_status')
api.add_resource(RequestReset, '/restapi/requests/reset')
api.add_resource(RequestSoftReset, '/restapi/requests/soft_reset')
api.add_resource(GetUniqueRequestValues, '/restapi/requests/unique_values')
api.add_resource(GetCmsDriverForRequest, '/restapi/requests/get_drivers/<string:prepid>')
api.add_resource(GetSubmittedTogetherForRequest, '/restapi/requests/submit_plan/<string:prepid>')
api.add_resource(UpdateStats, '/restapi/requests/update_stats')


# Request public APIs
api.add_resource(GetSetupFileForRequest, '/public/restapi/requests/get_setup/<string:prepid>')
api.add_resource(GetTestFileForRequest, '/public/restapi/requests/get_test/<string:prepid>')
api.add_resource(GetValidationFileForRequest, '/public/restapi/requests/get_valid/<string:prepid>')
api.add_resource(GetFragmentForRequest, '/public/restapi/requests/get_fragment/<string:prepid>')
api.add_resource(GetStatusAndApproval, '/public/restapi/requests/get_status_and_approval/<string:prepid>')
api.add_resource(GENLogOutput, '/restapi/requests/gen_log/<string:request_id>')


# REST Invalidation Actions
api.add_resource(GetInvalidation, '/restapi/invalidations/get/<string:prepid>')
api.add_resource(DeleteInvalidation, '/restapi/invalidations/delete/<string:prepid>')
api.add_resource(AnnounceInvalidation, '/restapi/invalidations/announce')
api.add_resource(AcknowledgeInvalidation,
                 '/restapi/invalidations/acknowledge/<string:prepid>',
                 '/restapi/invalidations/acknowledge')
api.add_resource(HoldInvalidation, '/restapi/invalidations/hold')
api.add_resource(ResetInvalidation, '/restapi/invalidations/reset')


# REST MccM Actions
api.add_resource(GetMccM, '/restapi/mccms/get/<string:prepid>')
api.add_resource(UpdateMccm, '/restapi/mccms/update')
api.add_resource(CreateMccm, '/restapi/mccms/save')
api.add_resource(DeleteMccm, '/restapi/mccms/delete/<string:prepid>')
api.add_resource(GetEditableMccM,
                 '/restapi/mccms/get_editable',
                 '/restapi/mccms/get_editable/<string:prepid>')
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


def setup_error_logger(debug):
    """
    Setup the main logger
    Log to file and rotate for production or log to console in debug mode
    Automatically log user email
    """
    logger = logging.getLogger()
    if debug:
        # If debug - log to console
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
    else:
        # If not debug - log to files
        if not os.path.isdir('logs'):
            os.mkdir('logs')

        log_size = 1024 ** 2  # 10MB
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

        log_size = 1024 ** 2  # 10MB
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

        log_size = 1024 ** 2  # 10MB
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
    """
    Main function
    """
    parser = argparse.ArgumentParser(description='McM - Monte Carlo Management tool')
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
    dev = not prod
    Config.load('config.cfg', 'production' if prod else 'development')
    Config.set('dev', dev)
    assert dev == Config.get('dev')
    # Run flask
    port = args.get('port') or Config.getint('port')
    host = args.get('host') or Config.get('host')
    setup_api_docs(app)
    error_logger.info('Starting McM, host=%s, port=%s, debug=%s, prod=%s', host, port, debug, prod)
    app.run(host=host, port=port, threaded=True, debug=debug)


if __name__ == '__main__':
    main()
