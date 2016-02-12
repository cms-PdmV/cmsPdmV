import time
import os
import socket
import errno
import logging

from tools.ssh_executor import ssh_executor
from tools.locator import locator
from tools.settings import settings

class batch_control:
    """
    a class to which is passed a script for batch testing and provides monitoring and logging
    and success status
    """
    logger = logging.getLogger("mcm_error")
    hname = '' # handler's name
    group = 'no-group'

    def __init__(self, test_id, test_script, timeout=None, memory=None):
        self.script_for_test = test_script
        self.test_id = test_id
        self.test_err = os.path.abspath( self.script_for_test + '.err')
        self.test_out = os.path.abspath( self.script_for_test + '.out')
        locat = locator()
        if locat.isDev():
            self.group = '/dev'
        else:
            self.group = '/prod'
        self.directory_for_test = os.path.dirname(self.script_for_test)
        self.log_out = 'Not available'
        self.log_err = 'Not available'
        try:
            self.ssh_exec = ssh_executor(self.directory_for_test, self.test_id)
        except Exception as e:
            self.ssh_exec = None
            self.log_err = str(e)

        self.timeout = int(settings().get_value('batch_timeout'))
        self.queue = '8nh'
        if timeout:
            self.timeout = int(timeout / 60.)
        if (self.timeout / 3600. ) > 8.:
            self.queue = '1nd' ## fall back to the one day queue at worse
        if memory:
            self.test_max_mem = memory*1000 ##we convert from MB to KB for batch

    def check_ssh_outputs(self, stdin, stdout, stderr, fail_message):
        if not stdin and not stdout and not stderr:
            self.log_err = fail_message
            self.logger.error(fail_message)
            return False
        return True

    def build_batch_command(self):
        cmd = 'bsub -J ' + self.test_id
        cmd += ' -g ' + self.group
        cmd += ' -q ' + self.queue
        cmd += ' -cwd ' + self.directory_for_test
        if self.timeout:
            cmd += ' -W %s'%  self.timeout
        cmd += ' -eo ' + self.test_err
        cmd += ' -oo ' + self.test_out
        cmd += ' -M ' + str(self.test_max_mem)
        cmd += ' bash ' + os.path.abspath(self.script_for_test)
        return cmd

    def batch_submit(self):
        cmd = self.build_batch_command()
        if not cmd:
            return False

        self.logger.info('submission command: \n%s' % cmd)

        stdin,  stdout,  stderr = self.ssh_exec.execute(cmd)

        if not self.check_ssh_outputs(stdin, stdout, stderr,
                "There was a problem with SSH remote execution of command:\n{0}!".format(cmd)): return False

        self.logger.info(stdout.read())
        errors = stderr.read()
        self.logger.info('SSH remote execution stderr stream: \n%s' % (errors))
        if 'Job not submitted' in errors:
            self.log_err = errors
            return False

        return True

    def monitor_job_status(self):

        cmd = 'bjobs -w -J %s -g %s' % (self.test_id, self.group)
        stdin, stdout, stderr = self.ssh_exec.execute(cmd)
        if not self.check_ssh_outputs(stdin, stdout, stderr,
                "Problem with SSH execution of command bjobs -w -J %s -g %s" % (self.test_id,
                        self.group)): return False

        for line in [l for l in stdout.read().split('\n') if self.test_id in l]:
            jid = line.split()[0]
            self.logger.info(self.get_job_percentage(jid))
            return False

        return True

    def get_job_percentage(self, jobid):

        cmd = 'bjobs -WP -J %s -g %s' % (self.test_id, self.group)
        stdin,  stdout,  stderr = self.ssh_exec.execute(cmd)

        if not stdin and not stdout and not stderr:
            self.log_err = 'SSH execution problem with command bjobs -WP -J %s -g %s' % (
                    self.test_id, self.group)

            return 'SSH execution problem with command bjobs -WP -J %s -g %s' % (self.test_id, self.group)

        for line in [l for l in stdout.read().split('\n') if jobid in l]:
            return '<job %s monitor hearbeat> job completion: %s' % (self.test_id,
                    line.strip().rsplit(' ')[-2])

        return 'Not found the percentage for %s job' % jobid

    def get_job_result(self):
        cmd = 'cat %s' % self.test_out

        stdin, stdout, stderr = self.ssh_exec.execute(cmd)
        self.logger.info("Reading file with command %s" % cmd)
        time_out=settings().get_value('batch_retry_timeout')
        out=""
        err=""
        if stdout:
            out=stdout.read()
            err=stderr.read()

        trials_time_out=10
        trials=0
        ## wait for afs to synchronize the output file
        while ((not stdin and not stdout and not stderr) or err) and trials < trials_time_out:
            time.sleep(time_out)
            trials+=1
            self.logger.info('Trying to get %s for the %s time' % (self.test_out, trials+1))
            stdin, stdout, stderr = self.ssh_exec.execute(cmd)
            if stdout:
                out=stdout.read()
                err=stderr.read()

        if trials >= trials_time_out:
            self.log_err = '%s could not be retrieved after %s tries in interval of %s s' % (
                    self.test_out, trials, time_out)

            self.logger.error(self.log_err)
            return False

        for line in out.split('\n'):
            if 'Successfully completed.' in line:
                return True
            elif 'Exited with' in line:
                # self.logger.error('workflow batch test returned: %s' % (line))
                self.log_out = out

                cmd = 'cat %s' % self.test_err
                stdin, stdout, stderr = self.ssh_exec.execute(cmd)
                if not self.check_ssh_outputs(stdin, stdout, stderr,
                        'Could not read the error log file: %s' % self.test_err): return False

                self.log_err = stdout.read()
                return False

        self.log_out = "We could get %s, but it does not look properly formatted. \n %s" % (
                self.test_out, out)

        self.log_err = stderr.read()
        return False

    def test(self):
        if not self.ssh_exec:
            return False
        try:
            ## send the test in batch
            if not self.batch_submit():
                return False

            timeout_counter = 0
            ## check when it is finished
            finished = False
            while not finished:
                try:
                    finished = self.monitor_job_status()
                    timeout_counter = 0
                except socket.error as e:
                    if e.errno == errno.ETIMEDOUT:
                        timeout_counter += 1
                        if timeout_counter > 2:
                            return False
                    else:
                        raise e
                time.sleep( settings().get_value('batch_retry_timeout') )

            ## check that it succeeded
            #wait for afs to sync the .out file
            result = self.get_job_result()

            if not result:
                return False

            ## and we are done
            return True
        finally:
            if self.ssh_exec:
                self.ssh_exec.close_executor()
