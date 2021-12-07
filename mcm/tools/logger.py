import logging


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
