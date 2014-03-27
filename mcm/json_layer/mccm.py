#!/usr/bin/env python

from json_base import json_base


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
        'repetitions': 1,
        'size': 0,
        'status': 'new'
    }

    _json_base__approvalsteps = ['none', 'approved']
    _json_base__status = ['new', 'done']

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}
        # update self according to json_input
        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()

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
            not_editable=["status", "prepid","meeting","pwg","approval","message_id"]
            for key in not_editable:
                editable[key] = False
        else:
            for key in self._json_base__schema:
                editable[key] = False
        return editable
