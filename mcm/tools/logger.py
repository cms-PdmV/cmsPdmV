#!/usr/bin/env python

import logging
import os


class InjectionLogAdapter(logging.LoggerAdapter):
    """
    Custom Adapter to modify message with extra info e.g. prepid
    """
    def process(self, msg, kwargs):
        return '[%s] %s' % (self.extra['handle'], msg), kwargs


class UserFilter(logging.Filter):
    """
    This is a filter which injects contextual information into the log.
    """

    def filter(self, record):
        from tools.user_management import user_pack
        email = user_pack().get_email()
        if email:
            record.user = email
        else:
            record.user = "main_thread"
        return True


class MemoryFilter(logging.Filter):
    """
    This is a filter which injects contextual information into the log.
    """

    def filter(self, record):
        # memory usage
        try:
            _proc_status = '/proc/%d/status' % os.getpid()
            t = open(_proc_status)
            v = t.read()
            t.close()
            i = v.index('VmRSS')
            v = v[i:].split(None, 3)  # whitespace
            mem = "%s %s" % (v[1], v[2])
        except Exception:
            mem = "N/A"

        record.mem = mem
        return True
