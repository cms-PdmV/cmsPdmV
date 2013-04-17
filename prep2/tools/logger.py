#!/usr/bin/env python

import sys
import time
import logging
import logging.handlers
import cherrypy


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

                if record.levelno > 20: # above info
                        if cherrypy.request.headers and 'ADFS-EMAIL' in cherrypy.request.headers:
                                record.msg = '[%s][user:%s][%s][%s] {%s} %s' % ( rtime,
                                                                        cherrypy.request.headers['ADFS-EMAIL'],
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
                        if cherrypy.request.headers and 'ADFS-EMAIL' in cherrypy.request.headers:
                                record.msg = '[%s][user:%s][%s][%s] %s' % ( rtime,
                                                                        cherrypy.request.headers['ADFS-EMAIL'],
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

class prep2_formatter(logging.Formatter):
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

                if record.levelno > 20:
                        if cherrypy.request.headers and 'ADFS-EMAIL' in cherrypy.request.headers:
                                record.msg = '[%s][user:%s][%s] {%s} %s' % ( rtime,
                                                                        cherrypy.request.headers['ADFS-EMAIL'],
                                                                        record.levelname,
                                                                        self.find_topmost_stack_frame(),
                                                                        record.msg)
                        else:
                                record.msg = '[%s][%s] {%s} %s' % ( rtime,
                                                                record.levelname,
                                                                self.find_topmost_stack_frame(),
                                                                record.msg)
                else:
                        if cherrypy.request.headers and 'ADFS-EMAIL' in cherrypy.request.headers:
                                record.msg = '[%s][user:%s][%s] %s' % ( rtime,
                                                                        cherrypy.request.headers['ADFS-EMAIL'],
                                                                        record.levelname,
                                                                        record.msg)
                        else:
                                record.msg = '[%s][%s] %s' % ( rtime,
                                                                record.levelname,
                                                                record.msg)

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

		if record.levelno > 20:
			if cherrypy.request.headers and 'ADFS-EMAIL' in cherrypy.request.headers:
                        	record.msg = '[%s][user:%s][%s] {%s} %s' % ( rtime,
                                	                                cherrypy.request.headers['ADFS-EMAIL'],
                                        	                        record.levelname, 
									self.find_topmost_stack_frame(),
                                                	                record.msg)
	                else:
        	                record.msg = '[%s][%s] {%s} %s' % ( rtime,
                	                                        record.levelname,
								self.find_topmost_stack_frame(),
                        	                                record.msg)
		else:
 	        	if cherrypy.request.headers and 'ADFS-EMAIL' in cherrypy.request.headers:
        		       	record.msg = '[%s][user:%s][%s] %s' % ( rtime,
									cherrypy.request.headers['ADFS-EMAIL'], 
									record.levelname,
									record.msg)
	                else:
        	                record.msg = '[%s][%s] %s' % ( rtime,
								record.levelname,
								record.msg)

		record.done = True
                return logging.Formatter.format(self, record)

class logger:
	def __init__(self, logger_name='prep2', error_log='logs/error.log', access_log='logs/access.log'):
		self.error_logger = logging.getLogger(logger_name+'_error')
		self.inject_logger = logging.getLogger('prep2_inject')

		self.inject_handlers = {}
		#self.access_logger =logging.getLogger(logger_name+'_access')

	def add_inject_handler(self, name='', handler=None):
		if name and handler and name not in self.inject_handlers:
			self.inject_handlers[name] = handler
			hi = logging.FileHandler('logs/inject.log', 'a')
			hi.setFormatter(inject_formatter(name))

			self.inject_handlers[name+'_central'] = hi

	def remove_inject_handler(self, name=''):
		if name and name in self.inject_handlers:
			self.inject_handlers[name].close()
			self.inject_handlers[name+'_central'].close()

			del self.inject_handlers[name]
			del self.inject_handlers[name+'_central']

	def error(self, msg='', level='error'):
		if msg:
			if level == 'warning':
				self.error_logger.warning(msg)
			elif level == 'error':
				self.error_logger.error(msg)
			elif level == 'critical':
				self.error_logger.critical(msg)
			else:
				self.error_logger.error(msg)

	
	#def access(self, msg='', level='debug'):
#		if msg:
#			if level == 'debug':
#				self.access_logger.debug(msg)
#			elif level == 'info':
#				self.access_logger.info(msg)
#			else:
#				self.access_logger.debug(msg)

	def log(self, msg='', level='info'):
		if msg:
			if level == 'info':
				self.error_logger.info(msg)
                        elif level == 'debug':
                                self.error_logger.debug(msg)
                        else:
                                self.error_logger.info(msg)   


	def inject(self, msg='', level='info', handler=''):
		if handler in self.inject_handlers:
			self.inject_logger.addHandler(self.inject_handlers[handler])
			self.inject_logger.handlers[0] = self.inject_handlers[handler+'_central']

	        if msg:
				msg = msg.replace('\n', '<breakline>')
				if level == 'info':
					self.inject_logger.info(msg)
				elif level == 'debug':
					self.inject_logger.debug(msg)
				elif level == 'warning':
					self.inject_logger.warning(msg)
				elif level == 'error':
					self.inject_logger.error(msg)
				elif level == 'critical':
					self.inject_logger.critical(msg)
				try:
					self.inject_logger.removeHandler(self.inject_handlers[handler])
					#self.inject_logger.removeHandler(self.inject_handlers[handler+'_central'])
				except:
					pass
