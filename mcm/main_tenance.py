import cherrypy
import os
import logging
import logging.handlers
import json
import time
import shelve
import subprocess
from tools.logger import rest_formatter
from rest_api.RestAPIMethod import RESTResourceIndex, RESTResource
from rest_api.ControlActions import TurnOffServer

file_location = os.path.dirname(__file__)

@cherrypy.expose
def maintenance_page(*args, **kwargs):
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

root.restapi = RESTResourceIndex()
root.restapi.users = RESTResourceIndex()
root.restapi.users.get_role = GetDummyUserRole()
root.restapi.news = RESTResourceIndex()
root.restapi.news.getall = GetDummyNews()
root.restapi.control = RESTResourceIndex()
root.restapi.control.turn_on = TurnOffServer()

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

def start():
    RESTResource.counter = shelve.open('.mcm_rest_counter')

def stop():
    RESTResource.counter.close()

cherrypy.engine.subscribe('start', start)
cherrypy.engine.subscribe('stop', stop)

cherrypy.quickstart(root, config='configuration/cherrypy.conf')
