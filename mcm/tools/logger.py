import logging
from flask import request
from flask import g as request_context


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
        if not request_context:
            record.user = 'main_thread'
        else:
            email = request.headers.get('Adfs-Email')
            if email:
                record.user = email
            else:
                record.user = 'unknown_email'
        return True
