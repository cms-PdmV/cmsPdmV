import paramiko
import time
import logging
import random
import os
import tools.settings as settings
from tools.logger import InjectionLogAdapter
from threading import BoundedSemaphore


class ssh_executor:
    semaph = BoundedSemaphore(10)

    def __init__(self, directory=None, prepid=None, server=None):
        self.ssh_client = None
        if not server:
            server = settings.get_value("node_for_test")
        self.ssh_server = server
        self.ssh_server_port = 22
        self.ssh_credentials = os.environ.get('CRED_FILE', '')
        self.hname = None
        # TO-DO
        # rename logger -> inject_logger
        # error_logger -> logger
        # to be in same naming convention as everywhere else
        self.error_logger = logging.getLogger("mcm_error")
        self.logger = InjectionLogAdapter(logging.getLogger("mcm_inject"), {'handle': prepid})
        self.__build_ssh_client()

    def __enter__(self):
        return self

    def __exit__(self, t, value, traceback):
        self.close_executor()

    def __build_ssh_client(self):
        self.ssh_client = paramiko.SSHClient()
        # paramiko.util.log_to_file(self.__ssh_logfile, 10)
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        us, pw = self.__get_ssh_credentials()

        if not us:
            self.logger.error('Credentials could not be retrieved. Reason: username was None')
            raise paramiko.AuthenticationException('Credentials could not be retrieved.')

        try:
            time.sleep(2 * random.randrange(8))
            self.ssh_client.connect(self.ssh_server, port=self.ssh_server_port, username=us, password=pw)
        except paramiko.AuthenticationException as ex:
            self.logger.error('Could not authenticate to remote server "%s:%d". Reason: %s' % (self.ssh_server, self.ssh_server_port, ex))
            return
        except paramiko.BadHostKeyException as ex:
            self.logger.error('Host key was invalid. Reason: %s' % ex)
            return
        except paramiko.SSHException as ex:
            self.logger.error('There was a problem with the SSH connection. Reason: %s' % ex)
            return
        except Exception as ex:
            self.logger.error('Could not allocate socket for SSH. Reason: %s' % ex)
            return

    def __get_ssh_credentials(self):
        try:
            f = open(self.ssh_credentials, 'r')
            data = f.readlines()
            f.close()
        except IOError as ex:
            self.error_logger.error('Could not access credential file. IOError: %s' % ex)
            return None, None

        username, password = None, None
        for line in data:
            if 'username:' in line:
                toks = line.split(':')
                if len(toks) < 2:
                    self.logger.error('Username was None')
                    raise paramiko.AuthenticationException('Username not found.')
                username = toks[1].strip()
            elif 'password' in line:
                toks = line.split(':')
                if len(toks) < 2:
                    self.logger.error('Password was None')
                    raise paramiko.AuthenticationException('Password not found.')
                password = toks[1].strip()

        return username, password

    def __remote_exec(self, cmd=''):
        if not cmd:
            return None, None, None
        retry = 1
        retries = 2
        while True:
            try:
                with self.semaph:
                    return self.ssh_client.exec_command(cmd)
            except paramiko.SSHException as ex:
                self.logger.error('Could not execute remote command. Reason: %s' % ex)
                return None, None, None
            except AttributeError as ex:
                self.logger.error('There was an AttributeError inside the paramiko during try nr %s. Error: %s ' % (retry, ex))
                retry += 1
                if retry > retries:
                    self.logger.error('Attribute error two times. Returning nothing.')
                    return None, None, None

    def execute(self, cmd):
        stdin, stdout, stderr = self.__remote_exec(cmd)
        return stdin, stdout, stderr

    def close_executor(self):
        self.ssh_client.close()
