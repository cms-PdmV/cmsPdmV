import time
import os

from threading import Thread

import logging
from tools.logger import logger as logfactory, prep2_formatter
from tools.locator import locator
from tools.batch_control import batch_control
from couchdb_layer.prep_database import database
#from json_layer.request import request
from tools.installer import installer

class handler(Thread):
    """
    a class which threads a list of operations
    """
    logger = logfactory('mcm')
    hname = '' # handler's name

    def __init__(self):
        Thread.__init__(self)
        self.res = []

    def run(self):
        try:
            self.unsafe_run()
            # set the status, save the request, notify ...
            pass
        except:
            ## catch anything that comes this way and handle it
            # logging, rolling back the request, notifying, ...
            pass

    def status(self):
        return self.res


class store_configuration(handler):
    """
    setup the configuration, upload to config cach, sets back the request configId and toggles to approved or defined
    """
    def __init__(self, rid):
        handler.__init__(self)
        self.rid = rid
        self.db = database('requests')

    def run(self):
        location = installer( self.rid, care_on_existing=False, clean_on_exit=False)
        
        test_script = location.location()+'prepare.sh'
        there = open( test_script ,'w')
        time.sleep( 10 )
        mcm_r = request(self.db.get(self.rid))
        there.write( mcm_r.get_setup_file( location.location() ))
        there.close()

        ## or straight with ssh_executor
        batch_test = batch_control( self.rid, test_script )
        success = batch_test.test()

        ids = mcm_r.get_attribute('config_id')
        new_ids = []
        ##initialize with Nones
        for i in range(len(mcm_r.get_attribute('sequences'))):
            new_ids.append(None)

        ## now suck in the configuration files        
        for i in range(len(mcm_r.get_attribute('sequences'))):
            fname= '%s%s_%d.py'%( location.location(), mcm_r.get_attribute('prepid'), i+1)
            if os.path.exists(fname):
                open(fname).read().replace('\n','')


        ##happen a lit of ids of the lenght of sequences
        ids.append( new_ids)
        
        
        location.close()

