#!/usr/bin/env python

from json_base import json_base

class mccm(json_base):

    def __init__(self, json_input={}):
        self._json_base__approvalsteps = ['none','approved']
        self._json_base__status = ['new', 'done']
        self._json_base__schema = {
            '_id':'',
            'prepid': '',
            'approval': self.get_approval_steps()[0],
            'block': 0,
            'meeting' : '',
            'deadline': '',
            'history': [],
            'message_id': '',
            'notes': '',
            'pwg': '',
            'requests': [],
            'size': 0,
            'status': self.get_status_steps()[0]
            }
        # update self according to json_input
        self.update(json_input)
        self.validate()
        self.get_current_user_role_level()

    def get_editable(self):
        editable= {}
        for key in self._json_base__schema:
            editable[key] = True
        editable['prepid'] = False
        return editable

    @staticmethod
    def get_meeting_date():
        import datetime
        from tools.settings import settings
        t = datetime.date.today()
        meeting_day = int(settings().get_value('mccm_meeting_day'))
        w = 0 if meeting_day>t.weekday() else 1
        t = t + datetime.timedelta(days=meeting_day-t.weekday(), weeks=w)
        return t
