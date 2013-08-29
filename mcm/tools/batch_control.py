import paramiko
import time
import os
import re

import logging
from tools.logger import logger as logfactory, prep2_formatter
from tools.ssh_executor import ssh_executor
from tools.locator import locator

class batch_control:
    """
    a class to which is passed a script for batch testing and provides monitoring and logging, and success status
    """
    logger = logfactory('mcm')
    hname = '' # handler's name
    group = 'no-group'
    timeout = 80 # in minutes
        
    def __init__(self, test_id, test_script):
        self.script_for_test = test_script
        self.test_id = test_id
        locat = locator()
        if locat.isDev():
            self.test_id += '-dev'
            self.group = '/dev'
        else:
            self.group = '/prod'
        self.directory_for_test = self.script_for_test.rsplit('/',1)[0] +'/'
        self.ssh_exec = ssh_executor(self.directory_for_test, self.test_id)

        self.log_out = 'Not available'
        self.log_err = 'Not available'
        
    def build_batch_command(self):
            
        cmd = 'bsub -J ' + self.test_id
        cmd += ' -g ' + self.group
        cmd += ' -R "type=SLC5_64" ' # on slc5 nodes
        #cmd += '-M 3000000 ' # 3G of mem
        cmd += ' -q 8nh -cwd ' + self.directory_for_test
        if self.timeout:
            cmd += ' -W %s'% ( self.timeout )
        self.test_err = os.path.abspath( self.script_for_test + '.err')
        self.test_out = os.path.abspath( self.script_for_test + '.out')
        cmd += ' -eo ' + self.test_err
        cmd += ' -oo ' + self.test_out
        cmd += ' bash ' + os.path.abspath( self.script_for_test )
        
        return cmd
    
    def batch_submit(self):
        cmd = self.build_batch_command()
        if not cmd:
            return False

        self.logger.log('submission command: \n%s' % (cmd))
        
        stdin,  stdout,  stderr = self.ssh_exec.execute(cmd)
        
        if not stdin and not stdout and not stderr:
            self.log_out = stdout.read()
            self.log_err = stderr.read()
            return False
        
        self.logger.log(stdout.read())
        self.logger.log('SSH remote execution stderr stream: \n%s' % (stderr.read()))
        
        return True
    
    def monitor_job_status(self):
        
        cmd = 'bjobs -w'
        
        stdin,  stdout,  stderr = self.ssh_exec.execute(cmd)
        
        if not stdin and not stdout and not stderr:
            return False
            
        for line in stdout.read().split('\n'):
            if self.test_id in line:
                jid = line.split()[0]
                self.logger.log(self.get_job_percentage(jid))
                return False
        
        return True

    def get_job_percentage(self, jobid):

        cmd = 'bjobs -WP'
        stdin,  stdout,  stderr = self.ssh_exec.execute(cmd)

        if not stdin and not stdout and not stderr:
            return 'Not found'

        for line in stdout.read().split('\n'):
            if jobid in line:
                return '<job monitor hearbeat> job completion: %s' % (line.strip().rsplit(' ')[-2])

        return ''

    def get_job_result(self):
        cmd = 'cat %s' % ( self.test_out )
        
        stdin, stdout, stderr = self.ssh_exec.execute(cmd)

        if not stdin and not stdout and not stderr:
            return False

        out = stdout.read()
        for line in out.split('/n'):
            if 'Successfully completed.' in line:
                return True
            elif 'Exited with' in line:
                # self.logger.error('workflow batch test returned: %s' % (line))
                self.log_out = out
                
                cmd = 'cat %s' % ( self.test_err )
                stdin, stdout, stderr = self.ssh_exec.execute(cmd)
                if not stdin and not stdout and not stderr:
                    self.log_err = 'Could not be retrieved %s' %( stderr.read())
                    return False
                self.log_err = stdout.read()
                return False

        return None

    """
    def __read_job_log_file(self):
        for log in self.configurationLogFiles:
            stdin, stdout, stderr = self.__remote_exec('cat %s'%(log))
            if not stdin and not stdout and not stderr:
                continue
            data = stdout.read()
            if data.strip():
                self.job_log_when_failed = data
                self.logger.inject('Configuration test %s log: \n %s'%(log,data))
                
    def __read_job_error(self,extension='.err'):
        stdin, stdout, stderr = self.__remote_exec('cat %s%s' % (self.directory + self.request.get_attribute('prepid'),extension))

        if not stdin and not stdout and not stderr:
            return

        data = stdout.read()
        if data.strip():
	    self.logger.inject('Job %s file dump: \n%s' % (extension,data), level='error', handler=self.hname)

    """
    def test(self):
        
        ## send the test in batch
        submit_flag = self.batch_submit()
        if not submit_flag:
            return False
        
        ## check when it is finished
        while not self.monitor_job_status():
            time.sleep(60)
            
        ## check that it succeeded
        #wait for afs to sync the .out file
        time.sleep(30)
        result = self.get_job_result()
        self.ssh_exec.close_executor()
        if not result:
            return False

        ## and we are done
        return True
