from tools.handler import handler
from tools.installer import installer
from tools.ssh_executor import ssh_executor
from tools.locator import locator
from os import path
from couchdb_layer.prep_database import database
from json_layer.request import request


class ConfigMakerAndUploader(handler):
    """
    Class preparing and uploading (if needed) the configuration and adding it for the given request
    """
    def __init__(self, **kwargs):
        handler.__init__(self, **kwargs)
        self.prepid = kwargs["prepid"]
        self.request_db = database("requests")
        self.config_db = database("configs")
        self.ssh_executor = ssh_executor(server='pdmvserv-test.cern.ch')

    @staticmethod
    def prepare_command(cfgs, directory, req, test_string):
        cmd = req.get_setup_file(directory)
        cmd += 'source /afs/cern.ch/cms/LCG/LCG-2/UI/cms_ui_env.sh ; source /afs/cern.ch/cms/ccs/wm/scripts/Crab/crab.sh\n'
        cmd += 'cat /afs/cern.ch/user/p/pdmvserv/private/PdmVService.txt | voms-proxy-init -voms cms --valid 240:00 -pwstdin --key /afs/cern.ch/user/p/pdmvserv/private/$HOST/userkey.pem --cert /afs/cern.ch/user/p/pdmvserv/private/$HOST/usercert.pem 2> /dev/null\n'
        cmd += 'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh\n'
        cmd += 'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n'
        cmd += "wmupload.py {1} -u pdmvserv -g ppd {0}".format(" ".join(cfgs), test_string)
        return cmd

    def internal_run(self):
        with self.lock:
            req = request(self.request_db.get(self.prepid))
            additional_config_ids = []
            cfgs_to_upload = []
            l_type = locator()
            dev=''
            wmtest=''
            if l_type.isDev():
                dev='-dev'
                wmtest = '--wmtest'
            if len(req.get_attribute('config_id')): # we already have configuration ids saved in our request
                return
            for i in range(len(req.get_attribute('sequences'))):
                hash_id = req.configuration_identifier(i)
                if self.config_db.document_exists(hash_id): # cached in db
                    additional_config_ids.append(self.config_db.get(hash_id)['docid'])
                else: # has to be setup and uploaded to config cache
                    cfgs_to_upload.append("{0}{1}_{2}_cfg.py".format(req.get_attribute('prepid'), dev, i+1))
            if len(cfgs_to_upload):
                directory_manager = installer(self.prepid, care_on_existing=False)
                try:
                    command = self.prepare_command(cfgs_to_upload, directory_manager.location(), req, wmtest)
                    _, stdout, stderr = self.ssh_executor.execute(command)
                    if not stdout and not stderr:
                        self.logger.error('ssh error for request {0}'.format(self.prepid))
                        req.test_failure('ssh error for request {0}'.format(self.prepid), what='Configuration upload')
                        return
                    output = stdout.read()
                    error = stderr.read()
                    if error: # money on the table that it will break
                        self.logger.error('Error in wmupload: {0}'.format(error))
                        req.test_failure(error, what='Configuration upload')
                        return
                    for line in output.split("\n"):
                        if 'DocID:' in line:
                            docid = line.split()[-1]
                            additional_config_ids.append(docid)
                    self.logger.log("Full upload result: {0}".format(output))
                finally:
                    directory_manager.close()

                self.logger.log("New configs for request {0} : {1}".format(self.prepid, additional_config_ids))
                req.set_attribute('config_id', additional_config_ids)
                self.request_db.save(req.json())




class Inject(handler):
    """
    Class injecting the configuration
    """
    def __init__(self, **kwargs):
        handler.__init__(self, **kwargs)
        self.prepid = kwargs["prepid"]
        self.architecture = kwargs["arch"] if kwargs.has_key("arch") else 'slc5_amd64_gcc462'
        self.cmssw_release = kwargs["cmssw_release"]
        self.directory_manager = installer(self.prepid, care_on_existing=False)
        self.directory = self.directory_manager.location()
        self.ssh_executor = ssh_executor(self.directory, self.prepid)

    def __write_script(self):
        script = ''
        script += 'cd ' + self.directory + '\n'
        script += 'source /afs/cern.ch/cms/LCG/LCG-2/UI/cms_ui_env.sh ; source /afs/cern.ch/cms/ccs/wm/scripts/Crab/crab.sh \n'
        script += 'cat /afs/cern.ch/user/p/pdmvserv/private/PdmVService.txt | voms-proxy-init -voms cms --valid 240:00 -pwstdin --key /afs/cern.ch/user/p/pdmvserv/private/$HOST/userkey.pem --cert /afs/cern.ch/user/p/pdmvserv/private/$HOST/usercert.pem\n'
        script += 'set -o verbose \n'
        script += 'export SCRAM_ARCH=%s \n' % self.architecture
        script += 'scram project CMSSW %s \n' % self.cmssw_release
        script += 'cd %s \n' % self.cmssw_release
        script += 'eval `scram runtime -sh` \n\n'
        script += 'cd ../\n'
        script += 'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh\n'
        script += 'cd %s \n ' % self.prepid
        script += 'ls -l \n'
        script += 'chmod 755 injectAndApprove.sh \n'
        script += 'grep wmcontrol injectAndApprove.sh \n'
        script += './injectAndApprove.sh \n'

        try:
            script_path = path.join(self.directory,'inject-' + self.prepid + '.sh')
            self.logger.inject('Writing injection script to ' + script_path)
            with open(script_path, 'w') as f:
                f.write(script)
        except IOError as ex:
            self.logger.inject('Could not create injection script. IOError: {0}'.format(ex), level='error',
                               handler=self.prepid)
            return False
        return True

    def internal_run(self):
        try:
            if not self.__write_script():
                return
            _, stdout, stderr = self.ssh_executor.execute('sh ' + path.join(self.directory,'inject-' + self.prepid + '.sh'))
            output = stdout.read()
            error = stderr.read()

            wmcontrol_exceptions = [exc for exc in error.split('\n') if '[wmcontrol exception]' in exc]
            if len(wmcontrol_exceptions):
                self.logger.inject('Executed \n %s' % output, handler=self.prepid, level='error')
                self.logger.inject('Errors returned: %s' % error, handler=self.prepid, level='error')
                self.res.append({"results": False, "message": "wmcontrol exceptions : \n %s \n in full log : \n %s" % (
                    '\n'.join(wmcontrol_exceptions), output)})
                return

            injected_names = []
            approved_names = []
            document_ids = []
            for line in output.split('\n'):
                split_line = line.split()
                if line.startswith('Injected workflow:'):
                    injected_names.append(split_line[2])
                if line.startswith('Approved workflow:'):
                    approved_names.append(split_line[2])
                if line.startswith('DocID: '):
                    self.logger.inject('A line of the output contains docid %s : %s' % (line, split_line), handler=self.prepid)
                    document_ids.append(split_line[-1])


            if not len(approved_names):
                self.res.append({"results": False, "message": 'There were no request manager name recorded \n %s \n\n\n %s' % (output, error)})
                if len(injected_names):
                    invalidation = database('invalidations')
                    for r_inject_but_not_approved in injected_names:
                        new_invalidation={"object" : r_inject_but_not_approved , "type" : "request", "status" : "new" , "prepid" : self.hname.replace('-dev','')}
                        new_invalidation['_id'] = new_invalidation['object']
                        invalidation.save( new_invalidation )
                return

            self.res.append({"results": True, "message": "Injection output: \n%s" % output})
            self.logger.inject('Injection output: %s' % output, handler=self.prepid)

        finally:
            self.ssh_executor.close_executor()
            self.directory_manager.close()