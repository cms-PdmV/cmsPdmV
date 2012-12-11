import paramiko
import time
import os
import re

class package_tester:
    def __init__(self,  request_object,  directory='/afs/cern.ch/work/n/nnazirid/public/prep2_submit_area/',  pyconfigs=[]):
        self.request = request_object
        
        if not self.request:
            raise NoneTypeException('Request object passed was None.')
        
        self.directory = directory
        self.__check_directory()
        
        self.pyconfigs = pyconfigs
        
        if not self.pyconfigs:
            return
        
        self.ssh_client = None
        self.ssh_server = 'lxplus.cern.ch'
        self.ssh_server_port = 22
        self.ssh_credentials = '/afs/cern.ch/user/n/nnazirid/private/credentials'
        
        self.__build_ssh_client()
    
    def __check_directory(self):
        
        # check if directory is empty
        if not self.directory:
            self.directory = '/afs/cern.ch/work/n/nnazirid/public/prep2_submit_area/'
        
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
            
    def build_submit_script(self):
        infile = ''
        infile += '#!/bin/bash\n'
        infile += 'export SCRAM_ARCH=slc5_amd64_gcc434\n'
        infile += 'export myrel=' + self.request.get_attribute('cmssw_release') + '\n'
        infile += 'rel=`echo $myrel | sed -e "s/CMSSW_//g" | sed -e "s/_patch.*//g" | awk -F _ \'{print $1$2$3}\'`\n'
        infile += 'if [ $rel -gt 505 ]; then\n'
        infile += '  export SCRAM_ARCH=slc5_amd64_gcc462\n'
        infile += '  echo $SCRAM_ARCH\n'
        infile += 'fi\n'
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
            print 'Could not create testing script. Reason: '+str(ex)
            return False
        except Exception as ex:
            print 'Error: Could not create testing script. Reason: '+str(ex)
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
        
        stdin,  stdout,  stderr = self.__remote_exec(cmd)
        
        if not stdin and not stdout and not stderr:
            return False
        
        print stdout.read()
        
        return True
    
    def monitor_job_status(self):
        print '\t[Job Monitor Heartbeat]'
        
        cmd = 'bjobs -w'
        
        stdin,  stdout,  stderr = self.__remote_exec(cmd)
        
        if not stdin and not stdout and not stderr:
            return False
            
        data = stdout.read()
        lines = re.split(r'(\n+)', data)
        
        for line in lines:
            if self.request.get_attribute('prepid') in line:
                return False
        
        return True

    def get_job_result(self):
        try:
            log = open(self.directory + self.request.get_attribute('prepid') + '.out', 'r')
            
            for line in log.readlines():
                if 'Successfully completed.' in line:
                    return True
                elif 'Exited with exit code' in line:
                    return False
            log.close()
        except Exception as e:
            print 'Status Log Error: ' + str(e)
            return None

    def test(self):
        if not self.ssh_client:
            raise NoneTypeError('SSH Client was not initialized. Aborting...')
        
        submit_flag = self.batch_submit()
        
        if not submit_flag:
            return False
        
        
        while not self.monitor_job_status():
            time.sleep(5)
            
        result = self.get_job_result()
        
        if not result:
            return False
            
        return True
