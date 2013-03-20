import paramiko
import time
import os
import re

import logging
from tools.logger import logger as logfactory, prep2_formatter

class package_tester:
    logger = logfactory('prep2')
    hname = '' # handler's name

    def __init__(self,  request_object,  directory='/afs/cern.ch/cms/PPD/PdmV/tools/prep2/prep2_submit_area/',  pyconfigs=[]):
        self.request = request_object
        
        if not self.request:
            raise NoneTypeException('Request object passed was None.')

        self.directory = directory
        self.__check_directory()

	self.hname = self.request.get_attribute('prepid')
        self.__build_logger()
        
        self.pyconfigs = pyconfigs
        
        if not self.pyconfigs:
            return
        
        self.ssh_client = None
        self.ssh_server = 'lxplus.cern.ch'#'pdmvserv-test.cern.ch'
        self.ssh_server_port = 22
        self.ssh_credentials = '/afs/cern.ch/user/p/pdmvserv/private/credentials'#'/afs/cern.ch/user/n/nnazirid/private/credentials'

        self.scram_arch = None
        self.__build_ssh_client()

    def __build_logger(self):

        # define logger
        #logger = logging.getLogger('prep2_inject')

        # define .log file
        self.__logfile = self.directory + self.request.get_attribute('prepid') + '.log'

            #self.logger.setLevel(1)

            # main stream handler using the stderr
            #mh = logging.StreamHandler()
            #mh.setLevel((6 - self.__verbose) * 10) # reverse verbosity

            # filename handler outputting to log
        fh = logging.FileHandler(self.__logfile)
        fh.setLevel(logging.DEBUG) # log filename is most verbose

            # format logs
            #formatter = logging.Formatter("%(levelname)s - %(asctime)s - %(message)s")
            #mw.setFormatter(formatter)
        fh.setFormatter(prep2_formatter())

            # add handlers to main logger - good to go
        self.hname = self.request.get_attribute('prepid')
        self.logger.add_inject_handler(name=self.hname, handler=fh)
            #self.logger.addHandler(mh)

        #self.logger.inject('full debugging information in ' + repr(self.__logfile), handler=self.hname)

    
    def __check_directory(self):
        
        # check if directory is empty
        if not self.directory:
            self.directory = '/afs/cern.ch/cms/PPD/PdmV/tools/prep2/prep2_submit_area/'#'/afs/cern.ch/work/n/nnazirid/public/prep2_submit_area/'
        
        self.directory = os.path.abspath(self.directory) + '/' + self.request.get_attribute('prepid') + '/'
        
        # check if exists (and force)
        if os.path.exists(self.directory):
            return
            
        # recursively create any needed parents and the dir itself
        os.makedirs(self.directory)
    
    def __build_ssh_client(self):
        self.ssh_client = paramiko.SSHClient()
        paramiko.util.log_to_file(self.directory + self.request.get_attribute('prepid')+'_ssh_.log', 10) 
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #self.ssh_client.load_host_keys(os.path.expanduser(os.path.join('/afs/cern.ch/user/n/nnazirid/', ".ssh", "known_hosts")))
        
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
        except SSHException as ex:
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
            self.logger.inject('Could not access credential file. IOError: %s' % (ex), level='error', handler=self.hname)
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
        try:
            return self.ssh_client.exec_command(cmd)
        except SSHException as ex:
            self.logger.inject('Could not execute remote command. Reason: %s' % (ex), level='error', handler=self.hname)
            return None,  None,  None
            
    def build_submit_script(self):
        infile = ''
        infile += '#!/bin/bash\n'
        #infile += 'export SCRAM_ARCH=slc5_amd64_gcc434\n'
        #infile += 'export myrel=' + self.request.get_attribute('cmssw_release') + '\n'
        #infile += 'rel=`echo $myrel | sed -e "s/CMSSW_//g" | sed -e "s/_patch.*//g" | awk -F _ \'{print $1$2$3}\'`\n'
        #infile += 'if [ $rel -gt 505 ]; then\n'
        #infile += '  export SCRAM_ARCH=slc5_amd64_gcc462\n'
        #infile += '  echo $SCRAM_ARCH\n'
        #infile += 'fi\n'
        infile += 'export SCRAM_ARCH=%s\n'%(self.scram_arch)
        infile += 'scram p CMSSW ' + self.request.get_attribute('cmssw_release') + '\n'
        infile += 'cd ' + self.request.get_attribute('cmssw_release') + '\n'
        infile += 'eval `scram runtime -sh`\n'
        infile += 'cd ../\n'
        
        for step in self.pyconfigs:
            logname = os.path.abspath(self.directory + os.path.pardir+ '/' + step + ".log")
            infile += "cmsRun " + os.path.abspath(self.directory + os.path.pardir + '/' + step) + " &> " + logname
            infile += ' || exit $? ;\n'
        
        try:
            script = open(self.directory+'run_test.sh',  'w')
            script.write(infile)
            script.close()
            os.chmod(self.directory + 'run_test.sh', 0755)
        except IOError as ex:
            self.logger.inject('Could not create testing script. Reason: %s' % (ex), level='error', handler=self.hname)
            return False
        except Exception as ex:
            self.logger.inject('Could not create testing script. Reason: %s' % (ex), level='error', handler=self.hname)
            return False
        
        return True
    
    def build_test_command(self):
        if not self.build_submit_script():
            return None
            
        cmd = 'bsub -J ' + self.request.get_attribute('prepid') 
        cmd += ' -q 8nh -W 40 -cwd ' + self.directory 
        cmd += ' -eo ' + os.path.abspath(self.directory + self.request.get_attribute('prepid') + '.err') 
        cmd += ' -oo ' + os.path.abspath(self.directory + self.request.get_attribute('prepid') + '.out') 
        cmd += ' bash ' + os.path.abspath(self.directory + 'run_test.sh')
        
        return cmd
    
    def batch_submit(self):
        cmd = self.build_test_command()
        if not cmd:
            return False

        self.logger.inject('submission command: %s' % (cmd), level='debug', handler=self.hname)
        
        stdin,  stdout,  stderr = self.__remote_exec(cmd)
        
        if not stdin and not stdout and not stderr:
            return False
        
        self.logger.inject(stdout.read(), handler=self.hname)
        self.logger.inject('SSH remote execution stderr stream: "%s"' % (stderr.read()), handler=self.hname, level='debug')
        
        return True
    
    def monitor_job_status(self):
        #print '\t[Job Monitor Heartbeat]'
        
        cmd = 'bjobs -w'
        
        stdin,  stdout,  stderr = self.__remote_exec(cmd)
        
        if not stdin and not stdout and not stderr:
            return False
            
        data = stdout.read()
        lines = re.split(r'(\n+)', data)
        
        for line in lines:
            if self.request.get_attribute('prepid') in line:
                jid = line[:line.index(' ')]
                self.logger.inject(self.__get_job_percentage(jid), level='debug', handler=self.hname)
                
                return False
        
        return True

    def __get_job_percentage(self, jobid=''):
        if not jobid:
            return ''

        cmd = 'bjobs -WP'
        stdin,  stdout,  stderr = self.__remote_exec(cmd)

        if not stdin and not stdout and not stderr:
            return False

        data = stdout.read()
        lines = re.split(r'(\n+)', data)

        for line in lines:
            if jobid in line:
                return '<job monitor hearbeat> job completion: %s' % (line.strip().rsplit(' ')[-2])

        return ''

    def get_job_result(self):
        stdin, stdout, stderr = self.__remote_exec('cat %s.out' % (self.directory + self.request.get_attribute('prepid')))

        if not stdin and not stdout and not stderr:
            return False

        data = stdout.read()
        lines = re.split(r'(\n+)', data)

        for line in lines:
            if 'Successfully completed.' in line:
                return True
            elif 'Exited with ' in line:
                self.logger.inject('workflow batch test returned: %s' % (line), level='error', handler=self.hname)
                self.__read_job_error()
                return False

        self.logger.inject('Could not obtain status from logfile "%s.out". Error stream dump: %s' % (self.directory + self.request.get_attribute('prepid'), stderr.read()), level='error', handler=self.hname)
        return None

    def __read_job_error(self):
        stdin, stdout, stderr = self.__remote_exec('cat %s.err' % (self.directory + self.request.get_attribute('prepid')))

        if not stdin and not stdout and not stderr:
            return

        data = stdout.read()
        if data.strip():
	    self.logger.inject('job error dump: %s' % (data), level='error', handler=self.hname)

#    def get_job_resulta(self):
#        try:
#            log = open(self.directory + self.request.get_attribute('prepid') + '.out', 'r')
#            
#            for line in log.readlines():
#                if 'Successfully completed.' in line:
#                    return True
#                elif 'Exited with exit code' in line:
#                    return False
#            log.close()
#        except Exception as e:
#            self.logger.inject('Status error: %s' % (e), level='error', handler=self.hname)
#            return None

    def test(self):
        if not self.ssh_client:
            self.logger.inject('SSH Client was not initialized. Aborting...', level='error', handler=self.hname)
            raise NoneTypeError('SSH Client was not initialized. Aborting...')
        
        submit_flag = self.batch_submit()
        
        if not submit_flag:
            return False
        
        
        while not self.monitor_job_status():
            time.sleep(10)
            
        result = self.get_job_result()
        
        if not result:
            return False
            
        return True
