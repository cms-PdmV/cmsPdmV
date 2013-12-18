from RestAPIMethod import RESTResource
from tools.ssh_executor import ssh_executor
from tools.user_management import access_rights
from tools.settings import settings
from json import dumps


class RenewCertificate(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Renew certificate on pdmvserv-test.cern.ch
        """
        ssh_exec = ssh_executor(server='pdmvserv-test.cern.ch')
        try:
            self.logger.log("Renewing certificate")
            stdin, stdout, stderr = ssh_exec.execute(self.create_command())
            self.logger.log("Certificate renewed:\n{0}".format(stdout.read()))
        finally:
            ssh_exec.close_executor()

    def create_command(self):
            # crab setup
            command = 'source /afs/cern.ch/cms/LCG/LCG-2/UI/cms_ui_env.sh ; source /afs/cern.ch/cms/ccs/wm/scripts/Crab/crab.sh \n'
            # certificate
            command += 'cat /afs/cern.ch/user/p/pdmvserv/private/PdmVService.txt | voms-proxy-init -voms cms --valid 240:00 -pwstdin --key /afs/cern.ch/user/p/pdmvserv/private/$HOST/userkey.pem --cert /afs/cern.ch/user/p/pdmvserv/private/$HOST/usercert.pem --out /afs/cern.ch/user/p/pdmvserv/private/$HOST/voms_proxy.cert 2> /dev/null\n'
            return command