#!/usr/bin/env python

import sys
import time
import logging
import logging.handlers
import cherrypy

class formatter(logging.Formatter):
	
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
		self.access_logger =logging.getLogger(logger_name+'_access')

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

	
	def access(self, msg='', level='debug'):
		if msg:
			if level == 'debug':
				self.access_logger.debug(msg)
			elif level == 'info':
				self.access_logger.info(msg)
			else:
				self.access_logger.debug(msg)

	def log(self, msg=''):
		if msg:
			self.error_logger.info(msg)
