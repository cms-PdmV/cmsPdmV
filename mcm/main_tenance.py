import cherrypy
import os
import logging
import logging.handlers
import json
import time

from tools.logger import rest_formatter
from rest_api.RestAPIMethod import RESTResourceIndex, RESTResource

file_location = os.path.dirname(__file__)

@cherrypy.expose
def maintenance_page():
    return open(os.path.join(file_location,'HTML','maintenance.html'))

#@cherrypy.expose
class GetDummyUserRole(RESTResource):
    def GET(self, *args):
        return json.dumps({"username": "trained", "role_index": 1, "role": "monkey"})

#@cherrypy.expose
class GetDummyNews(RESTResource):
    def GET(self, *args):
        return json.dumps([{"announced":True, "subject":"McM is in maintenance", "text":"", "date" : time.strftime('%Y-%m-%d-%H-%M'),"author" : "support" }])


root = maintenance_page
root.search = maintenance_page
root.campaigns = maintenance_page
root.chained_campaigns = maintenance_page
root.chained_requests = maintenance_page
root.requests = maintenance_page
root.flows = maintenance_page
root.edit = maintenance_page
root.create = maintenance_page
root.actions = maintenance_page
root.getDefaultSequences = maintenance_page
root.injectAndLog = maintenance_page
root.users = maintenance_page
root.batches = maintenance_page
root.invalidations = maintenance_page
root.injection_status = maintenance_page

root.restapi = RESTResourceIndex()
root.restapi.users = RESTResourceIndex()
root.restapi.users.get_role = GetDummyUserRole()
root.news = RESTResourceIndex()
root.restapi.news.getall = GetDummyNews()

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

# Make a new RotatingFileHandler for the access log.
fname = getattr(log, "rot_access_file", "logs/access.log")
h = logging.handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
h.setLevel(logging.DEBUG)
h.setFormatter(rest_formatter())
log.access_log.addHandler(h)

cherrypy.quickstart(root, config='configuration/cherrypy.conf')
