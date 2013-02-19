import logging
import os
from submitter.class_tarball import tarball
from submitter.package_tester import package_tester
from submitter.package_injector import package_injector
import re
import subprocess
import math
import shutil
import cherrypy
import logging
from tools.logger import prep2_formatter, logger as logfactory
from json_layer.request import request

class package_builder:
	
    logger = logfactory('prep2')
    hname = '' # the name of the handler for the request to be injected

    class DataAlreadyExistsException(Exception):
        def __init__(self, directory=None):
            self.directory = directory
            if not self.directory:
                package_builder.logger.inject('Data directory already exists. Give --force option to overwrite.', level='error', handler=package_builder.hname)
            else:
                package_builder.logger.inject('Directory already exists. Give --force option to overwrite.', level='error', handler=package_builder.hname)

        def __str__(self):
            if not self.directory:
                return 'Error: Data directory already exists. Give --force option to overwrite.'
            return 'Error: Directory ' + str(self.directory) + ' already exists. Give --force option to overwrite'
 
    class NoValidRequestsDetectedException(Exception):
        def __init__(self):
            package_builder.logger.inject('Error: There were no valid requests in provided list', level='error', handler=package_builder.hname)

        def __str__(self):
            return 'Error: There were no valid requests in provided list'

    class NotInitializedException(Exception):
        def __init__(self,  msg=''):
            self.msg = str(msg)
            if self.msg:
                package_builder.logger.inject('Package is not initialized. Reason: %s' % (self.msg), level='error', handler=package_builder.hname)
            else:
                package_builder.logger.inject('Package is not initialized. ', level='error', handler=package_builder.hname)

        def __str__(self):
            if self.msg:
                return 'Error: Package is not initialized. Reason: '+self.msg
            return 'Error: Package is not initialized.'

    class NoStepsDetected(Exception):
        def __init__(self,  rid):
            self.rid = str(rid)
            package_builder.logger.inject(' no valid cmsDriver commands could be built for request "%s"' % (self.rid), level='error', handler=package_builder.hname)

        def __str__(self):
            return 'Error: no valid cmsDriver commands could be built for request "'+self.rid+'".'

    class NoneTypePackageNameException(Exception):
        def __init__(self):
            package_builder.logger.inject(' Package name given was NoneType', level='error', handler=package_builder.hname)

        def __str__(self):
            return 'Error: Package name given was NoneType'


    def __init__(self,  req_json=None,  directory='/afs/cern.ch/cms/PPD/PdmV/tools/prep2/prep2_submit_area/',  events=5):
        
        # set time out to 2000 seconds
        cherrypy.response.timeout = 2000
        
        # init request object
        try:
            self.request = request('',  json_input=req_json)
        except request.IllegalAttributeName:
            return

        self.__flags = []
        self.__tarobj = None
        self.closed = False
        self.__logfile = ''
        self.__verbose = 4

        # list of different production steps (represented as a different element in the request's "sequences" property)
        self.__cmsDrivers = []
        self.wmagent_type = ''
        self.__injection_command = ''
        self.__build_command = ''

        # reqmgr config cache specifics
        self.reqmgr_couchurl = "https://cmsweb.cern.ch/couchdb"
        self.reqmgr_database = "reqmgr_config_cache"
        self.reqmgr_user = "pdmvserv" # generic uname and pword
        self.reqmgr_group = "ppd" # to be updated on the fly later (no worries)

        # config files
        self.__summary = None
        self.__upload_configs = None
        self.__injectAndApprove = None
        self.__pyconfigs = []

        # There is a not-Initialized exception that is not handled
        self.directory = directory
        self.__check_directory() # check directory sanity

        # init logger
        #self.logger = None
        self.__build_logger()

        # initialize tarball
        self.tarball = None
        self.__init_tarball()

        # the number of events to be tested.
        # for generation requests, I need to take into consideration
        # the matching and filter efficiencies
        if self.request.get_attribute('generator_parameters'):
            match = float(self.request.get_attribute('generator_parameters')[-1]['match_efficiency'])
            filter = float(self.request.get_attribute('generator_parameters')[-1]['filter_efficiency'])
            if match > -1 and filter > -1:
                self.events = int(math.fabs(events / (match*filter)))
            else:
                self.events = int(math.fabs(events))
        else:
            self.events = math.fabs(int(events))

        # avoid large testing samples
        if self.events > 1000:
            self.events = 50

    # check and create all working directories
    def __check_directory(self):

        # check if directory is empty
        if not self.directory:
            self.logger.inject('Data directory is not defined', level='error', handler=self.hname)
            raise self.NotInitializedException('Data directory is not defined.')

        self.directory = os.path.abspath(self.directory) + '/' + self.request.get_attribute('prepid') + '/'

        # check if exists (and force)
        if os.path.exists(self.directory):
            #self.logger.warning('Directory ' + directory + ' already exists.')
            return

        # recursively create any needed parents and the dir itself
        os.makedirs(self.directory)


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
        #self.logger.inject_logger.handlers[0].setFormatter(inject_formatter(self.request.get_attribute('prepid')))
            #self.logger.addHandler(mh)

        self.logger.inject('full debugging information in ' + repr(self.__logfile), handler=self.hname)

    # check and init the tarball
    def __init_tarball(self):
        if self.directory:
            self.tarball = os.path.abspath(self.directory + os.path.pardir) + '/' +self.request.get_attribute('prepid')+'.tgz'
        else:
            self.tarball = None # randomize tarball name

        self.__tarobj = tarball(tarball=self.request.get_attribute('prepid')+'.tgz',  workdir=os.path.abspath(self.directory + os.path.pardir) + '/')

        if not self.tarball:
            self.tarball = self.__tarobj.tarball

        # inform
        self.logger.inject('Tarball : %s' % (self.tarball), handler=self.hname)

        return self.__tarobj

    # initialize configuration files for packaging
    def __init_configuration(self):
        if not self.directory:
            raise self.NotInitializedException

        self.logger.inject('Initializing configuration files...', handler=self.hname)

        # build path strings
        self.__summary = self.directory + 'summary.txt'
        self.__upload_configs = self.directory + 'upload_configs.sh'
        self.__injectAndApprove = self.directory + 'injectAndApprove.sh'

        self.logger.inject('Populating configuration files...', level='debug', handler=self.hname)

        # create summary
        try:
            sin = open(self.__summary, 'w')
            sin.write('request ID\tRelease\tEventcontent\tPriority\tEvents\ttime\tsize\tfilterEff\tmatchingEff\tdatasetName\tGlobalTag\tconfigurations\n')
            sin.close()
        except Exception as ex:
            self.logger.inject('Could not create summary file "%s". Reason: %s' % (self.__summary, ex), level='error', handler=self.hname)

        self.logger.inject('summary.txt file created', level='debug', handler=self.hname)

        # create upload_configs script
        try:
            uin = open(self.__upload_configs, 'w')
            uin.write('#!/usr/bin/env bash\n')
            uin.close()
        except Exception as ex:
            self.logger.inject('Could not create configuration injection file "%s". Reason: %s' % (self.__upload_configs, ex), level='error', handler=self.hname)

        self.logger.inject('upload_configs.sh script created', level='debug', handler=self.hname)

        # create injectAndApprove.sh script
        try:
            iin = open(self.__injectAndApprove, 'w')
            iin.write('#!/usr/bin/env bash\n')
            iin.close()
        except Exception as ex:
            self.logger.inject('Could not create injection file "%s". Reason: %s' % (self.__injectAndApprove, ex), level='error', handler=self.hname)

        self.logger.inject('injectAndApprove.sh script created', level='debug', handler=self.hname)

    # takes a path to a configuration file and a new line
    # appends the line to the end of the configuration
    def __update_configuration(self, configuration, line):
        if not line:
            return
        try:
            # make sure new entry is new
            fin = open(configuration, 'r')
            lines = fin.read()
            fin.close()

            # append the new line
            fin = open(configuration, 'a')

            # inject once for identical configurations
            if line not in lines:
                fin.write(line + '\n')
            fin.close()
        except Exception as ex:
            self.logger.inject('Could not update configuration file "%s". Reason: %s' % (configuration, ex), level='error', handler=self.hname)

    def init_package(self):
        self.__summary = self.directory + 'summary.txt'
        self.__upload_configs = self.directory + 'upload_configs.sh'
        self.__injectAndApprove = self.directory + 'injectAndApprove.sh'

        # initialize the config files
        self.__init_configuration()

    def __validate_configuration(self,  cmsDriver):
        # check if Prod
        if self.request.get_attribute('type') == 'Prod':
            if self.request.get_attribute('mcdb_id') == -1:
                self.wmagent_type = 'MonteCarlo'
            else:
                self.wmagent_type = 'MonteCarloFromGEN'

            if 'conditions' not in cmsDriver:
                raise self.NotInitializedException('Conditions are not defined.')

            if not self.request.get_attribute('cvs_tag'):
                raise self.NotInitializedException('No CVS Production Tag is defined.')

            #if not self.request.get_attribute('input_filename'):
            #    raise self.NotInitializedException('Input Dataset name is not defined.')

        # check if LHE
        elif  self.request.get_attribute('type') == 'LHE':
            if self.request.get_attribute('mcdb_id') == -1:
                self.wmagent_type = 'MonteCarlo'
            else:
                self.wmagent_type = 'MonteCarloFromGEN'

            if 'pileup' not in cmsDriver:
                raise self.NotInitializedException('PileUp Scenario is not defined.')

            if 'NoPileUp' not in cmsDriver:
                if not self.request.get_attribute('pileup_dataset_name'):
                    raise self.NotInitializedException('A pileup dataset name has not been provided.')

            if not self.request.get_attribute('cvs_tag'):
                raise self.NotInitializedException('No CVS Production Tag is defined.')

        # check if MCReproc
        elif self.request.get_attribute('type') == 'MCReproc':
            self.wmagent_type = 'ReDigi'

            if not self.request.get_attribute('input_filename'):
                raise self.NotInitializedException('Input Dataset name is not defined.')
            if 'conditions' not in cmsDriver:
                raise self.NotInitializedException('Conditions are not defined.')

    def __build_injection_command(self,  cmsDriver,  index):
        command = 'inject-to-config-cache '
        command += self.reqmgr_couchurl + ' '
        command += self.reqmgr_database + ' '
        command += self.reqmgr_user + ' '
        command += self.reqmgr_group + ' '
        command += "config_0_"+str(index)+"_cfg.py "
        command += 'step'+str(index)+'_'+self.request.get_attribute('member_of_campaign') + ' '
        command += '"step'+str(index)+'_'+self.request.get_attribute('member_of_campaign') + '" '
        command += ' | grep DocID | awk \'{print \"config_0_'+str(index)+'_cfg.py \"$2}\'\n'
        return command

    def __build_setup_script(self):
        # commands required for setting up the cms environ
        #script = open(self.directory + 'setup.sh', 'w')

        infile = ''
        infile += '#!/bin/bash\n'
        infile += 'cd ' + os.path.abspath(self.directory + '../') + '\n'
        infile += 'source  /afs/cern.ch/cms/cmsset_default.sh\n'
        infile += 'export SCRAM_ARCH=slc5_amd64_gcc434\n'
        infile += 'export myrel=' + self.request.get_attribute('cmssw_release') + '\n'
        infile += 'rel=`echo $myrel | sed -e "s/CMSSW_//g" | sed -e "s/_patch.*//g" | awk -F _ \'{print $1$2$3}\'`\n'
        infile += 'if [ $rel -gt 505 ]; then\n'
        infile += '  export SCRAM_ARCH=slc5_amd64_gcc462\n'
        infile += '  echo $SCRAM_ARCH\n'
        infile += 'fi\n'
        #infile += 'export SCRAM_ARCH=slc5_ia32_gcc434\n'
        infile += 'scram p CMSSW ' + self.request.get_attribute('cmssw_release') + '\n'
        infile += 'cd ' + self.request.get_attribute('cmssw_release') + '/src\n'
        infile += 'eval `scram runtime -sh`\n'

        infile += 'export CVSROOT=:pserver:anonymous@cmscvs.cern.ch:/local/reps/CMSSW\n'
        infile += "echo '/1 :pserver:anonymous@cmscvs.cern.ch:2401/local/reps/CMSSW AA_:yZZ3e' > cvspass\n"
        infile += "export CVS_PASSFILE=`pwd`/cvspass\n"

        # build personal proxy (mainly for cvs)
        #infile += 'source /afs/cern.ch/project/gd/LCG-share/current_3.2/etc/profile.d/grid_env.sh\n'
        #infile += 'voms-proxy-init --debug\n'

        # checkout from cvs (if needed)
        if self.request.get_attribute('nameorfragment') != None:
            infile += 'cvs co -r ' + self.request.get_attribute('cvs_tag') + ' ' + self.request.get_attribute('nameorfragment') + '\n'

        # previous counter
        previous = 0

        # validate and build cmsDriver commands
        cmsd_list = ''
        for cmsd in self.__cmsDrivers:

            # validate the configuration for each cmsDriver
            try:
                self.__validate_configuration(cmsd)
            except self.NotInitializedException as ex:
                return False

            # check if customization is needed
            if '--customise' in cmsd:
                cust = cmsd.split('--customise=')[1].split(' ')[0]
                toks = cust.split('.')
                cname = toks[0]
                cfun = toks[1]

                # add customization
                if 'GenProduction' in cname:
                    infile += 'cvs co -r ' + self.request.get_attribute('cvs_tag') + ' Configuration/GenProduction/python/' + cname.split('/')[-1]

            # finalize cmsDriver command
            res = cmsd
            res += ' --python_filename '+self.directory+'config_0_'+str(previous+1)+'_cfg.py '
            res += '--fileout step'+str(previous+1)+'.root '
            if previous > 0:
                res += '--filein file:step'+str(previous)+'.root '
                res += '--lazy_download '
            res += '--no_exec --dump_python -n '+str(self.events)#str(self.request.get_attribute('total_events'))
            #infile += res
            cmsd_list += res + '\n'

            self.__pyconfigs.append('config_0_'+str(previous+1)+'_cfg.py')

            # build injection commands and update the configurations
            incomm = self. __build_injection_command(cmsd,  previous+1)
            self.__update_configuration(self.__upload_configs,  incomm)

            previous += 1

        infile += '\nscram b\n'
        infile += cmsd_list
        # since it's all in a subshell, there is
        # no need for directory traversal (parent stays unaffected)
        infile += 'cd ../../\n'

        self.logger.inject(infile, level='debug', handler=self.hname)

        return infile

    # wraps around all the needed steps to prepare the
    # python configuration files
    def __prepare_request(self):
        # get cmsDriver commands from request object
        self.__cmsDrivers = self.request.build_cmsDrivers()

        # check to see if cmsDrivers are defined
        if not self.__cmsDrivers:
            raise self.NoStepsDetected(self.request.get_attribute('prepid'))

        self.logger.inject('Detected %d steps' % (len(self.__cmsDrivers)), handler=self.hname)

        # get the full setup.sh script
        fullcommand = self.__build_setup_script()

        if not fullcommand:
            self.logger.inject('Could build configuration scripts. Please check the request.', level='error', handler=self.hname)
            return False

        # write full command to setup.sh
        try:
            f = open(self.directory + os.path.pardir + '/'+'setup.sh',  'w')
            f.write(fullcommand)
            f.close()
        except IOError as ex:
            self.logger.inject('Could not access setup.sh script. IOError: %s' % (ex), level='critical', handler=self.hname)
            return False
        
        self.logger.inject('Created "setup.sh" script.', level='debug', handler=self.hname)

        # populate injectAndApprove.sh script
        self.__update_configuration(self.__injectAndApprove,  self.__prepare_approve_command())

        return 'sh '+self.directory + os.path.pardir + '/'+'setup.sh'

    # determine different request options for them
    # to be saved in upload_configs.sh and injectAndApprove.sh
    # injection scripts (This works the magic)
    def __prepare_approve_command(self):
        # calculate the appropriate scram architecture
        # set scram env
        scram_arch='slc5_amd64_gcc434'

        #assumed CMSSW_X_Y_Z_*
        releasesplit=self.request.get_attribute('cmssw_release').split("_")
        nrelease=releasesplit[1]+releasesplit[2]+releasesplit[3]
        if int(nrelease)>=510:
            scram_arch='slc5_amd64_gcc462'

        # use the central installation of wmconrol
	command = 'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n' 

        # if MonteCarlo analysis
        if self.wmagent_type == 'MonteCarlo':
            command += 'wmcontrol.py --release %s' %(self.request.get_attribute('cmssw_release'))
            command += ' --arch %s' %(scram_arch)
            command += ' --conditions %s::All' %(self.request.get_attribute('sequences')[0]['conditions'])
            command += ' --version %s' %("0") # dummy

            # set priority (only if it is defined)
            if self.request.get_attribute('priority') >= 1:
                command += ' --priority %s' %(self.request.get_attribute("priority"))

            command += ' --time-event %s' %(self.request.get_attribute('time_event'))
            command += ' --size-event %s' %(self.request.get_attribute('size_event'))

            # calculate filter efficiency
            feff = self.request.get_attribute('generator_parameters')[-1]['filter_efficiency']
            meff = self.request.get_attribute('generator_parameters')[-1]['match_efficiency']

            # calculate eff dev
            command += ' --filter-eff %s' %( float(feff) * float(meff) )

            command += ' --input-ds %s' %(self.request.get_attribute('input_filename'))
            command += ' --request-type %s' %(self.wmagent_type)
            command += ' --number-events %s' %(self.request.get_attribute('total_events'))
            command += ' --step1-cfg %s' %('config_0_1_cfg.py')
            command += ' --primary-dataset %s' %(self.request.get_attribute('dataset_name'))
            command += ' --request-id %s' %(self.request.get_attribute('prepid'))
            command += ' --cfg_db_file configs.txt'

        elif self.wmagent_type == 'MonteCarloFromGEN':
            command +=  'wmcontrol.py --release %s' %(self.request.get_attribute('cmssw_release'))
            command += ' --arch %s' %(scram_arch)
            command += ' --input-ds %s' %(self.request.get_attribute('input_filename'))
            command += ' --version %s' %("0") # dummy
            command += ' --conditions %s::All' %(self.request.get_attribute('sequences')[0]['conditions'])

            # set priority (only if it is defined)
            if self.request.get_attribute('priority') >= 1:
                command += ' --priority %s' %(self.request.get_attribute("priority"))

            command += ' --time-event %s' %(self.request.get_attribute('time_event'))
            command += ' --size-event %s' %(self.request.get_attribute('size_event'))

            # calculate filter efficiency
            feff = self.request.get_attribute('generator_parameters')[-1]['filter_efficiency']
            meff = self.request.get_attribute('generator_parameters')[-1]['match_efficiency']

            # calculate eff dev
            command += ' --filter-eff %s' %( float(feff) * float(meff) )

            command += ' --request-type %s' %(self.wmagent_type)
            command += ' --step1-cfg %s' %('config_0_1_cfg.py')
            command += ' --primary-dataset %s' %(self.request.get_attribute('dataset_name'))
            command += ' --request-id %s' %(self.request.get_attribute('prepid'))
            command += ' --cfg_db_file configs.txt'
            if self.request.get_attribute('input_block') != None:
                command += ' --blocks "'+self.request.get_attribute('input_block')+'"'


        elif self.wmagent_type == 'LHEStepZero':
            command += 'wmcontrol.py --release %s' %(self.request.get_attribute('cmssw_release'))
            command += ' --arch %s' %(scram_arch)
            command += ' --version %s' %("0") # dummy
            command += ' --conditions %s::All' %(self.request.get_attribute('sequences')[0]['conditions'])
            if self.request.get_attribute("priority") >= 1:
                command += ' --priority %s' %(self.request.get_attribute("priority"))
            command += ' --time-event %s' %(self.request.get_attribute('time_event'))
            command += ' --size-event %s' %(self.request.get_attribute('size_event'))
            command += ' --number-events %s' %(self.request.get_attribute('total_events'))
            command += ' --request-type %s' %(self.wmagent_type)
            command += ' --step1-cfg %s' %('config_0_1_cfg.py')
            command += ' --primary-dataset %s' %(self.request.get_attribute('dataset_name'))
            command += ' --request-id %s' %(self.request.get_attribute('prepid'))
            command += ' --cfg_db_file configs.txt'
            if int(self.mcdbid) == 0:
              command += ' --events-per-job '+str(self.numberOfEventsPerJob)


        # Else: ReDigi step
        elif self.wmagent_type == 'ReDigi':
            command +=  'wmcontrol.py --release %s' %(self.request.get_attribute('cmssw_release'))
            command += ' --arch %s' %(scram_arch)
            command += ' --input-ds %s' %(self.request.get_attribute('input_filename'))
            command += ' --step1-cfg %s' %('config_0_1_cfg.py')

            command += ' --version %s' %("0") # dummy
            command += ' --conditions %s::All' %(self.request.get_attribute('sequences')[0]['conditions'])
            # set priority (only if it is defined)
            if self.request.get_attribute('priority') >= 1:
                command += ' --priority %s' %(self.request.get_attribute("priority"))

            command += ' --request-type %s' %(self.wmagent_type)
            command += ' --request-id %s' %(self.request.get_attribute('prepid'))
            command += ' --cfg_db_file configs.txt'

            # temp ev cont holder
            eventcontentlist = []

            for cmsDriver in self.__cmsDrivers:
                if 'pileup' in cmsDriver:
                    if 'NoPileUp' in cmsDriver:
                        continue
                    else:
                        command += ' --pileup-ds '+self.request.get_attribute('pileup_dataset_name')

                # get the first event content of every defined sequence and use it as output
                eventcontent = cmsDriver.split('--eventcontent')[1].split(' ')[0]
                if ',' in eventcontent:
                    eventcontent = eventcontent.split(',')[0] + 'output'

                eventcontentlist.append(eventcontent)


            for i in range(len(eventcontentlist)):
                if len(eventcontentlist) > 1 and i < len(eventcontentlist)-1:
                    command += ' --keep-step'+str(i+1)+' True'
                if i > 0:
                    command += ' --step'+str(i+1)+'-cfg config_0_'+str(i+1)+'_cfg.py'
                if i < len(eventcontentlist)-1:
                    command += ' --step'+str(i+1)+'-output '+eventcontentlist[i]

            if self.request.get_attribute('process_string') != None:
                command += ' --process-string '+self.request.get_attribute('process_string')
            if self.request.get_attribute('input_block') != None:
                command += ' --blocks "'+self.request.get_attribute('input_block')+'"'


        command += ' --user %s' % (self.reqmgr_user)
        command += ' --group %s' % (self.reqmgr_group)
        command += ' --batch mybatch'
        command += '\n'

        return command

    def __build_summary_string(self):
        summarystring = str(self.request.get_attribute('prepid'))
        summarystring += '\t' + str(self.request.get_attribute('cmssw_release'))
        summarystring += '\t' + str(self.__cmsDrivers[0].split('--eventcontent')[1].split(' ')[0])
        summarystring += '\t' + str(self.request.get_attribute('priority'))
        summarystring += '\t' + str(self.request.get_attribute('total_events'))
        summarystring += '\t' + str(self.request.get_attribute('time_event'))
        summarystring += '\t' + str(self.request.get_attribute('size_event'))
        summarystring += '\t' + str(self.request.get_attribute('generator_parameters')[-1]['filter_efficiency'])
        summarystring += '\t' + str(self.request.get_attribute('generator_parameters')[-1]['match_efficiency'])
        summarystring += '\t' + str(self.request.get_attribute('dataset_name'))
        summarystring += '\t' + str(self.__cmsDrivers[0].split('--conditions')[1].split(' ')[0])
        for pyc in self.__pyconfigs:
            summarystring += '\t' + pyc

        if self.request.get_attribute('input_filename') != None:
            summarystring += '\t' + self.request.get_attribute('input_filename')

        if self.request.get_attribute('type') == 'LHE':
            summarystring += '\t' + self.request.get_attribute('nameorfragment').split('/')[-1] + '\t' + self.request.get_attribute('mcdb_id')

        return summarystring + '\n'

    # Spawns a subprocess to execute the setup script
    # and to produce the config files. If it fails, it
    # informs the user and dies.
    def build_configuration(self):
        # prepare the setup scripts
        command = self.__prepare_request()

        # Avoid faulty execution and inform the user.
        if not command:
            self.logger.inject("%s FAILED" % (self.request.get_attribute('prepid')), level='error', handler=self.hname)
            return False

        self.logger.inject('Executing setup scripts...', handler=self.hname)

        # spawn a subprocess to run it
        p = subprocess.Popen([command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        p.wait()

        # check for success
        retcode = p.poll()

        # get results
        output = p.stdout.read()
        output += p.stderr.read()

        self.logger.inject(output, level='debug', handler=self.hname)

        # when you fail, you die
        if retcode:
            self.logger.inject("%s FAILED" % (self.request.get_attribute('prepid')), level='error', handler=self.hname)
            return False

        self.logger.inject("%s SUBMITTED" % (self.request.get_attribute('prepid')), handler=self.hname)
        self.__update_configuration(self.__summary,  self.__build_summary_string())
        self.__update_configuration(self.__summary, 'Total evts = ' + str(self.request.get_attribute('total_events')))
        return True

    # clean up
    def close(self):
        #if self.closed:
        #    return

        #self.logger.debug('Shutting down...')
        #logging.shutdown()
        self.logger.remove_inject_handler(self.hname)

        # clean streams
        self.__tarobj.close()

        # delete directory
        #self.__delete_directory()

    # clean work directory for tarification
    def __clean_directory(self):
        self.logger.inject('Cleaning up directory ...', level='debug', handler=self.hname)

        for filename in os.listdir(self.directory):
            if filename == 'summary.txt':
                continue
            if filename == 'upload_configs.sh':
                continue
            if filename == 'injectAndApprove.sh':
                continue
            if '.log' in filename:
                continue
            if '.py' in filename:
                continue
            if os.path.isdir(self.directory + filename):
                continue

            self.logger.inject('Deleting %s...' % (filename), level='debug', handler=self.hname)

            try:
                # remove
                os.remove(self.directory + filename)
            except Exception as ex:
                self.logger.inject('Could not delete "%s". Reason: %s' % (filename, ex), level='error', handler=self.hname)

        # clean up parent directory
        for filename in os.listdir(self.directory + os.path.pardir):
            if '.tgz' in filename:
                continue

            try:
                # remove
                os.remove(self.directory + os.path.pardir + '/' + filename)
            except Exception as ex:
                try:
                    shutil.rmtree(self.directory + os.path.pardir + '/' + filename)
                except Exception as ex:
                    self.logger.inject('Could not delete "%s". Reason: %s' % (filename, ex), level='error', handler=self.hname)

    # delete working directory
    def __delete_directory(self):
        import shutil

        # clean configuration files & execution leftovers
        try:
            shutil.rmtree(self.directory)
        except Exception as ex:
            self.logger.inject('Could not delete directory "%s". Reason: %s' % (self.directory, ex), level='warning')
        try:
            tempy = os.path.abspath('.') + '/'
            dirlist = os.listdir(tempy)
            for filename in dirlist:
                try:
                    if 'CMSSW_' in filename:
                        shutil.rmtree(tempy + filename)
                except Exception:
                    continue
        except Exception as ex:
            self.logger.inject('Could not list files in directory "%s". Reason: %s' % (tempy, ex), level='warning')

    def build_package(self):
        #init configuration and package specific stuff
        self.init_package()

        flag = self.build_configuration()

        if not flag:
            return False
        
        # test configuration
        tester = package_tester(self.request,  self.directory,  self.__pyconfigs)
        if tester.test():
            self.__tarobj.add(self.directory)
            self.logger.inject('JOB successfully completed !', handler=self.hname)
            print 'JOB completed successfully'
            flag = True
        
        
        else:
        #    print 'JOB Failed. Check "/afs/cern.ch/work/n/nnazirid/public/prep2_submit_area/" for details'
            self.logger.inject('JOB Failed. Check tarball for details.', level='error', handler=self.hname) 
            flag = False

        # clean directory
        #self.__clean_directory()    

        # clean up
        self.close()

	#flag = True
        
        # inject config to couch
        if flag:
            self.logger.inject('Injecting...', handler=self.hname)

            # initialize injector object with the finalized tarball
            injector = package_injector(self.tarball.split('/')[-1],  self.request.get_attribute('cmssw_release'))

            if injector.inject():
                self.logger.inject('Injection successful !', handler=self.hname)
                flag = True
            else:
                self.logger.inject('Injection failed :( ', level='warning', handler=self.hname)
                flag = False

        return flag
