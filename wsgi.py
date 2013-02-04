import cherrypy
import sys
import atexit
import os
import socket

#sys.stdout = sys.stderr
sys.stderr = sys.stdout

# mod_wsgi fix
sys.path.append('/home/prep2/')
sys.path.append('/home/')

import main

def application(environ, start_response):
    cherrypy.tree.mount(main.root, script_name='', config='/home/prep2/configuration/cherrypy.conf')
    return cherrypy.tree(environ, start_response)
