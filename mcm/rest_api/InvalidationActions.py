#!/usr/bin/env python

import cherrypy
import sys
import traceback
import string
import time
import itertools
from math import sqrt
from json import loads, dumps
from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResource
from tools.communicator import communicator
from tools.locator import locator
from json_layer.invalidation import invalidation
from tools.settings import settings

class Invalidate(RESTResource):

    def __init__(self):
        self.access_limit = 4

    def GET(self, *args):
        """
        Operate the invalidation of a given document
        """
        if not len(args):
            return dumps({'results': False, 'message': 'not id has been provided'})

        docid = args[0]
        invalidations = database('invalidations')
        if not invalidations.document_exists(docid):
            return dumps({'results': False, 'message': '%s does not exists' % docid})

        invalid = invalidation(invalidations.get(docid))
        if invalid.get_attribute('type') in ['request', 'dataset']:
            return dumps({'results': False,
                          'message': 'Not implemented to invalidate {0}s'.format(invalid.get_attribute('type'))})
        else:
            return dumps({'results': False, 'message': 'Type {0} not recognized'.format(invalid.get_attribute('type'))})


class SetStatus(RESTResource):

    def __init__(self):
        self.access_limit = 4

    def GET(self, *args):
        """
        Set the status of an invalidation to the next status
        """
        if not len(args):
            return dumps({'results': False, 'message': 'not id has been provided'})

        docid = args[0]
        invalidations = database('invalidations')
        if not invalidations.document_exists(docid):
            return dumps({'results': False, 'message': '%s does not exists' % ( docid)})

        invalid = invalidation(invalidations.get(docid))
        invalid.set_status()
        invalidations.update(invalid.json())
        return dumps({'results': True})


class InspectInvalidation(RESTResource):

    def __init__(self):
        self.access_limit = 3

    def GET(self, *args):
        """
        Goes through invalidation documents and display (/) and announce them to data ops (/announce)
        """

        announce = False
        clear = False
        if len(args) != 0:
            if args[0] == 'announce':
                announce = True
            if args[0] == 'clear':
                clear = True

        idb = database('invalidations')
        r_to_be_rejected = map(invalidation, idb.queries(['status==new', 'type==request']))
        ds_to_be_invalidated = map(invalidation, idb.queries(['status==new', 'type==dataset']))
        ds_to_be_invalidated = filter(lambda ds : not 'None-' in ds.get_attribute('object'), ds_to_be_invalidated)
        l_type = locator()

        def add_prepid(invalid, html):
            if 'prepid' in invalid.json():
                html += 'for request <a href=%srequests?prepid=%s> %s </a>' % (
                    l_type.baseurl(), invalid.get_attribute('prepid'), invalid.get_attribute('prepid'))

        def print_invalidations(invalids):
            a_text=''
            for invalid in invalids:
                a_text += ' %s\n' % (invalid.get_attribute('object'))
            return a_text

        html = '<html><body>\n'
        html += 'Requests to be aborted/rejected <br>\n'
        html += '<ul>\n'
        for r in r_to_be_rejected:
            html += '<li> <a href=%sreqmgr/view/details/%s> %s </a>' % (l_type.cmsweburl(), r.get_attribute('object'), r.get_attribute('object') )
            add_prepid(r, html)
            html += '</li>\n'
        html += '</ul>\n'
        html += 'Datasets to be invalidated <br>\n'
        html += '<ul>\n'
        for ds in ds_to_be_invalidated:
            html += '<li> %s ' % ( ds.get_attribute('object') )
            add_prepid(ds, html)
            html += '</li>\n'
        html += '</ul>\n'
        html += '<a href=%srestapi/invalidations/inspect/clear> Clear invalidation withouth announcing</a><br>\n'%( l_type.baseurl() )
        html += '<a href=%srestapi/invalidations/inspect/announce> Announce invalidations</a><br>\n'%( l_type.baseurl() )
        html += '<a href=%srestapi/invalidations/inspect> Back</a><br>\n'%( l_type.baseurl() )

        html += '</html></body>\n'

        if announce and (len(ds_to_be_invalidated)!=0 or len(r_to_be_rejected)!=0):
            text = 'Dear Data Operation Team,\n\n'
            if len(r_to_be_rejected)!=0:
                text += 'please reject or abort the following requests:\n'
                text += print_invalidations(r_to_be_rejected)
            if len(ds_to_be_invalidated)!=0:
                text += '\nPlease invalidate the following datasets:\n'
                text += print_invalidations(ds_to_be_invalidated)
            text += '\nas a consequence of requests being reset.\n'
            com = communicator()

            to_who = [settings().get_value('service_account')]
            if l_type.isDev():
                to_who.append( settings().get_value('hypernews_test'))
            else:
                to_who.append( settings().get_value('dataops_announce' ))

            try:
                elem = (r_to_be_rejected + ds_to_be_invalidated)[0]
                sender = elem.current_user_email
            except IndexError:
                sender = None

            com.sendMail(to_who,
                         'Request and Datasets to be Invalidated',
                         text,
                         sender)

            for to_announce in itertools.chain(r_to_be_rejected, ds_to_be_invalidated):
                to_announce.set_announced()
                idb.update(to_announce.json())

        if clear and (len(ds_to_be_invalidated)!=0 or len(r_to_be_rejected)!=0):
            for to_announce in itertools.chain(r_to_be_rejected, ds_to_be_invalidated):
                to_announce.set_announced()
                idb.update(to_announce.json())

        return html


class GetInvalidation(RESTResource):

    def __init__(self):
        self.access_limit = 4

    def GET(self, *args):
        """
        Retrieve the content of a given invalidation object
        """
        if not args:
            self.logger.error('No arguments were given.')
            return dumps({"results": False})
        return self.get_request(args[0])

    def get_request(self, object_name):
        db = database('invalidations')
        return dumps({"results": db.get(object_name)})
