from rest_api.ControlActions import Search, MultiSearch
from rest_api.RestAPIMethod import RESTResourceIndex, RESTResource
from rest_api.RequestActions import ImportRequest, ManageRequest, DeleteRequest, GetRequest, GetRequestByDataset, UpdateRequest, GetCmsDriverForRequest, GetFragmentForRequest, GetSetupForRequest, ApproveRequest, UploadConfig, InjectRequest, ResetRequestApproval, SetStatus, GetStatus, GetEditable, GetDefaultGenParams, CloneRequest, RegisterUser, MigrateRequest, MigratePage, GetActors, NotifyUser, InspectStatus, UpdateStats, RequestsFromFile, TestRequest, StalledReminder, RequestsReminder, RequestPerformance, SearchableRequest, UpdateMany, GetAllRevisions, ListRequestPrepids, OptionResetForRequest, GetRequestOutput, GetInjectCommand, GetUploadCommand, GetUniqueValues, PutToForceComplete, ForceCompleteMethods, Reserve_and_ApproveChain, TaskChainRequestDict, RequestsPriorityChange
from rest_api.CampaignActions import CreateCampaign, DeleteCampaign, UpdateCampaign, GetCampaign, ToggleCampaign, ToggleCampaignStatus, ApproveCampaign, GetAllCampaigns, GetCmsDriverForCampaign, ListAllCampaigns, InspectRequests, InspectCampaigns
from rest_api.ChainedCampaignActions import ChainedCampaignsPriorityChange, CreateChainedCampaign, DeleteChainedCampaign, GetChainedCampaign, UpdateChainedCampaign, InspectChainedRequests, InspectChainedCampaigns, SelectNewChainedCampaigns, ListChainCampaignPrepids
from rest_api.ChainedRequestActions import ChainsFromTicket, ChainedRequestsPriorityChange, CreateChainedRequest, UpdateChainedRequest, DeleteChainedRequest, GetChainedRequest,  FlowToNextStep,  ApproveRequest as ApproveChainedRequest, InspectChain, RewindToPreviousStep, GetConcatenatedHistory, SearchableChainedRequest, TestChainedRequest, GetSetupForChains, TaskChainDict, InjectChainedRequest, SoftResetChainedRequest, TestOutputDSAlgo, ForceChainReqToDone, ForceStatusDoneToProcessing, ToForceFlowList, RemoveFromForceFlowList
from rest_api.FlowActions import CreateFlow,  UpdateFlow,  DeleteFlow,  GetFlow,  ApproveFlow
from rest_api.RequestPrepId import RequestPrepId
from rest_api.ChainedRequestPrepId import ChainedRequestPrepId
from rest_api.LogActions import ReadInjectionLog, GetVerbosities
from rest_api.UserActions import GetUserRole, GetAllRoles, GetAllUsers, AddRole, AskRole, ChangeRole, GetUser, SaveUser, GetUserPWG, FillFullNames, NotifyPWG
from rest_api.BatchActions import HoldBatch, SaveBatch, UpdateBatch, GetBatch, GetAllBatches, AnnounceBatch, GetIndex, InspectBatches, ResetBatch, NotifyBatch
from rest_api.InvalidationActions import GetInvalidation, DeleteInvalidation, AnnounceInvalidations, ClearInvalidations, AcknowledgeInvalidation, PutOnHoldInvalidation, PutHoldtoNewInvalidations
from rest_api.DashboardActions import GetBjobs, GetLogFeed, GetLogs, GetRevision, GetStartTime, TestConnection, ListReleases, GetLocksInfo, GetQueueInfo
from rest_api.MccmActions import GetMccm, UpdateMccm, CreateMccm, DeleteMccm, CancelMccm, GetEditableMccmFields, GenerateChains, MccMReminderProdManagers, MccMReminderGenContacts, CalculateTotalEvts
from rest_api.SettingsActions import GetSetting, UpdateSetting, SaveSetting
from rest_api.TagActions import GetTags, AddTag, RemoveTag
from rest_api.ControlActions import RenewCertificate, ChangeVerbosity, TurnOffServer, ResetRESTCounters, Communicate
from rest_api.NotificationActions import CheckNotifications, FetchNotifications, SaveSeen, FetchActionObjects, FetchGroupActionObjects

from json_layer.sequence import sequence #to get campaign sequences
from tools.settings import settings
from tools.communicator import communicator
from tools.logger import UserFilter, MemoryFilter

import logging
import logging.handlers
import json
import cherrypy
import os
import shelve
import subprocess
import imp
import datetime

file_location = os.path.dirname(__file__)
start_time = datetime.datetime.now().strftime("%c")

###UPDATED METHODS##
@cherrypy.expose
def campaigns_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','campaigns.html'))
@cherrypy.expose
def requests_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','requests.html'))
@cherrypy.expose
def edit_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','edit.html'))
@cherrypy.expose
def flows_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','flows.html'))
@cherrypy.expose
def chained_campaigns_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','chained_campaigns.html'))
@cherrypy.expose
def chained_requests_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','chained_requests.html'))
@cherrypy.expose
def priority_change_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','priority_change.html'))
@cherrypy.expose
def index( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','index.html'))
@cherrypy.expose
def create_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','create.html'))
@cherrypy.expose
def injectAndLog( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','injectAndLog.html'))
@cherrypy.expose
def users( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','users.html'))
@cherrypy.expose
def batches( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','batches.html'))
@cherrypy.expose
def getDefaultSequences(*args, **kwargs):
    tmpSeq = sequence()._json_base__schema
    return json.dumps(tmpSeq)
@cherrypy.expose
def injection_status( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','injection_status.html'))
@cherrypy.expose
def mccms_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','mccms.html'))
@cherrypy.expose
def settings_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','settings.html'))
@cherrypy.expose
def invalidations_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','invalidations.html'))
@cherrypy.expose
def edit_many_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','edit_many.html'))


@cherrypy.expose
def dashboard_html(*args, **kwargs):
    return open(os.path.join(file_location, 'HTML', 'dashboard.html'))
@cherrypy.expose
def graph_painter_html(*args, **kwargs):
    return open(os.path.join(file_location, 'HTML', 'graph_painter.html'))

@cherrypy.expose
def graph_representation_html(*args, **kwargs):
    return open(os.path.join(file_location, 'HTML', 'graph.html'))

### END OF UPDATED METHODS###
root = index

# web apps (relevant to interface)
root.search = Search()
root.multi_search = MultiSearch()

root.campaigns = campaigns_html
root.chained_campaigns = chained_campaigns_html
root.chained_requests = chained_requests_html
root.requests = requests_html
root.flows = flows_html
root.edit = edit_html
root.create = create_html
root.priority_change = priority_change_html
root.getDefaultSequences = getDefaultSequences
root.injectAndLog = injectAndLog
root.users = users
root.batches = batches
root.invalidations = invalidations_html
root.injection_status = injection_status
root.dashboard = dashboard_html
root.edit_many = edit_many_html
root.mccms = mccms_html
root.settings = settings_html
root.graph = graph_painter_html
root.graph_representation = graph_representation_html

# REST API - RESTResourceIndex is the directory of available commands
root.restapi = RESTResourceIndex()
root.restapi.requests = RESTResourceIndex()
root.restapi.campaigns = RESTResourceIndex()
root.restapi.chained_requests = RESTResourceIndex()
root.restapi.chained_campaigns = RESTResourceIndex()
root.restapi.actions = RESTResourceIndex()
root.restapi.flows = RESTResourceIndex()
root.restapi.users = RESTResourceIndex()
root.restapi.batches = RESTResourceIndex()
root.restapi.invalidations = RESTResourceIndex()
root.restapi.dashboard = RESTResourceIndex()
root.restapi.mccms = RESTResourceIndex()
root.restapi.settings = RESTResourceIndex()
root.restapi.tags = RESTResourceIndex()
root.restapi.control = RESTResourceIndex()
root.restapi.notifications = RESTResourceIndex()

## create a restriction-free urls, with limited capabilities
root.public = RESTResourceIndex()
root.public.restapi = RESTResourceIndex()
root.public.restapi.requests = RESTResourceIndex()
root.public.restapi.requests.get = GetRequest()
root.public.restapi.requests.get_fragment = GetFragmentForRequest()
root.public.restapi.requests.get_setup = GetSetupForRequest()
root.public.restapi.requests.get_test = GetSetupForRequest(mode='test')
root.public.restapi.requests.get_valid = GetSetupForRequest(mode='valid')
root.public.restapi.requests.get_status = GetStatus()
root.public.restapi.requests.get_actors = GetActors()
root.public.restapi.requests.produces = GetRequestByDataset()
root.public.restapi.requests.output = GetRequestOutput()
root.public.restapi.chained_requests = RESTResourceIndex()
root.public.restapi.chained_requests.get_setup = GetSetupForChains()
root.public.restapi.chained_requests.get_test = GetSetupForChains(mode='test')
root.public.restapi.chained_requests.get_valid = GetSetupForChains(mode='valid')
root.public.restapi.chained_requests.get_dict = TaskChainDict()
root.public.restapi.requests.get_dict = TaskChainRequestDict()

# REST API - root.restapi.[db name].[action]
# dwells on : /restapi/[db_name]/[action]

# - 'save' actions require a JSON object through PUT requests
# - 'delete' actions require a DELETE HTTP request
# - 'update' actions require a JSON object with a CouchDB _rev defined through a PUT HTTP request
# - 'get' actions are request through HTTP GET and return a json

# REST User actions
root.restapi.users.get_role = GetUserRole()
root.restapi.users.get_pwg = GetUserPWG()
root.restapi.users.get_all_roles = GetAllRoles()
root.restapi.users.get_all_users = GetAllUsers()
root.restapi.users.add_role = AddRole()
root.restapi.users.ask_role = AskRole()
root.restapi.users.change_role = ChangeRole()
root.restapi.users.get = GetUser()
root.restapi.users.save = SaveUser()
root.restapi.users.update = SaveUser()
root.restapi.users.fill_full_names = FillFullNames()
root.restapi.users.notify_pwg = NotifyPWG()

# REST request actions
root.restapi.requests.save = ImportRequest()
root.restapi.requests.update = UpdateRequest()
root.restapi.requests.manage = ManageRequest()
root.restapi.requests.delete = DeleteRequest()
root.restapi.requests.clone = CloneRequest()
root.restapi.requests.get = GetRequest()
root.restapi.requests.get_cmsDrivers = GetCmsDriverForRequest()
root.restapi.requests.approve = ApproveRequest()
root.restapi.requests.reset = ResetRequestApproval()
root.restapi.requests.soft_reset = ResetRequestApproval(hard=False)
root.restapi.requests.status = SetStatus()
root.restapi.requests.upload = UploadConfig()
root.restapi.requests.inject = InjectRequest()
root.restapi.requests.injectlog = ReadInjectionLog()
root.restapi.requests.editable = GetEditable()
root.restapi.requests.default_generator_params = GetDefaultGenParams()
root.restapi.requests.register = RegisterUser()
root.restapi.requests.notify = NotifyUser()
root.restapi.requests.migrate = MigrateRequest()
root.restapi.requests.inspect = InspectStatus()
root.restapi.requests.update_stats = UpdateStats()
root.restapi.requests.listwithfile = RequestsFromFile()
root.restapi.requests.test = TestRequest()
root.restapi.requests.searchable = SearchableRequest()
root.restapi.requests.reminder = RequestsReminder()
root.restapi.requests.stalled = StalledReminder()
root.restapi.requests.perf_report = RequestPerformance()
root.restapi.requests.update_many = UpdateMany()
root.restapi.requests.all_revs = GetAllRevisions()
root.restapi.requests.search_view = ListRequestPrepids()
root.restapi.requests.option_reset = OptionResetForRequest()
root.restapi.requests.get_inject = GetInjectCommand()
root.restapi.requests.get_upload = GetUploadCommand()
root.restapi.requests.unique_values = GetUniqueValues()
root.restapi.requests.add_forcecomplete = PutToForceComplete()
root.restapi.requests.forcecomplete = ForceCompleteMethods()
root.restapi.requests.reserveandapprove = Reserve_and_ApproveChain()
root.restapi.requests.priority_change = RequestsPriorityChange()

# REST Campaign Actions
root.restapi.campaigns.save = CreateCampaign()
root.restapi.campaigns.update = UpdateCampaign()
root.restapi.campaigns.delete = DeleteCampaign()
root.restapi.campaigns.get = GetCampaign()
root.restapi.campaigns.approve = ApproveCampaign()
root.restapi.campaigns.get_all = GetAllCampaigns()
root.restapi.campaigns.status = ToggleCampaignStatus()
root.restapi.campaigns.get_cmsDrivers = GetCmsDriverForCampaign()
root.restapi.campaigns.migrate = MigratePage()
root.restapi.campaigns.listall = ListAllCampaigns()
root.restapi.campaigns.inspect = InspectRequests()
root.restapi.campaigns.inspectall = InspectCampaigns()

# REST Chained Campaign Actions
root.restapi.chained_campaigns.save = CreateChainedCampaign()
root.restapi.chained_campaigns.delete = DeleteChainedCampaign()
root.restapi.chained_campaigns.get = GetChainedCampaign()
root.restapi.chained_campaigns.update = UpdateChainedCampaign()
root.restapi.chained_campaigns.inspect = InspectChainedRequests()
root.restapi.chained_campaigns.inspectall = InspectChainedCampaigns()
root.restapi.chained_campaigns.select = SelectNewChainedCampaigns()
root.restapi.chained_campaigns.search_view = ListChainCampaignPrepids()
root.restapi.chained_campaigns.priority_change = ChainedCampaignsPriorityChange()

# REST Chained Request Actions
root.restapi.chained_requests.request_chainid = ChainedRequestPrepId()
root.restapi.chained_requests.save = CreateChainedRequest()
root.restapi.chained_requests.update = UpdateChainedRequest()
root.restapi.chained_requests.delete = DeleteChainedRequest()
root.restapi.chained_requests.get = GetChainedRequest()
root.restapi.chained_requests.flow = FlowToNextStep()
root.restapi.chained_requests.rewind = RewindToPreviousStep()
root.restapi.chained_requests.approve = ApproveChainedRequest()
root.restapi.chained_requests.inspect = InspectChain()
root.restapi.chained_requests.fullhistory = GetConcatenatedHistory()
root.restapi.chained_requests.searchable = SearchableChainedRequest()
root.restapi.chained_requests.inject = InjectChainedRequest(mode='inject')
root.restapi.chained_requests.soft_reset = SoftResetChainedRequest()
root.restapi.chained_requests.get_inject = InjectChainedRequest(mode='show')
root.restapi.chained_requests.test = TestChainedRequest()
root.restapi.chained_requests.test_ds_output = TestOutputDSAlgo()
root.restapi.chained_requests.force_done = ForceChainReqToDone()
root.restapi.chained_requests.back_forcedone = ForceStatusDoneToProcessing()
root.restapi.chained_requests.force_flow = ToForceFlowList()
root.restapi.chained_requests.remove_force_flow = RemoveFromForceFlowList()
root.restapi.chained_requests.priority_change = ChainedRequestsPriorityChange()
root.restapi.chained_requests.from_ticket = ChainsFromTicket()

# REST Flow Actions
root.restapi.flows.get = GetFlow()
root.restapi.flows.save = CreateFlow()
root.restapi.flows.update = UpdateFlow()
root.restapi.flows.delete = DeleteFlow()
root.restapi.flows.approve = ApproveFlow()

# REST Batches Actions
root.restapi.batches.get = GetBatch()
root.restapi.batches.save = SaveBatch()
root.restapi.batches.update = UpdateBatch()
root.restapi.batches.get_all_batches = GetAllBatches()
root.restapi.batches.announce = AnnounceBatch()
root.restapi.batches.redirect = GetIndex()
root.restapi.batches.inspect = InspectBatches()
root.restapi.batches.reset = ResetBatch()
root.restapi.batches.hold = HoldBatch()
root.restapi.batches.notify = NotifyBatch()

# REST invalidation Actions
root.restapi.invalidations.get = GetInvalidation()
root.restapi.invalidations.delete = DeleteInvalidation()
root.restapi.invalidations.announce = AnnounceInvalidations()
root.restapi.invalidations.clear = ClearInvalidations()
root.restapi.invalidations.acknowledge = AcknowledgeInvalidation()
root.restapi.invalidations.new_to_hold = PutOnHoldInvalidation()
root.restapi.invalidations.hold_to_new = PutHoldtoNewInvalidations()

# REST dashboard Actions
root.restapi.dashboard.get_bjobs = GetBjobs()
root.restapi.dashboard.get_log_feed = GetLogFeed()
root.restapi.dashboard.get_logs = GetLogs()
root.restapi.dashboard.get_revision = GetRevision()
root.restapi.dashboard.get_start_time = GetStartTime(start_time)
root.restapi.dashboard.get_verbosities = GetVerbosities()
root.restapi.dashboard.get_connection = TestConnection()
root.restapi.dashboard.get_releases = ListReleases()
root.restapi.dashboard.lock_info = GetLocksInfo()
root.restapi.dashboard.queue_info = GetQueueInfo()

# REST mccms Actions
root.restapi.mccms.get = GetMccm()
root.restapi.mccms.update = UpdateMccm()
root.restapi.mccms.save = CreateMccm()
root.restapi.mccms.delete = DeleteMccm()
root.restapi.mccms.cancel = CancelMccm()
root.restapi.mccms.editable = GetEditableMccmFields()
root.restapi.mccms.generate = GenerateChains()
root.restapi.mccms.reminder = MccMReminderProdManagers()
root.restapi.mccms.reminder_gen_contacts = MccMReminderGenContacts()
root.restapi.mccms.update_total_events = CalculateTotalEvts()

# REST settings Actions
root.restapi.settings.get = GetSetting()
root.restapi.settings.update = UpdateSetting()
root.restapi.settings.save = SaveSetting()

# REST tags Actions
root.restapi.tags.get_all = GetTags()
root.restapi.tags.add = AddTag()
root.restapi.tags.remove = RemoveTag()

# REST control Actions
root.restapi.control.renew_cert = RenewCertificate()
root.restapi.control.set_verbosity = ChangeVerbosity()
root.restapi.control.turn_off = TurnOffServer()
root.restapi.control.reset_rest_counter = ResetRESTCounters()
root.restapi.control.communicate = Communicate()

# REST notification Actions
root.restapi.notifications.check = CheckNotifications()
root.restapi.notifications.fetch = FetchNotifications()
root.restapi.notifications.seen = SaveSeen()
root.restapi.notifications.fetch_actions = FetchActionObjects()
root.restapi.notifications.fetch_group_actions = FetchGroupActionObjects()

##Define loggers

log = cherrypy.log
log.error_file = None
log.access_file = None

#ERROR log file
maxBytes = getattr(log, "rot_maxBytes", 10000000)
backupCount = getattr(log, "rot_backupCount", 1000)
fname = getattr(log, "rot_error_file", "logs/error.log")

logger = logging.getLogger()
logger.setLevel(0)

ha = logging.handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
error_formatter = logging.Formatter(fmt='[%(asctime)s][%(user)s][%(levelname)s] %(message)s',
        datefmt='%d/%b/%Y:%H:%M:%S')

usr_filt = UserFilter()
ha.setFormatter(error_formatter)
ha.addFilter(usr_filt)
log.error_log.addHandler(ha)
error_logger = logging.getLogger("mcm_error")
error_logger.addHandler(ha)

# set up injection logger
##due to LogAdapter empty space for message will be added inside of it
inject_formatter = logging.Formatter(fmt='[%(asctime)s][%(levelname)s]%(message)s',
        datefmt='%d/%b/%Y:%H:%M:%S')
inject_logger = logging.getLogger("mcm_inject")
hi = logging.FileHandler('logs/inject.log', 'a')
hi.setFormatter(inject_formatter)
inject_logger.addHandler(hi)

#Access log file
fname = getattr(log, "rot_access_file", "logs/access.log")
h = logging.handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
rest_formatter = logging.Formatter(fmt='{%(mem)s} [%(asctime)s][%(user)s][%(levelname)s] %(message)s',
        datefmt='%d/%b/%Y:%H:%M:%S')

mem_filt = MemoryFilter()
h.setLevel(logging.DEBUG)
h.setFormatter(rest_formatter)
h.addFilter(usr_filt)
h.addFilter(mem_filt)
log.access_log.addHandler(h)

def start():
    error_logger.info(".mcm_rest_counter persistence opening")
    error_logger.info("CherryPy version:%s" % (cherrypy.__version__))
    RESTResource.counter = shelve.open('.mcm_rest_counter')

def stop():
    error_logger.info(".mcm_rest_counter persistence closing")
    RESTResource.counter.close()
    error_logger.info("Flushing communications")
    com = communicator()
    com.flush(0)

def maintain():
    if not cherrypy.engine.execv:
        error_logger.info("going to maintenance")
        subprocess.call("python2.6 main_tenance.py &", shell=True)

cherrypy.engine.subscribe('start', start)
cherrypy.engine.subscribe('stop', stop)
cherrypy.engine.subscribe('exit', maintain)
cherrypy.engine.signal_handler.handlers['SIGINT'] = cherrypy.engine.exit

#START the engine
cherrypy.quickstart(root, config='configuration/cherrypy.conf')
