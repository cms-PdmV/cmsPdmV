import cherrypy
from web_apps.Page import Page
from web_apps.Search import Search
from web_apps.Results import Results
from web_apps.Edit import Edit
from web_apps.Create import Create  
from web_apps.Actions import Actions
from rest_api.RestAPIMethod import RESTResourceIndex
from rest_api.RequestActions import ImportRequest, DeleteRequest, GetRequest, UpdateRequest, GetCmsDriverForRequest,  ApproveRequest,  InjectRequest
from rest_api.CampaignActions import CreateCampaign, DeleteCampaign, UpdateCampaign, GetCampaign,  ToggleCampaign
from rest_api.ChainedCampaignActions import CreateChainedCampaign, DeleteChainedCampaign, GetChainedCampaign, UpdateChainedCampaign,  GenerateChainedRequests as chained_generate_requests
from rest_api.ChainedRequestActions import CreateChainedRequest, UpdateChainedRequest, DeleteChainedRequest, GetChainedRequest, AddRequestToChain,  FlowToNextStep,  ApproveRequest as ApproveChainedRequest
from rest_api.FlowActions import CreateFlow,  UpdateFlow,  DeleteFlow,  GetFlow,  ApproveFlow
from rest_api.ActionsActions import GetAction,  SelectChain,  DeSelectChain,  GenerateChainedRequests,  DetectChains,  GenerateAllChainedRequests
from rest_api.RequestPrepId import RequestPrepId 
from rest_api.RequestChainId import RequestChainId

# Initialize Web UI Page Objects

# home (root)
home = Page(title='Prep 2.0.1 - Alpha version', result='<div class="list" id="result_list"></div>', signature='PREP v.2.0.1 - CherryPy v.3.2.2')
home.render_template('main.tmpl')

# campaigns
campaigns = Page(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
campaigns.render_template('campaigns.tmpl')

# requests
requests = Page(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
requests.render_template('requests.tmpl')

# chained campaigns
chained_campaigns = Page(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
chained_campaigns.render_template('chained_campaigns.tmpl')

# chained requests
chained_requests = Page(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
chained_requests.render_template('chained_requests.tmpl')

# flows
flows = Page(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
flows.render_template('flows.tmpl')

# Web apps - Results, Edit, Create
results = Results(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
edit = Edit(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
create = Create(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
actions = Actions(title='Prep 2.0.1 - Alpha version', signature='PREP v.2.0    .1 - CherryPy v.3.2.2')
actions.render_template('actions.tmpl')

# root
root = home

# web apps (relevant to interface)
root.search = Search()
root.campaigns = campaigns
root.chained_campaigns = chained_campaigns
root.chained_requests = chained_requests
root.requests = requests
root.flows = flows
root.results = results
root.edit = edit
root.create = create
root.actions = actions

# REST API - RESTResourceIndex is the directory of available commands
root.restapi = RESTResourceIndex()
root.restapi.requests = RESTResourceIndex()
root.restapi.campaigns = RESTResourceIndex()
root.restapi.chained_requests = RESTResourceIndex()
root.restapi.chained_campaigns = RESTResourceIndex()
root.restapi.actions = RESTResourceIndex()
root.restapi.flows = RESTResourceIndex()

# REST API - root.restapi.[db name].[action]
# dwells on : /restapi/[db_name]/[action]

# - 'save' actions require a JSON object through PUT requests
# - 'delete' actions require a DELETE HTTP request
# - 'update' actions require a JSON object with a CouchDB _rev defined through a PUT HTTP request
# - 'get' actions are request through HTTP GET and return a json

# REST request actions
root.restapi.requests.save = ImportRequest()
root.restapi.requests.update = UpdateRequest()
root.restapi.requests.delete = DeleteRequest()
root.restapi.requests.get = GetRequest()
root.restapi.requests.get_cmsDrivers = GetCmsDriverForRequest() 
root.restapi.requests.request_prepid = RequestPrepId()
root.restapi.requests.approve = ApproveRequest()
root.restapi.requests.inject = InjectRequest()

# REST Campaign Actions
root.restapi.campaigns.save = CreateCampaign()
root.restapi.campaigns.update = UpdateCampaign()
root.restapi.campaigns.delete = DeleteCampaign()
root.restapi.campaigns.get = GetCampaign()
root.restapi.campaigns.toggle = ToggleCampaign() # start/stop campaign

# REST Chained Campaign Actions
root.restapi.chained_campaigns.save = CreateChainedCampaign()
root.restapi.chained_campaigns.delete = DeleteChainedCampaign()
root.restapi.chained_campaigns.get = GetChainedCampaign()
root.restapi.chained_campaigns.update = UpdateChainedCampaign()
root.restapi.chained_campaigns.generate_chained_requests = chained_generate_requests()

# REST Chained Request Actions
root.restapi.chained_requests.request_chainid = RequestChainId()
root.restapi.chained_requests.save = CreateChainedRequest()
root.restapi.chained_requests.update = UpdateChainedRequest()
root.restapi.chained_requests.delete = DeleteChainedRequest()
root.restapi.chained_requests.get = GetChainedRequest()
root.restapi.chained_requests.add_to_chain = AddRequestToChain()
root.restapi.chained_requests.flow = FlowToNextStep()
root.restapi.chained_requests.approve = ApproveChainedRequest()

# REST Actions
root.restapi.actions.get = GetAction()
root.restapi.actions.select = SelectChain()
root.restapi.actions.deselect = DeSelectChain()
root.restapi.actions.generate_chained_requests = GenerateChainedRequests()
root.restapi.actions.detect_chains = DetectChains()
root.restapi.actions.generate_all_chained_requests = GenerateAllChainedRequests()

# REST Flow Actions
root.restapi.flows.get = GetFlow()
root.restapi.flows.save = CreateFlow()
root.restapi.flows.update = UpdateFlow()
root.restapi.flows.delete = DeleteFlow()
root.restapi.flows.approve = ApproveFlow()

# Use global configs
cherrypy.quickstart(root, config='configuration/cherrypy.conf')
