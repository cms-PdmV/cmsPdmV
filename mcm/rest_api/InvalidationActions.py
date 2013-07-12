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

class Invalidate(RESTResource):
    def __init__(self):
        self.access_limit =4
    def GET(self, *args):
        """
        Operate the invalidation of a given document
        """
        if not len(args):
            return dumps({'results':False,'message':'not id has been provided'})

        docid = args[0]
        invalidations = database('invalidations')
        if not invalidations.document_exists(docid):
            return dumps({'results':False,'message':'%s does not exists'%( docid)})
        
        invalid = invalidations.get(docid)
        if invalid['type'] == 'request':
            return dumps({'results':False,'message':'Not implemented to invalidate requests'})
        elif invalid['type'] == 'dataset':
            return dumps({'results':False,'message':'Not implemented to invalidate datasets'})
        else:
            return dumps({'results':False,'message':'Type %s not recognized'%( invalid['type'])})


class SetStatus(RESTResource):
    def __init__(self):
        self.access_limit =4
    def GET(self, *args):
        """
        Set the status of an invalidation to the next status
        """
        if not len(args):
            return dumps({'results':False,'message':'not id has been provided'})

        docid = args[0]
        invalidations = database('invalidations')
        if not invalidations.document_exists(docid):
            return dumps({'results':False,'message':'%s does not exists'%( docid)})
        
        invalid = invalidations.get(docid)
        invalid['status']=done
        invalidations.update( invalid )
        return dumps({'results':True})


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
        
        l_type= locator()

        html='<html><body>\n'
        html+='Requests to be aborted/rejected <br>\n'
        html+='<ul>\n'
        for r in r_to_be_rejected:
            html+='<li> <a href=%sreqmgr/view/details/%s> %s </a>'%(l_type.cmsweburl() , r['object'] ,r['object'] )
            if 'prepid' in r:
                html+='for request <a href=%srequests?prepid=%s> %s </a>'%(l_type.baseurl(), r['prepid'], r['prepid'])
            html+='</li>\n'
        html+='</ul>\n'
        html+='Datasets be invalidated <br>\n'
        html+='<ul>\n'
        for ds in ds_to_be_invalidated:
            html+='<li> %s '%( ds['object'] )
            if 'prepid' in ds:
                html+='for request <a href=%srequests?prepid=%s> %s </a>'%(l_type.baseurl(), ds['prepid'], ds['prepid'])
            html+='</li>\n'
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


            to_who = ['pdmvserv@cern.ch']
            if not l_type.isDev():
                to_who.append( 'hn-cms-dataopsrequests@cern.ch' )

            ## to be replace
            com.sendMail(['vlimant@cern.ch'],
                         'Request and Datasets to be Invalidated',
                         text)

        return html


class GetInvalidation(RESTResource):
    def __init__(self):
        self.access_limit = 4
        self.db = database('invalidations')

    def GET(self, *args):
        """
        Retrieve the content of a given invalidation object
        """
        if not args:
            self.logger.error('No arguments were given.')
            return dumps({"results": False})
        return self.get_request(args[0])

    def get_request(self, object_name):
        return dumps({"results": self.db.get(object_name)})