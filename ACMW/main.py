import cherrypy
import json


import urllib2

import traceback

from display import Simulation, HomePage,Initializer, ListOfSimulations
            
#Initialisation , first define the last heart beat to not get and error during the processing of the JSON file
#Next initialization of the counter that will make beating the heart of the application 
#Next we create list for the treatment of request and other. 
#List Of Attributs will give us the ability to get a lot of things in our code.


@cherrypy.expose
def getAllSimulations():
    data = []
    for elem in ListOfSimulations:
        data.append(elem.getsim())
    return json.dumps(data)
    
@cherrypy.expose
def manualUpdate():
    Initializer().Actualization()
    return "Updated page cache"
    
@cherrypy.expose
def getAllDocs():
    f = urllib2.urlopen('http://cms-pdmv-stats:5984/stats/_all_docs')
    data = f.read()
    return data
    
root = HomePage()
root.simulation_list = getAllSimulations
root.update_all = manualUpdate
root.Db_all = getAllDocs
Initializer().Actualization()
cherrypy.quickstart(root, config='prod.conf')
