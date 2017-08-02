#!/usr/bin/env python

from json_base import json_base
from couchdb_layer.mcm_database import database

class mccm(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'approval': 'none',
        'block': 0,
        'staged': 0,
        'threshold': 0.,
        'meeting': '',
        'deadline': '',
        'history': [],
        'message_id': '',
        'notes': '',
        'pwg': '',
        'requests': [],
        'chains': [],
        'tags': [],
        'repetitions': 1,
        'size': 0,
        'status': 'new',
        'special': False,
        'generated_chains': {},
        'total_events': 0 #Sum of request events in ticket not considering repetitions nor chains
    }

    _json_base__approvalsteps = ['none', 'approved']
    _json_base__status = ['new', 'done']

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}
        # update self according to json_input
        if 'repetitions' in json_input:
            if int(json_input['repetitions']) > 10:
                self.logger.error("Issue in creating mccm... To many repetitions:%s" % (
                        json_input['repetitions']))
                raise Exception('More than 10 repetitions')

        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()
        self.setup()

    @staticmethod
    def get_meeting_date():
        import datetime
        from tools.settings import settings
        t = datetime.date.today()
        meeting_day = int(settings().get_value('mccm_meeting_day'))
        w = 0 if meeting_day>=t.weekday() else 1
        t = t + datetime.timedelta(days=meeting_day-t.weekday(), weeks=w)
        return t

    def get_editable(self):
        editable = dict()
        if self.get_attribute('status') == 'new':
            for key in self._json_base__schema:
                editable[key] = True
            not_editable=["status", "prepid", "meeting", "pwg", "approval", "message_id", "generated_chains"]
            for key in not_editable:
                editable[key] = False
        else:
            for key in self._json_base__schema:
                editable[key] = False
        return editable

    @staticmethod
    def get_mccm_by_generated_chain(chain_id):
        mccms_db = database('mccms')
        __query = mccms_db.construct_lucene_query({'generated_chains' : chain_id})
        result = mccms_db.full_text_search('search', __query, page=-1)
        try:
            return mccm(json_input=result[0])
        except Exception as ex:
            mccms_db.logger.error('Initalization of mccm object failed: %s' % (str(ex)))
            return None
        mccms_db.logger.error('No mccm with generated chain: %s' % (chain_id))
        return None

    def update_mccm_generated_chains(self, chains_requests_dict):
        generated_chains = self.get_attribute('generated_chains')
        for chain, requests in chains_requests_dict.iteritems():
            if chain in generated_chains:
                for request in chains_requests_dict[chain]:
                    generated_chains[chain].append(request)
            else:
                generated_chains[chain] = chains_requests_dict[chain]
        mccms_db = database('mccms')
        mccms_db.save(self.json())

    def get_request_list(self, request_list):
        """
        convert list of requests and range of requests into list
        """
        new_request_list = []
        for req in request_list:
            if isinstance(req, list):
                if len(req) == 1:
                    new_request_list.append(r[0])
                elif len(req) == 2:
                    start = int(req[0].split('-')[2])
                    split = req[1].split('-')
                    end = int(split[2])
                    placeholder = split[0] + '-' + split[1] + '-'
                    while(start <= end):
                        current = str(start)
                        current = '0' * (5 - len(current)) + current
                        new_request_list.append(placeholder + current)
                        start += 1
            else:
                new_request_list.append(req)
        return new_request_list

    def update_total_events(self):
        """
        calculate total_evts for  request list
        """

        requests_db = database('requests')
        index = 0
        fetched_requests = []
        new_requests = self.get_request_list(self.get_attribute("requests"))

        while len(new_requests) > index:
            query = requests_db.construct_lucene_query({'prepid':
                    new_requests[index:index+20]}, boolean_operator='OR')

            fetched_requests += requests_db.full_text_search("search", query,
                    page=-1)

            index += 20

        fetched_requests_dict = {}
        for req in fetched_requests:
            fetched_requests_dict[req['prepid']] = req['total_events'] if 'total_events' in req else 0
        events = 0
        for req in new_requests:
            events += fetched_requests_dict[req] if req in fetched_requests_dict else 0

        self.set_attribute('total_events', events)