import paramiko
import os

class package_injector:
    def __init__(self,  tarball,  cmssw_release, directory='/afs/cern.ch/work/n/nnazirid/public/prep2_submit_area/',  batch=10):
        self.tarball = str(tarball)
        self.directory = str(directory)
        self.cmssw_release = str(cmssw_release)
        self.batch = str(batch)

        self.ssh_client = None
        self.ssh_server = 'lxplus.cern.ch'
        self.ssh_server_port = 22
        self.ssh_credentials = '/afs/cern.ch/user/n/nnazirid/private/credentials'

        self.__build_ssh_client()

    def build_injection_script(self):
        script = ''
        script += 'cd '+self.directory + '\n'
        script += 'source /afs/cern.ch/project/gd/LCG-share/current_3.2/etc/profile.d/grid_env.sh\n'
        script += 'voms-proxy-init --debug\n'
        script += 'cd SubmissionTools/\n'
        script += 'sh wmcontrol2_injection_procedure.sh '+self.directory+'/'+self.tarball+' '+self.cmssw_release+' nnazirid PREP '+self.batch +'\n'
        
        try:
            f = open(self.directory+'inject-'+self.tarball+'.sh',  'w')
            f.write(script)
            f.close()
        except IOError as ex:
            print 'Error: Could not create injection script. Reason:'+str(ex)
            return False
        return True

    def __build_ssh_client(self):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.load_host_keys(os.path.expanduser(os.path.join('/afs/cern.ch/user/n/nnazirid/', ".ssh", "known_hosts")))

        us,  pw = self.__get_ssh_credentials()

        if not us:
            raise paramiko.AuthenticationException('Credentials could not be retrieved.')

        try:
            self.ssh_client.connect(self.ssh_server,  port=self.ssh_server_port,  username=us,  password=pw)
        except paramiko.AuthenticationException as ex:
            print 'Error: Could not authenticate to remote server '+self.ssh_server+':'+str(self.ssh_server_port)
            print 'Reason: '+str(ex)
            return
        except paramiko.BadHostKeyException as ex:
            print 'Error: Host Key was invalid. Reason: '+str(ex)
            return
        except SSHException as ex:
            print 'Error: There was a problem with the SSH connection. Reason: '+str(ex)
            return
        except SocketError  as ex:
            print 'Error: Could not allocate a socket. Reason: '+str(ex)
            return

    def __get_ssh_credentials(self):
        try:
            f = open(self.ssh_credentials,  'r')
            data = f.readlines()
            f.close()
        except IOError as ex:
            print str(ex)
            return None,  None

        username,  password = None,  None

        for line in data:
            if 'username:' in line:
                toks = line.split(':')
                if len(toks) < 2:
                    raise paramiko.AuthenticationException('Username not found.')
                username = toks[1].strip()
            elif 'password' in line:
                toks = line.split(':')
                if len(toks) < 2:
                    raise paramiko.AuthenticationException('Password not found.')
                password = toks[1].strip()

        return username,  password


    def __remote_exec(self,  cmd=''):
        if not cmd:
            return None,  None,  None
        try:
            return self.ssh_client.exec_command(cmd)
        except SSHException as ex:
            print 'Error: Could not execute remote command. Reason: '+str(ex)
            return None,  None,  None


    def inject(self):
        flag = self.build_injection_script()
        if not flag:
            return False

        stdin,  stdout,  stderr = self.__remote_exec('sh '+self.directory+'inject-'+self.tarball+'.sh')

        if not stdin and not stdout and not stderr:
            return False

        print 'Errors returned: ', stderr.read()

        print stdout.read()

        return True
