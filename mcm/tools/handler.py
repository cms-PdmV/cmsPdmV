import time
import os
import traceback

from threading import Thread, Lock

import logging
from tools.logger import logger as logfactory, prep2_formatter
from tools.locator import locator
from tools.batch_control import batch_control
from couchdb_layer.prep_database import database
from collections import Iterable
#from json_layer.request import request
from tools.installer import installer


class PoolOfHandlers(Thread):
    """
    Class used for instantiating and taking care of running a number of handlers in parallel. It provides them
    with lock for protection of concurrently-vulnerable parts of program (e.g. database access).
    """

    logger = logfactory('mcm')

    def __init__(self, handler_class, arguments):
        """
        handler_class is used to instantiate the objects.

        arguments parameter is a list of arguments (dictionnaries) passed to the handler_class' constructor method.
        """
        Thread.__init__(self)
        try:
            self._handlers_list = []
            self._lock = Lock()
            for arg in arguments:
                if not isinstance(arg, dict):  # if arg is e.g. list
                    raise TypeError("Arguments should be a list of dictionaries")
                arg['lock'] = self._lock
                self._handlers_list.append(handler_class(**arg))
            self.logger.log("Instantiated %s handlers %s in pool" % (len(arguments), handler_class.__name__))
        except:
            self.logger.error('Failed to instantiate handlers \n %s' % (traceback.format_exc()))

    def run(self):
        """
        Starts the handlers from pool.
        """
        self.logger.log("Starting %s handlers" % (len(self._handlers_list)))
        for handler_object in self._handlers_list:
            handler_object.start()
        for handler_object in self._handlers_list:
            handler_object.join()


class handler(Thread):
    """
    a class which threads a list of operations
    """
    logger = logfactory('mcm')
    hname = '' # handler's name
    lock = None

    def __init__(self, **kwargs):
        Thread.__init__(self)
        self.res = []
        if 'lock' not in kwargs:
            self.lock = Lock()
        else:
            self.lock = kwargs['lock']

    def run(self):
        try:
            self.unsafe_run()
            # set the status, save the request, notify ...
            pass
        except:
            ## catch anything that comes this way and handle it
            # logging, rolling back the request, notifying, ...
            self.rollback()
            pass

    def unsafe_run(self):
        pass

    def rollback(self):
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

