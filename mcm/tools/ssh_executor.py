import paramiko
import time
import os
import re

import logging
from tools.logger import logfactory, mcm_formatter
from threading import BoundedSemaphore


class ssh_executor:
    logger = logfactory
    semaph = BoundedSemaphore(10)
    def __init__(self, directory=None, prepid=None, server='lxplus.cern.ch'):
        self.ssh_client = None
        self.ssh_server = server
        self.ssh_server_port = 22
        self.ssh_credentials = '/afs/cern.ch/user/p/pdmvserv/private/credentials'
        self.hname = None
        if not (directory is None or prepid is None):
            self.__logfile = os.path.join(directory, prepid + '.log')
            # self.__ssh_logfile = directory + prepid + '_ssh_.log'
            self.hname = prepid

            # filename handler outputting to log
            fh = logging.FileHandler(self.__logfile)
            fh.setLevel(logging.DEBUG) # log filename is most verbose

            # format logs
            fh.setFormatter(mcm_formatter())

            # add handlers to main logger - good to go
            self.logger.add_inject_handler(name=self.hname, handler=fh)
        self.__build_ssh_client()
    
    def __build_ssh_client(self):
        self.ssh_client = paramiko.SSHClient()
        # paramiko.util.log_to_file(self.__ssh_logfile, 10)
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        us,  pw = self.__get_ssh_credentials()
        
        if not us:
            self.logger.inject('Credentials could not be retrieved. Reason: username was None', level='error', handler=self.hname)
            raise paramiko.AuthenticationException('Credentials could not be retrieved.')
        
        try:
            self.ssh_client.connect(self.ssh_server,  port=self.ssh_server_port,  username=us,  password=pw)
        except paramiko.AuthenticationException as ex:
            self.logger.error('Could not authenticate to remove server "%s:%d". Reason: %s' % (self.ssh_server, self.ssh_server_port, ex), level='error', handler=self.hname)
            return
        except paramiko.BadHostKeyException as ex:
            self.logger.inject('Host key was invalid. Reason: %s' % (ex), level='error', handler=self.hname)
            return
        except paramiko.SSHException as ex:
            self.logger.inject('There was a problem with the SSH connection. Reason: %s' % (ex), level='error', handler=self.hname)
            return
        except SocketError  as ex:
            self.logger.inject('Could not allocate socket for SSH. Reason: %s' % (ex), level='error', handler=self.hname)
            return

    def __get_ssh_credentials(self):
        try:
            f = open(self.ssh_credentials,  'r')
            data = f.readlines()
            f.close()
        except IOError as ex:
            self.logger.error('Could not access credential file. IOError: %s' % (ex), level='error')
            return None,  None
        
        username,  password = None,  None
        
        for line in data:
            if 'username:' in line:
                toks = line.split(':')
                if len(toks) < 2:
                    self.logger.inject('Username was None', level='error', handler=self.hname)
                    raise paramiko.AuthenticationException('Username not found.')
                username = toks[1].strip()
            elif 'password' in line:
                toks = line.split(':')
                if len(toks) < 2:
                    self.logger.inject('Password was None', level='error', handler=self.hname)
                    raise paramiko.AuthenticationException('Password not found.')
                password = toks[1].strip()
        
        return username,  password
                
    
    def __remote_exec(self,  cmd=''):
        if not cmd:
            return None,  None,  None
        retry = 1
        retries = 2
        while True:
            try:
                with self.semaph:
                    return self.ssh_client.exec_command(cmd)
            except paramiko.SSHException as ex:
                self.logger.inject('Could not execute remote command. Reason: %s' % (ex), level='error', handler=self.hname)
                return None,  None,  None
            except AttributeError as ex:
                self.logger.inject('There was an AttributeError inside the paramiko during try nr %s. Error: %s ' % (retry, ex), level='error', handler=self.hname)
                retry += 1
                if retry > retries:
                    self.logger.inject('Attribute error two times. Returning nothing.', level='error', handler=self.hname)
                    return None, None, None


    def execute(self, cmd):
        stdin,  stdout,  stderr = self.__remote_exec(cmd)
        return stdin,  stdout,  stderr

    def close_executor(self):
        self.ssh_client.close()
        if self.hname is not None:
            self.logger.remove_inject_handler(self.hname)
