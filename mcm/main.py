#from web_apps.Page import Page
from web_apps.Search import Search
#from web_apps.Results import Results
#from web_apps.Edit import Edit
#from web_apps.Create import Create
#from web_apps.Actions import Actions
from rest_api.RestAPIMethod import RESTResourceIndex
from rest_api.RequestActions import ImportRequest, ManageRequest, DeleteRequest, GetRequest, UpdateRequest, GetCmsDriverForRequest, GetFragmentForRequest, GetSetupForRequest, ApproveRequest,  InjectRequest, ResetRequestApproval, SetStatus, GetStatus, GetEditable, GetDefaultGenParams, CloneRequest, RegisterUser, MigrateRequest, MigratePage, GetActors, NotifyUser, InspectStatus, UploadFile, SearchRequest
from rest_api.CampaignActions import CreateCampaign, DeleteCampaign, UpdateCampaign, GetCampaign, ToggleCampaign, ToggleCampaignStatus, ApproveCampaign, GetAllCampaigns, GetCmsDriverForCampaign, ListAllCampaigns, InspectRequests, InspectCampaigns
from rest_api.ChainedCampaignActions import CreateChainedCampaign, DeleteChainedCampaign, GetChainedCampaign, UpdateChainedCampaign,  GenerateChainedRequests as chained_generate_requests, InspectChainedRequests, InspectChainedCampaigns
from rest_api.ChainedRequestActions import CreateChainedRequest, UpdateChainedRequest, DeleteChainedRequest, GetChainedRequest, AddRequestToChain,  FlowToNextStep,  ApproveRequest as ApproveChainedRequest, InspectChain
from rest_api.FlowActions import CreateFlow,  UpdateFlow,  DeleteFlow,  GetFlow,  ApproveFlow
from rest_api.ActionsActions import GetAction,  SelectChain,  DeSelectChain,  GenerateChainedRequests,  DetectChains,  GenerateAllChainedRequests, CreateAction, UpdateAction, UpdateMultipleActions
from rest_api.RequestPrepId import RequestPrepId
from rest_api.RequestChainId import RequestChainId
from rest_api.LogActions import ReadInjectionLog
from rest_api.UserActions import GetUserRole, GetAllRoles, GetAllUsers, AddRole, ChangeRole, GetUser, SaveUser, GetUserPWG
from rest_api.BatchActions import GetBatch, GetAllBatches, AnnounceBatch, GetIndex

#to get campaign sequences
from json_layer.sequence import sequence
import json

import logging
import logging.handlers
from tools.logger import rest_formatter, prep2_formatter
import cherrypy #to expose cherrypy methods serving the HTML files
import os

# Initialize Web UI Page Objects

# home (root)
#home = Page(title='Prep 2.0.1 - Alpha version', result='<div class="list" id="result_list"></div>', signature='PREP v.2.0.1 - CherryPy v.3.2.2')
#home.render_template('main.tmpl')

# campaigns
#campaigns = Page(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
#campaigns.render_template('campaigns.tmpl')

# requests
#requests = Page(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
#requests.render_template('requests.tmpl')

# chained campaigns
#chained_campaigns = Page(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
#chained_campaigns.render_template('chained_campaigns.tmpl')

# chained requests
#chained_requests = Page(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
#chained_requests.render_template('chained_requests.tmpl')

# flows
#flows = Page(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
#flows.render_template('flows.tmpl')

# Web apps - Results, Edit, Create
#results = Results(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
#edit = Edit(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
#create = Create(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
#actions = Actions(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
#actions.render_template('actions.tmpl')

file_location = os.path.dirname(__file__)

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
def actions_html( *args, **kwargs):
    return open(os.path.join(file_location,'HTML','actions.html'))
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
### END OF UPDATED METHODS###
# root
#root = home
root = index

# web apps (relevant to interface)
root.search = Search()
#root.campaigns = campaigns
root.campaigns = campaigns_html
#root.chained_campaigns = chained_campaigns
root.chained_campaigns = chained_campaigns_html
#root.chained_requests = chained_requests
root.chained_requests = chained_requests_html
#root.requests = requests
root.requests = requests_html
#root.flows = flows
root.flows = flows_html
#root.results = results
#root.edit = edit
root.edit = edit_html
#root.create = create
root.create = create_html
#root.actions = actions
root.actions = actions_html
root.getDefaultSequences = getDefaultSequences
root.injectAndLog = injectAndLog
root.users = users
root.batches = batches
root.injection_status = injection_status

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

## create a restriction-free urls, with limited capabilities
root.public = RESTResourceIndex()
root.public.restapi = RESTResourceIndex()
root.public.restapi.requests = RESTResourceIndex()
root.public.restapi.requests.get = GetRequest()
root.public.restapi.requests.get_fragment = GetFragmentForRequest()
root.public.restapi.requests.get_setup = GetSetupForRequest()
root.public.restapi.requests.get_status = GetStatus()
root.public.restapi.requests.get_actors = GetActors()
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
root.restapi.users.change_role = ChangeRole()
root.restapi.users.get = GetUser()
root.restapi.users.save = SaveUser()
root.restapi.users.update = SaveUser()

# REST request actions
root.restapi.requests.save = ImportRequest()
root.restapi.requests.update = UpdateRequest()
root.restapi.requests.manage = ManageRequest()
root.restapi.requests.delete = DeleteRequest()
root.restapi.requests.clone = CloneRequest()
root.restapi.requests.get = GetRequest()
root.restapi.requests.get_cmsDrivers = GetCmsDriverForRequest()
#root.restapi.requests.get_fragment = GetFragmentForRequest()
#root.restapi.requests.get_setup = GetSetupForRequest()
#root.restapi.requests.request_prepid = RequestPrepId()
root.restapi.requests.approve = ApproveRequest()
root.restapi.requests.reset = ResetRequestApproval()
root.restapi.requests.status = SetStatus()
root.restapi.requests.inject = InjectRequest()
root.restapi.requests.injectlog = ReadInjectionLog()
root.restapi.requests.editable = GetEditable()
root.restapi.requests.default_generator_params = GetDefaultGenParams()
root.restapi.requests.register = RegisterUser()
root.restapi.requests.notify = NotifyUser()
root.restapi.requests.migrate = MigrateRequest()
root.restapi.requests.inspect = InspectStatus()
root.restapi.requests.listwithfile = UploadFile()
root.restapi.requests.search = SearchRequest()

# REST Campaign Actions
root.restapi.campaigns.save = CreateCampaign()
root.restapi.campaigns.update = UpdateCampaign()
root.restapi.campaigns.delete = DeleteCampaign()
root.restapi.campaigns.get = GetCampaign()
#root.restapi.campaigns.toggle = ToggleCampaign() # start/stop campaign
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
root.restapi.chained_campaigns.generate_chained_requests = chained_generate_requests()
root.restapi.chained_campaigns.inspect = InspectChainedRequests()
root.restapi.chained_campaigns.inspectall = InspectChainedCampaigns()

# REST Chained Request Actions
root.restapi.chained_requests.request_chainid = RequestChainId()
root.restapi.chained_requests.save = CreateChainedRequest()
root.restapi.chained_requests.update = UpdateChainedRequest()
root.restapi.chained_requests.delete = DeleteChainedRequest()
root.restapi.chained_requests.get = GetChainedRequest()
root.restapi.chained_requests.add_to_chain = AddRequestToChain()
root.restapi.chained_requests.flow = FlowToNextStep()
root.restapi.chained_requests.approve = ApproveChainedRequest()
root.restapi.chained_requests.inspect = InspectChain()
# REST Actions
root.restapi.actions.save = CreateAction()
root.restapi.actions.update = UpdateAction()
root.restapi.actions.get = GetAction()
root.restapi.actions.select = SelectChain()
root.restapi.actions.deselect = DeSelectChain()
root.restapi.actions.generate_chained_requests = GenerateChainedRequests()
root.restapi.actions.detect_chains = DetectChains()
root.restapi.actions.generate_all_chained_requests = GenerateAllChainedRequests()
root.restapi.actions.update_multiple = UpdateMultipleActions()

# REST Flow Actions
root.restapi.flows.get = GetFlow()
root.restapi.flows.save = CreateFlow()
root.restapi.flows.update = UpdateFlow()
root.restapi.flows.delete = DeleteFlow()
root.restapi.flows.approve = ApproveFlow()

# REST Batches Actions
root.restapi.batches.get_batch = GetBatch()
root.restapi.batches.get_all_batches = GetAllBatches()
root.restapi.batches.announce = AnnounceBatch()
root.restapi.batches.redirect = GetIndex()

#cherrypy.root = root
#cherrypy.config.update(file = '/home/prep2/configuration/cherrypy.conf')
#cherrypy.server.start()

log = cherrypy.log
log.error_file = None
log.access_file = None

maxBytes = getattr(log, "rot_maxBytes", 10000000)
backupCount = getattr(log, "rot_backupCount", 1000)
fname = getattr(log, "rot_error_file", "logs/error.log")

logger = logging.getLogger()
logger.setLevel(0)

# Make a new RotatingFileHandler for the error log.
h = logging.handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
#h.setLevel(logging.DEBUG)
h.setFormatter(rest_formatter())
log.error_log.addHandler(h)

# set up custom ReST logger
logger = logging.getLogger("rest_error")
logger.addHandler(h)

# set up custom PREP2 logger
ha = logging.handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
#ha.setLevel(logging.DEBUG)
ha.setFormatter(prep2_formatter())
logger = logging.getLogger("prep2_error")
logger.addHandler(ha)

# set up injection logger
logger = logging.getLogger("prep2_inject")
hi = logging.FileHandler('logs/inject.log', 'a')
hi.setFormatter(prep2_formatter())
 
logger.addHandler(hi)

# Make a new RotatingFileHandler for the access log.
fname = getattr(log, "rot_access_file", "logs/access.log")
h = logging.handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
h.setLevel(logging.DEBUG)
h.setFormatter(rest_formatter())
log.access_log.addHandler(h)

cherrypy.quickstart(root, config='configuration/cherrypy.conf')
