from tools.ssh_executor import ssh_executor


class stats_updater:
    def __init__(self, inspect=False, force=True):
        self.ssh = ssh_executor(server='vocms074.cern.ch')
        self.inspect = ""
        if inspect:
            self.inspect = '--inspect'
        self.force = ""
        if force:
            self.force = '--force'

    def update(self, arg):
        com = ''
        com += 'export X509_USER_PROXY=/afs/cern.ch/user/p/pdmvserv/private/$HOSTNAME/voms_proxy.cert\n'
        # com += 'cd /build/pdmvserv/CMSSW_5_3_14/ \n'
        # com += 'eval `scramv1 runtime -sh`'
        # com += 'cd /afs/cern.ch/cms/PPD/PdmV/tools/stats \n'
        com += 'cd /home/pdmvserv/stats \n'
        com += 'tools/driveUpdate.py --do update --search %s %s %s \n' % (arg, self.force, self.inspect)
        (_, stdout, stderr) = self.ssh.execute(com)
        return stdout.read()
