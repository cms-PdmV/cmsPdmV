import paramiko
import os

import logging
from tools.logger import prep2_formatter, logger as logfactory

class package_injector:
    logger = logfactory('prep2')
    hname = '' # name of the log handler

    def __init__(self,  tarball,  cmssw_release, directory='/afs/cern.ch/cms/PPD/PdmV/tools/prep2/prep2_submit_area/'):
        self.tarball = str(tarball)
        self.prepid = self.tarball.rsplit('.tgz')[0]
        self.directory = str(directory)
        if ":" in cmssw_release:
            self.cmssw_release,self.arch = map(str, cmssw_release.split(':'))
        else:
            self.cmssw_release=str(self.cmssw_release)
            self.arch = 'slc5_amd64_gcc462'

        self.ssh_client = None
        self.ssh_server = 'pdmvserv-test.cern.ch'#'lxplus.cern.ch'
        self.ssh_server_port = 22
        self.ssh_credentials = '/afs/cern.ch/user/p/pdmvserv/private/credentials'

        self.__build_ssh_client()
        self.__build_logger()


    def __build_logger(self):

        # define logger
        #logger = logging.getLogger('prep2_inject')

        # define .log file
        self.__logfile = self.directory + self.prepid + '.log'

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
        self.hname = self.prepid
        self.logger.add_inject_handler(name=self.hname, handler=fh)


    def build_injection_script(self):
        script = ''
        script += 'cd '+self.directory + '\n'
        script += 'source /afs/cern.ch/cms/LCG/LCG-2/UI/cms_ui_env.sh ; source /afs/cern.ch/cms/ccs/wm/scripts/Crab/crab.sh \n'
	script += 'cat /afs/cern.ch/user/p/pdmvserv/private/PdmVService.txt | voms-proxy-init -voms cms --valid 240:00 -pwstdin --key /afs/cern.ch/user/p/pdmvserv/private/$HOST/userkey.pem --cert /afs/cern.ch/user/p/pdmvserv/private/$HOST/usercert.pem\n'
        script += 'set -o verbose \n'
        script += 'export SCRAM_ARCH=%s \n'%(self.arch)
        script += 'scram project CMSSW %s \n'%(self.cmssw_release)
        script += 'cd %s \n'%(self.cmssw_release)
        script += 'eval `scram runtime -sh` \n\n'
        script += 'cd ../\n'
        script += 'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh\n'
        script += 'tar xvzf %s \n'%(self.tarball)
        script += 'cd %s \n '%(self.tarball.replace('.tgz',''))
        script += 'ls -l \n'
        script += 'chmod 755 injectAndApprove.sh \n'
        script += './injectAndApprove.sh \n'
        
        try:
            f = open(self.directory+'inject-'+self.tarball+'.sh',  'w')
            f.write(script)
            f.close()
        except IOError as ex:
            self.logger.inject('Could not create injection script. IOError: %s' % (ex), level='error', handler=self.hname)
            return False
        return True

    def __build_ssh_client(self):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #self.ssh_client.load_host_keys(os.path.expanduser(os.path.join('/afs/cern.ch/user/p/pdmvserv/', ".ssh", "known_hosts")))

        us,  pw = self.__get_ssh_credentials()

        if not us:
            self.logger.inject('Credentials for injection could not be retrieved.', level='error', handler=self.hname)
            raise paramiko.AuthenticationException('Credentials could not be retrieved.')

        try:
            self.ssh_client.connect(self.ssh_server,  port=self.ssh_server_port,  username=us,  password=pw)
        except paramiko.AuthenticationException as ex:
            self.logger.inject('Could not authenticate to remote server "%s:%d". Reason: %s' % (self.ssh_server, self.ssh_server_port, ex), level='error', handler=self.hname)
            return
        except paramiko.BadHostKeyException as ex:
            self.logger.inject('Host key is invalid. Reason: %s' % (ex), level='error', handler=self.hname)
            return
        except SSHException as ex:
            self.logger.inject('There was a problem with the SSH connection. Reason: %s' % (ex), level='error', handler=self.hname)
            return
        except SocketError  as ex:
            self.logger.inject('Could not allocate socket. Reason: %s' % (ex), level='error', handler=self.hname)
            return

    def __get_ssh_credentials(self):
        try:
            f = open(self.ssh_credentials,  'r')
            data = f.readlines()
            f.close()
        except IOError as ex:
            self.logger.inject('Could not retrieve the credentials for the injection. IOError: %s' % (ex), level='critical', handler=self.hname)
            return None,  None

        username,  password = None,  None

        for line in data:
            if 'username:' in line:
                toks = line.split(':')
                if len(toks) < 2:
                    self.logger.inject('Username is None', level='error', handler=self.hname)
                    raise paramiko.AuthenticationException('Username not found.')
                username = toks[1].strip()
            elif 'password' in line:
                toks = line.split(':')
                if len(toks) < 2:
                    self.logger.inject('Password is None', level='error', hanlder=self.hname)
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


    def inject(self):
        flag = self.build_injection_script()
        if not flag:
            return False


        stdin,  stdout,  stderr = self.__remote_exec('sh '+self.directory+'inject-'+self.tarball+'.sh')

        if not stdin and not stdout and not stderr:
            return False

        error = stderr.read()
        if error:
            self.logger.inject('Errors returned: %s' % (error), handler=self.hname, level='error')


        self.logger.inject('Injection output: %s' % (stdout.read()), handler=self.hname)

        return True
