import paramiko
import time
import os
import re

import logging
from tools.logger import logger as logfactory, prep2_formatter
from tools.ssh_executor import ssh_executor
from tools.locator import locator


class package_tester:
    logger = logfactory('mcm')
    hname = '' # handler's name
    group = ''

    def __init__(self, request_object, directory=None, pyconfigs=[]):
        l_type = locator()
        if not directory:
            directory = l_type.workLocation()
        self.request = request_object
        self.configurationLogFiles = []

        if not self.request:
            raise NoneTypeException('Request object passed was None.')

        self.directory = directory
        self.__check_directory()

        self.job_log_when_failed = 'No log available'

        self.hname = self.request.get_attribute('prepid')
        if l_type.isDev():
            self.hname += "-dev"
            self.group = "/dev"
        else:
            self.group = "/prod"
        self.__build_logger()

        self.pyconfigs = pyconfigs

        if not self.pyconfigs:
            return
        self.ssh_exec = ssh_executor(directory, self.hname)

        self.scram_arch = None

    def __build_logger(self):


        # define .log file
        self.__logfile = self.directory + self.hname + '.log'

        # filename handler outputting to log
        fh = logging.FileHandler(self.__logfile)
        fh.setLevel(logging.DEBUG) # log filename is most verbose

        # format logs
        fh.setFormatter(prep2_formatter())

        # add handlers to main logger - good to go
        self.logger.add_inject_handler(name=self.hname, handler=fh)
        #self.logger.addHandler(mh)


    def __check_directory(self):

        if not self.directory.endswith('/'):
            self.directory += '/'

        # check if exists (and force)
        if os.path.exists(self.directory):
            return

    def __remote_exec(self, cmd=''):
        #s giving that away to ssh executor
        return self.ssh_exec.execute(cmd)

    def build_submit_script(self):
        infile = ''
        infile += '#!/bin/bash\n'
        infile += 'export SCRAM_ARCH=%s\n' % (self.scram_arch)
        infile += 'scram p CMSSW ' + self.request.get_attribute('cmssw_release') + '\n'
        infile += 'cd ' + self.request.get_attribute('cmssw_release') + '\n'
        infile += 'eval `scram runtime -sh`\n'
        infile += 'cd ../\n'

        for step in self.pyconfigs:
            #logname = os.path.abspath(self.directory + os.path.pardir+ '/' + step + ".log")
            #infile += "cmsRun " + os.path.abspath(self.directory + os.path.pardir + '/' + step) + " &> " + logname
            logname = os.path.abspath(self.directory + step + ".log")
            infile += "cmsRun " + os.path.abspath(self.directory + step) + " &> " + logname
            infile += ' || exit $? ;\n'
            self.configurationLogFiles.append(logname)

        if self.request.genvalid_driver:
            infile += self.request.harverting_upload

        try:
            script = open(self.directory + 'run_test.sh', 'w')
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
        cmd = 'bsub -J ' + self.hname
        cmd += ' -g ' + self.group
        cmd += ' -q 8nh -W 100 -cwd ' + self.directory
        cmd += ' -eo ' + os.path.abspath(self.directory + self.hname + '.err')
        cmd += ' -oo ' + os.path.abspath(self.directory + self.hname + '.out')
        cmd += ' bash ' + os.path.abspath(self.directory + 'run_test.sh')

        return cmd

    def batch_submit(self):
        cmd = self.build_test_command()
        if not cmd:
            return False

        self.logger.inject('submission command: \n%s' % (cmd), level='debug', handler=self.hname)

        stdin, stdout, stderr = self.__remote_exec(cmd)

        if not stdin and not stdout and not stderr:
            return False

        self.logger.log("CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCc")
        self.logger.inject(stdout.read(), handler=self.hname)
        self.logger.inject('SSH remote execution stderr stream: \n%s' % (stderr.read()), handler=self.hname,
                           level='debug')

        return True

    def monitor_job_status(self):
        #print '\t[Job Monitor Heartbeat]'

        cmd = 'bjobs -w'

        stdin, stdout, stderr = self.__remote_exec(cmd)

        if not stdin and not stdout and not stderr:
            return False

        data = stdout.read()
        lines = re.split(r'(\n+)', data)

        for line in lines:
            if self.hname in line:
                jid = line[:line.index(' ')]
                self.logger.inject(self.__get_job_percentage(jid), level='debug', handler=self.hname)

                return False

        return True

    def __get_job_percentage(self, jobid=''):
        if not jobid:
            return ''

        cmd = 'bjobs -WP'
        stdin, stdout, stderr = self.__remote_exec(cmd)

        if not stdin and not stdout and not stderr:
            return False

        data = stdout.read()
        lines = re.split(r'(\n+)', data)

        for line in lines:
            if jobid in line:
                return '<job monitor hearbeat> job completion: %s' % (line.strip().rsplit(' ')[-2])

        return ''

    def get_job_result(self):
        stdin, stdout, stderr = self.__remote_exec(
            'cat %s.out' % (self.directory + self.hname))

        if not stdin and not stdout and not stderr:
            return False

        data = stdout.read()
        lines = data.split('\n')
        #JR lines = re.split(r'(\n+)', data)

        for line in lines:
            if 'Successfully completed.' in line:
                return True
            elif 'Exited with ' in line:
                self.logger.inject('workflow batch test returned: %s' % (line), level='error', handler=self.hname)
                #self.__read_job_error('.out')
                self.__read_job_error()
                self.__read_job_log_file()
                return False

        self.logger.inject('Could not obtain status from logfile "%s.out". Error stream dump: %s' % (
            self.directory + self.hname, stderr.read()), level='error', handler=self.hname)
        return None

    def __read_job_log_file(self):
        for log in self.configurationLogFiles:
            stdin, stdout, stderr = self.__remote_exec('cat %s' % (log))
            if not stdin and not stdout and not stderr:
                continue
            data = stdout.read()
            if data.strip():
                self.job_log_when_failed = data
                self.logger.inject('Configuration test %s log: \n %s' % (log, data))

    def __read_job_error(self, extension='.err'):
        stdin, stdout, stderr = self.__remote_exec(
            'cat %s%s' % (self.directory + self.hname, extension))

        if not stdin and not stdout and not stderr:
            return

        data = stdout.read()
        if data.strip():
            self.logger.inject('Job %s file dump: \n%s' % (extension, data), level='error', handler=self.hname)

    def test(self):
        #if not self.ssh_client:
        if not self.ssh_exec:
            self.logger.inject('SSH Client was not initialized. Aborting...', level='error', handler=self.hname)
            raise NoneTypeError('SSH Client was not initialized. Aborting...')

        submit_flag = self.batch_submit()

        if not submit_flag:
            return False

        while not self.monitor_job_status():
            time.sleep(30)

        #wait for afs to sync the .out file
        time.sleep(10)
        result = self.get_job_result()

        if not result:
            return False

        return True
