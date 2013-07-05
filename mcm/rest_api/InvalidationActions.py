#!/usr/bin/env python

import cherrypy
import sys
import traceback
import string
import time
from math import sqrt
from json import loads,dumps
from couchdb_layer.prep_database import database
from RestAPIMethod import RESTResource
from tools.communicator import communicator
from tools.locator import locator

class InspectInvalidation(RESTResource):  
    def __init__(self):
        self.access_limit =3

    def GET(self, *args):
        """
        Goes through invalidation documents and display (/) and announce them to data ops (/announce)
        """

        announce=False
        if len(args)!=0:
            if args[0]=='announce':
                announce=True
        
        idb = database('invalidations')
        
        r_to_be_rejected = idb.queries(['status==new','type==request'])
        ds_to_be_invalidated = idb.queries(['status==new','type==dataset'])

        html='<html><body>\n'
        html+='Requests to be aborted/rejected <br>\n'
        html+='<ul>\n'
        for r in r_to_be_rejected:
            html+='<li> <a href=%s> %s </a> </li>\n'%( r['object'] ,r['object'] )
        html+='</ul>\n'
        html+='Datasets be invalidated <br>\n'
        html+='<ul>\n'
        for ds in ds_to_be_invalidated:
            html+='<li> %s </li>'%( ds['object'] )
        html+='</ul>\n' 
        html+='</html></body>\n'

        if announce:
            text ='Dear Data Operation Team,\n\n'
            text+='please reject or abort the following requests:\n'
            for r in r_to_be_rejected:
                text+=' %s\n'%(r['object'])
            text+='\n'
            text+='Please invalidate the following datasets:\n'
            for ds in ds_to_be_invalidated:
                text+=' %s\n'%(ds['object'])
            text+='\n'
            text+'as a consequence of requests being reset.\n'
            com = communicator()

            l_type= locator()
            to_who = ['pdmvserv@cern.ch']
            if not l_type.isDev():
                to_who.append( 'hn-cms-dataopsrequests@cern.ch' )

            ## to be replace
            com.sendMail(['vlimant@cern.ch'],
                         'Request and Datasets to be Invalidated',
                         text)

        return html
