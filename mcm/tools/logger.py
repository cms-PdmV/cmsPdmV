#!/usr/bin/env python

import sys
import time
import logging


class inject_formatter(logging.Formatter):
        def __init__(self, prepid):
                self.prepid = prepid
                logging.Formatter.__init__(self)

        def find_topmost_stack_frame(self):
                i = 0
                stack = []
                while True:
                        try:
                                fr = sys._getframe(i)
                                if fr.f_code.co_name == '__call__':
                                        break
                                stack.append(fr)
                        except:
                                break
                        i += 1

                # get second from top (because topmost belongs to mother class RestAPIMethod)
                return "%s:%s" % (stack[-4].f_code.co_filename, stack[-4].f_lineno)

        def format(self, record):
                try:
                        if record.done:
                                return record.msg
                except:
                        record.done = False

                rtime = time.strftime("%d/%b/%Y:%H:%M:%S", time.localtime(record.created))
                from tools.user_management import user_pack
                email = user_pack().get_email()
                if record.levelno > 20: # above info
                        if email:
                                record.msg = '[%s][user:%s][%s][%s] {%s} %s' % ( rtime,
                                                                        email,
                                                                        record.levelname,
                                                                        self.prepid,
                                                                        self.find_topmost_stack_frame(),
                                                                        record.msg)
                        else:
                                record.msg = '[%s][%s][%s] {%s} %s' % ( rtime,
                                                                record.levelname,
                                                                self.prepid,
                                                                self.find_topmost_stack_frame(),
                                                                record.msg)
                else:
                        if email:
                                record.msg = '[%s][user:%s][%s][%s] %s' % ( rtime,
                                                                        email,
                                                                        record.levelname,
                                                                        self.prepid,
                                                                        record.msg)
                        else:
                                record.msg = '[%s][%s][%s] %s' % ( rtime,
                                                                record.levelname,
                                                                self.prepid,
                                                                record.msg)

                record.done = True
                return logging.Formatter.format(self, record)


class mcm_formatter(logging.Formatter):
    def find_topmost_stack_frame(self):
        i = 0
        stack = []
        while True:
            try:
                fr = sys._getframe(i)
                if fr.f_code.co_name == '__call__':
                        break
                stack.append(fr)
            except:
                break
            i += 1

        # get second from top (because topmost belongs to mother class RestAPIMethod)
        return "%s:%s" % (stack[-4].f_code.co_filename, stack[-4].f_lineno)

    def format(self, record):
        try:
            if record.done:
                    return record.msg
        except:
            record.done = False

        rtime = time.strftime("%d/%b/%Y:%H:%M:%S", time.localtime(record.created))
        from tools.user_management import user_pack
        email = user_pack().get_email()

        if record.levelno > 20:
            if email:
                record.msg = '[%s][user:%s][%s] {%s} %s' % ( rtime, email, record.levelname, self.find_topmost_stack_frame(),
                                                             record.msg)
            else:
                record.msg = '[%s][%s] {%s} %s' % ( rtime, record.levelname, self.find_topmost_stack_frame(), record.msg)
        else:
            if email:
                record.msg = '[%s][user:%s][%s] %s' % ( rtime, email, record.levelname, record.msg)
            else:
                record.msg = '[%s][%s] %s' % ( rtime, record.levelname, record.msg)

        record.done = True
        return logging.Formatter.format(self, record)


class rest_formatter(logging.Formatter):
    def find_topmost_stack_frame(self):
        i = 0
        stack = []
        while True:
            try:
                fr = sys._getframe(i)
                if fr.f_code.co_name == '__call__':
                    break
                stack.append(fr)
            except:
                break
            i += 1

        # get second from top (because topmost belongs to mother class RestAPIMethod)
        return "%s:%s" % (stack[-2].f_code.co_filename, stack[-2].f_lineno)

    def format(self, record):
        try:
            if record.done:
                return record.msg
        except:
            record.done = False

        rtime = time.strftime("%d/%b/%Y:%H:%M:%S", time.localtime(record.created))
        from tools.user_management import user_pack
        email = user_pack().get_email()

        if record.levelno > 20:
            if email:
                record.msg = '[%s][user:%s][%s] {%s} %s' % ( rtime, email, record.levelname,
                                                             self.find_topmost_stack_frame(), record.msg)
            else:
                record.msg = '[%s][%s] {%s} %s' % ( rtime, record.levelname, self.find_topmost_stack_frame(), record.msg)
        else:
            if email:
                record.msg = '[%s][user:%s][%s] %s' % ( rtime, email, record.levelname, record.msg)
            else:
                record.msg = '[%s][%s] %s' % ( rtime, record.levelname, record.msg)

        record.done = True
        return logging.Formatter.format(self, record)


class logger:

    def __init__(self, logger_name='mcm'):
        self.error_logger = logging.getLogger(logger_name+'_error')
        self.inject_logger = logging.getLogger(logger_name+'_inject')
        self.verbosities = {0: "Basic logging", 1: "Error logging", 2: "Error and info logging", 3: "Full logging"}
        self.verbosity = 0
        self.error = None
        self.log = None

        ## those are the handlers for seperate log files when requried
        self.inject_handlers = {}
        ## those are logging in the log/inject.log for central browsing
        self.inject_central_handlers = {}
        self.set_verbosity(max(self.verbosities))

    def set_verbosity(self, verbosity_level):
        self.verbosity = verbosity_level
        if self.verbosity <= 0:
            self.error = self.log = self.empty_log
        elif self.verbosity == 1:
            self.error = self.error_f
            self.log = self.empty_log
        elif self.verbosity >= 2:
            self.error = self.error_f
            self.log = self.log_f

    def get_verbosity(self):
        return self.verbosity

    def get_verbosities(self):
        return self.verbosities

    def error_f(self, msg='', level='error'):
        if msg:
            getattr(self.error_logger, level)(msg)

    def empty_log(self, msg='', level=''):
        pass

    def log_f(self, msg='', level='info'):
        if msg:
            getattr(self.error_logger, level)(msg)

    def add_inject_handler(self, name='', handler=None):
        if name and handler and name not in self.inject_handlers:
            self.inject_handlers[name] = handler
        if name and name not in self.inject_central_handlers:
            hi = logging.FileHandler('logs/inject.log', 'a')
            hi.setFormatter(inject_formatter(name))
            self.inject_central_handlers[name] = hi

    def remove_inject_handler(self, name=''):
        if name and name in self.inject_handlers:
            self.inject_handlers[name].close()
            del self.inject_handlers[name]
        if name and name in self.inject_central_handlers:
            self.inject_central_handlers[name].close()
            del self.inject_central_handlers[name]

    def inject(self, msg='', level='info', handler=''):
        if handler in self.inject_handlers:
            self.inject_logger.addHandler(self.inject_handlers[handler])
        if handler and not handler in self.inject_central_handlers:
            self.add_inject_handler(name=handler)
        if handler in self.inject_central_handlers:
            if len(self.inject_logger.handlers):
                self.inject_logger.handlers[0] = self.inject_central_handlers[handler]
            else:
                self.inject_logger.addHandler(self.inject_central_handlers[handler])

            if msg:
                msg = msg.replace('\n', '<breakline>')
                getattr(self.inject_logger,level)(msg)
                try:
                    self.inject_logger.removeHandler(self.inject_handlers[handler])
                except:
                    pass


logfactory = logger("mcm")