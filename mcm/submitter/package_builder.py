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
from json_layer.campaign import campaign
from json_layer.batch import batch
from couchdb_layer.prep_database import database
from tools.ssh_executor import ssh_executor
from tools.locator import locator
from tools.request_to_wma import request_to_wmcontrol

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


    def __init__(self,  req_json=None,  directory=None,  events=5):
        l_type=locator()
        if not directory:
            directory = l_type.workLocation()

        # set time out to 2000 seconds
        cherrypy.response.timeout = 2000
        
        # init request object
        try:
            self.request = request(json_input=req_json)
        except request.IllegalAttributeName:
            return

        self.__flags = []
        #self.__tarobj = None
        self.closed = False
        self.__logfile = ''
        self.__verbose = 4

        #JR
        ## figure out the batch number from the batch DB
        ### this should all be under some db class somewhere !!!
        bdb = database('batches')
        if req_json['flown_with']:
            self.batchName = req_json['flown_with']+'_'+req_json['member_of_campaign']
        else:
            self.batchName = req_json['member_of_campaign']

        #find the last open batch
        #res = map(lambda x: x['value'], bdb.query('prepid ~= %s-*'%(self.batchName), page_num=-1))
        #### doing the query by hand    
        res = bdb.queries([])
        res_this = filter(lambda x: x['prepid'].split('-')[0] == self.batchName, res)
        ## filter to have the ones of that family, that are NEW
        res_new = filter(lambda x: x['status']=='new', res_this)
        ##get only the serial number of those
        res_new = map(lambda x: int(x['prepid'].split('-')[-1]), res_new)

        ##find out the next one
        if not res_new:
            ##no open batch of this kind
            res_next = filter(lambda x: x['prepid'].split('-')[0].endswith(req_json['member_of_campaign']) , res) 
            if not res_next:
                ## not even a document with *_<campaign>-* existing: ---> creating a new family
                self.batchNumber=1
            else:
                ## pick up the last+1 serial number of *_<campaign>-*  family
                self.batchNumber=max(map(lambda x: int(x['prepid'].split('-')[-1]), res_next)) + 1
        else:
            ## pick up the last serial number of that family
            self.batchNumber=max(res_new)

        self.batchName+='-%05d'%(self.batchNumber)
        if not bdb.document_exists(self.batchName):
            newBatch = batch({'_id':self.batchName,'prepid':self.batchName})
            notes=""
            cdb = database('campaigns')
            mcm_c = cdb.get(req_json['member_of_campaign'])
            if mcm_c['notes']:
                notes+="Notes about the campaign:\n"+mcm_c['notes']+"\n"
            if req_json['flown_with']:
                fdb = database('flows')
                mcm_f = fdb.get(req_json['flown_with'])
                if mcm_f['notes']:
                    notes+="Notes about the flow:\n"+mcm_f['notes']+"\n"
            if notes:
                newBatch.set_attribute('notes',notes)
            newBatch.update_history({'action':'created'})
            bdb.save(newBatch.json())

        # list of different production steps (represented as a different element in the request's "sequences" property)
        self.__cmsDrivers = []
        self.wmagent_type = ''
        self.__injection_command = ''
        self.__build_command = ''

        # reqmgr config cache specifics
        #self.reqmgr_couchurl = "https://cmsweb.cern.ch/couchdb"
        #self.reqmgr_couchurl = "https://cmsweb-testbed.cern.ch/couchdb"
        #self.reqmgr_database = "reqmgr_config_cache"
        #self.reqmgr_user = "pdmvserv" 
        #self.reqmgr_group = "ppd" 

        # config files
        #self.__summary = None
        #self.__upload_configs = None
        self.__injectAndApprove = None
        self.__pyconfigs = []

        # There is a not-Initialized exception that is not handled
        self.directory = directory
        if l_type.isDev():
            self.careOfExistingDirectory = False
        else:
            ## care of existing diretories in prod instance so as to limit the amount of space taken by the submissions 
            self.careOfExistingDirectory = True
        ## override it ANYWAYS to false
        self.careOfExistingDirectory = False

        self.__check_directory() # check directory sanity

        # init logger
        #self.logger = None
        self.__build_logger()

        # initialize tarball
        self.tarball = None
        #self.__init_tarball()

        # the number of events to be tested.
        # for generation requests, I need to take into consideration
        # the matching and filter efficiencies
        if self.request.get_attribute('generator_parameters'):
            match = float(self.request.get_attribute('generator_parameters')[-1]['match_efficiency'])
            filter_eff = float(self.request.get_attribute('generator_parameters')[-1]['filter_efficiency'])
            if match > -1 and filter_eff > -1:
                self.events = int(math.fabs(events / (match*filter_eff)))
            else:
                self.events = int(math.fabs(events))
        else:
            #self.events = math.fabs(int(events))
            self.events = int(math.fabs(events))

        # avoid large testing samples
        if self.events > 1000:
            truncatedTo=50
            self.logger.inject('The run test should be on %d events, truncating to %d'%(self.events,truncatedTo), handler=self.hname)
            self.events = truncatedTo

        self.ssh_exec = ssh_executor(self.directory,self.hname)

    # check and create all working directories
    def __check_directory(self):

        # check if directory is empty
        if not self.directory:
            self.logger.inject('Data directory is not defined', level='error', handler=self.hname)
            raise self.NotInitializedException('Data directory is not defined.')

        self.directory = os.path.abspath(self.directory) + '/' + self.request.get_attribute('prepid') + '/'

        # check if exists (and force)
        if os.path.exists(self.directory):
            self.logger.error('Directory ' + self.directory + ' already exists.')
            self.logger.error( os.popen('echo %s; ls -f %s'%(self.directory, self.directory)).read())
            if self.careOfExistingDirectory:
                raise self.NotInitializedException('Data directory %s already exists'%(self.directory))
                return
        else:
            self.logger.log('Creating directory :'+self.directory)

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

    """
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
    """


    # initialize configuration files for packaging
    def __init_configuration(self):
        if not self.directory:
            raise self.NotInitializedException

        self.logger.inject('Initializing configuration files...', handler=self.hname)

        # build path strings
        self.__injectAndApprove = self.directory + 'injectAndApprove.sh'

        self.logger.inject('Populating configuration files...', level='debug', handler=self.hname)

        # create injectAndApprove.sh script
        try:
            iin = open(self.__injectAndApprove, 'w')
            iin.write('#!/usr/bin/env bash\n')
            iin.close()
        except Exception as ex:
            self.logger.inject('Could not create injection file "%s". Reason: %s' % (self.__injectAndApprove, ex), level='error', handler=self.hname)

        self.logger.inject('injectAndApprove.sh script recreated for further appending', level='debug', handler=self.hname)

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
        #self.__summary = self.directory + 'summary.txt'
        #self.__upload_configs = self.directory + 'upload_configs.sh'
        self.__injectAndApprove = self.directory + 'injectAndApprove.sh'

        # initialize the config files
        self.__init_configuration()

        """
        def __validate_configuration(self,  cmsDriver):

        # check if Prod
        if self.request.get_attribute('type') == 'Prod':
            if self.request.get_attribute('mcdb_id') == -1:
                if self.request.get_attribute('input_filename'):
                    self.wmagent_type = 'MonteCarloFromGEN'
                else:
                    self.wmagent_type = 'MonteCarlo'
            else:
                self.wmagent_type = 'MonteCarloFromGEN'

            if 'conditions' not in cmsDriver:
                raise self.NotInitializedException('Conditions are not defined.')

            if not self.request.get_attribute('cvs_tag') and not self.request.get_attribute('fragment') and not self.request.get_attribute('name_of_fragment'):
                raise self.NotInitializedException('No CVS Production Tag is defined. No fragement name, No fragment text')

        # check if LHE
        elif  self.request.get_attribute('type') in ['LHE','LHEStepZero']:
            self.wmagent_type = 'LHEStepZero' #'MonteCarloFromGEN'

            if not (self.request.get_attribute('cvs_tag') and self.request.get_attribute('name_of_fragment')) and not self.request.get_attribute('fragment') and self.request.get_attribute('mcdb_id')<=0:
                raise self.NotInitializedException('No CVS Production Tag is defined. No fragement name, No fragment text')


        # check if MCReproc
        elif self.request.get_attribute('type') == 'MCReproc':
            self.wmagent_type = 'ReDigi'

            if not self.request.get_attribute('input_filename'):
                raise self.NotInitializedException('Input Dataset name is not defined.')
            if 'conditions' not in cmsDriver:
                raise self.NotInitializedException('Conditions are not defined.')
        """

    def __build_setup_script(self):
        # commands required for setting up the cms environ

        self.scram_arch=self.request.get_scram_arch()
        infile = self.request.get_setup_file(self.directory)

        # previous counter
        previous = 0

        # validate and build cmsDriver commands


        cmsd_list = ''
        self.wmagent_type = self.request.get_wmagent_type()
        
        if not self.request.verify_sanity():
            return False

        for cmsd in self.__cmsDrivers:
            ## this could be done a bit more transparently
            self.__pyconfigs.append(self.request.get_attribute('prepid')+'_'+str(previous+1)+'_cfg.py')
            previous += 1

            
        ## add the validation sequences if any ?
        if self.request.genvalid_driver:
            self.__pyconfigs.append('genvalid.py')
            self.__pyconfigs.append('genvalid_harvesting.py')
            
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
        self.__setupFile = self.request.get_attribute('prepid')+'-setup.sh'
        try:
            f = open(self.directory + os.path.pardir + '/'+self.__setupFile,  'w')
            f.write(fullcommand)
            f.close()
        except IOError as ex:
            self.logger.inject('Could not access setup.sh script. IOError: %s' % (ex), level='critical', handler=self.hname)
            return False
        
        self.logger.inject('Created "%s" script.'%(self.__setupFile), level='debug', handler=self.hname)

        # populate injectAndApprove.sh script
        ## JR try moving downstream
        #self.__update_configuration(self.__injectAndApprove,  self.__prepare_approve_command())

        return 'sh '+self.directory + os.path.pardir + '/'+self.__setupFile

    # determine different request options for them
    # to be saved in upload_configs.sh and injectAndApprove.sh
    # injection scripts (This works the magic)
    def __prepare_approve_command(self):


        return request_to_wmcontrol().get_command( self.request, self.batchNumber)

    """
        # calculate the appropriate scram architecture
        # set scram env
        #self.scram_arch='slc5_amd64_gcc434'

        #assumed CMSSW_X_Y_Z_*
        #releasesplit=self.request.get_attribute('cmssw_release').split("_")
        #nrelease=releasesplit[1]+releasesplit[2]+releasesplit[3]
        #if int(nrelease)>=510:
        #    self.scram_arch='slc5_amd64_gcc462'

        # use the central installation of wmconrol
        command = ''
        #command += '#!/usr/bin/env bash\n' 
	command += 'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n' 


        command += 'wmcontrol.py --release %s' %(self.request.get_attribute('cmssw_release'))
        command += ' --arch %s' %(self.scram_arch)
        command += ' --conditions %s' %(self.request.get_attribute('sequences')[0]['conditions'])
        command += ' --version %s' %(self.request.get_attribute('version'))
        if self.request.get_attribute('priority') >= 1:
            command += ' --priority %s' %(self.request.get_attribute("priority"))
        command += ' --time-event %s' %(self.request.get_attribute('time_event'))
        command += ' --size-event %s' %(self.request.get_attribute('size_event'))
        command += ' --request-type %s' %(self.wmagent_type)
        #command += ' --step1-cfg %s' %('config_0_1_cfg.py')
        command += ' --step1-cfg %s' %(self.request.get_attribute('prepid')+'_1_cfg.py')
        command += ' --request-id %s' %(self.request.get_attribute('prepid'))

        ##JR in order to inject into the testbed instead of the production machine
        l_type = locator()
        if l_type.isDev(): 
            command += ' --wmtest '
        #command += ' --user %s' % (self.reqmgr_user)
        command += ' --user pdmvserv '
        command += ' --group ppd '
        command += ' --batch %s' % (self.batchNumber)

        processString = self.request.get_attribute('process_string')

        # if MonteCarlo analysis
        if self.wmagent_type == 'MonteCarlo':
            # calculate filter efficiency
            feff = self.request.get_attribute('generator_parameters')[-1]['filter_efficiency']
            meff = self.request.get_attribute('generator_parameters')[-1]['match_efficiency']

            # calculate eff dev
            command += ' --filter-eff %s' %( float(feff) * float(meff) )

            command += ' --number-events %s' %(self.request.get_attribute('total_events'))
            command += ' --primary-dataset %s' %(self.request.get_attribute('dataset_name'))

        elif self.wmagent_type == 'MonteCarloFromGEN':
            # calculate filter efficienc
            feff = self.request.get_attribute('generator_parameters')[-1]['filter_efficiency']
            meff = self.request.get_attribute('generator_parameters')[-1]['match_efficiency']

            # calculate eff dev
            command += ' --filter-eff %s' %( float(feff) * float(meff) )

            command += ' --input-ds %s' %(self.request.get_attribute('input_filename'))

            command += ' --primary-dataset %s' %(self.request.get_attribute('dataset_name'))

            if self.request.get_attribute('block_white_list'):
                command += ' --blocks "'+','.join(self.request.get_attribute('block_white_list'))+'"'
            if self.request.get_attribute('block_black_list'):
                command += ' --blocks_black "'+','.join(self.request.get_attribute('block_black_list'))+'"'


        elif self.wmagent_type == 'LHEStepZero':

            command += ' --number-events %s' %(self.request.get_attribute('total_events'))
            command += ' --primary-dataset %s' %(self.request.get_attribute('dataset_name'))

            if self.request.get_attribute('mcdb_id') <= 0:
                self.numberOfEventsPerJob = self.request.numberOfEventsPerJob()
                if not self.numberOfEventsPerJob:
                    raise ValueError('Number of events per job could not be retrieved')

                self.logger.inject('Number of evetns per job : %s'%(self.numberOfEventsPerJob),  level='debug', handler=self.hname)
                command += ' --events-per-job %s' % (self.numberOfEventsPerJob)
            else:
                command += ' --lhe '
                if not processString:
                    processString=''
                processString+='STEP0ATCERN'

        # Else: ReDigi step
        elif self.wmagent_type == 'ReDigi':

            command += ' --input-ds %s' %(self.request.get_attribute('input_filename'))
            ## if PU dataset name is defined : add it
            if self.request.get_attribute('pileup_dataset_name'):
                command += ' --pileup-ds '+self.request.get_attribute('pileup_dataset_name')

            ## provide the total number of events requested: by default it is the amount in the input dataset.
            # and wmcontrol / wma should understand that we want partial statistics if that number is lower than expected
            command += ' --number-events %s' %(self.request.get_attribute('total_events'))
            # temp ev cont holder
            eventcontentlist = self.request.get_first_output()
            

            ##shipped back to request object 
            #for cmsDriver in self.__cmsDrivers:
            #    ## check for pileup dataset ??? why ?
            #    #if 'pileup' in cmsDriver:
            #    #    if 'NoPileUp' in cmsDriver:
            #    #        continue
            #    #    else:
            #    #        command += ' --pileup-ds '+self.request.get_attribute('pileup_dataset_name')
#
#                # get the first event content of every defined sequence and use it as output to the next step...
#                eventcontent = cmsDriver.split('--eventcontent')[1].split()[0] + 'output'
#                if ',' in eventcontent:
#                    eventcontent = eventcontent.split(',')[0] + 'output'
#
#                eventcontentlist.append(eventcontent)
 
    
            keeps = self.request.get_attribute('keep_output')
            if not keeps[-1]:
                raise ValueError('Is not set to save the output of last task')

            for (i,content) in enumerate(eventcontentlist):
                if keeps[i]:
                    command += ' --keep-step'+str(i+1)+' True'

                #if len(eventcontentlist) > 1 and i < len(eventcontentlist)-1:
                #    command += ' --keep-step'+str(i+1)+' True'
                if i > 0:
                    #command += ' --step'+str(i+1)+'-cfg config_0_'+str(i+1)+'_cfg.py'
                    command += ' --step'+str(i+1)+'-cfg '+self.request.get_attribute('prepid')+'_'+str(i+1)+'_cfg.py'
                # set the output of 
                if i < len(eventcontentlist)-1:
                    command += ' --step'+str(i+1)+'-output '+content


            if self.request.get_attribute('block_white_list'):
                command += ' --blocks "'+','.join(self.request.get_attribute('block_white_list'))+'"'
            if self.request.get_attribute('block_black_list'):
                command += ' --blocks_black "'+','.join(self.request.get_attribute('block_black_list'))+'"'



        if processString:
            command += ' --process-string '+processString

        command += '\n'

        return command
"""

    # Spawns a subprocess to execute the setup script
    # and to produce the config files. If it fails, it
    # informs the user and dies.
    def build_configuration(self):
        # prepare the setup scripts
        command = self.__prepare_request()

        # Avoid faulty execution and inform the user.
        if not command:
            self.logger.inject("%s Command Preparation FAILED" % (self.request.get_attribute('prepid')), level='error', handler=self.hname)
            return False

        self.logger.inject('Executing setup scripts...', handler=self.hname)

        # spawn a subprocess to run it
        
        #s p = os.popen(command)
        #s output = p.read()
        #s retcode = p.close()
        
        #use it via ssh instead of running it locally
        stdin, stdout, stderr = self.ssh_exec.execute(command)
        output=stdout.read()
        retcode=0
        if not stdin and not stdout and not stderr:
            retcode = -1
        sterr=stderr.read() ## this contains much more than what it should
        if len(sterr):
            self.logger.inject("%s Preparation FAILED with :\n %s" % (self.request.get_attribute('prepid'),sterr), level='error', handler=self.hname)
            retcode = -1

        #move it lower ? higher ? within a try/except ?
        self.__update_configuration(self.__injectAndApprove,  self.__prepare_approve_command())    

        self.logger.inject(output, level='debug', handler=self.hname)

        # when you fail, you die
        if retcode:
            self.logger.inject("%s Creation FAILED" % (self.request.get_attribute('prepid')), level='error', handler=self.hname)
            self.request.test_failure(sterr)
            return False

        self.logger.inject("%s Creation SUCCESS" % (self.request.get_attribute('prepid')), handler=self.hname)
        #self.__update_configuration(self.__summary,  self.__build_summary_string())
        #self.__update_configuration(self.__summary, 'Total evts = ' + str(self.request.get_attribute('total_events')))
        return True

    # clean up
    def close(self):
        #if self.closed:
        #    return

        #self.logger.debug('Shutting down...')
        #logging.shutdown()
        self.logger.remove_inject_handler(self.hname)

        # clean streams
        #self.__tarobj.close()

        # delete directory
        if self.careOfExistingDirectory:
            self.__delete_directory()

    """
    # clean work directory for tarification
    def __clean_directory(self):
        self.logger.inject('Cleaning up directory ...', level='debug', handler=self.hname)

        for filename in os.listdir(self.directory):
            if filename == 'summary.txt':
                continue
            #if filename == 'upload_configs.sh':
            #    continue
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

    """

    # delete working directory
    def __delete_directory(self):
        import shutil
        self.logger.error('I am trying to remove the directory %s'%( self.directory ))

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

    def build_package(self, how_far=None):
	# log new injection
	#self.logger.inject('## Logger instance retrieved', level='debug')

        #init configuration and package specific stuff
        self.init_package()

        flag = self.build_configuration()

        if not flag:
            self.close()
            return False
        
        ## JR find a way to skip testing in batch the request for digi-reco requests
        # test configuration
        cdb = database('campaigns')
        camp = campaign(cdb.get(self.request.get_attribute('member_of_campaign')))
        if camp.get_attribute('root')==1:
            #self.__tarobj.add(self.directory)
            self.logger.inject('Requests not from root or possible root campaigns do not need to be ran locally')
            flag=True
        else:
            self.logger.inject('Testing request for %d events'%(self.events))
            tester = package_tester(self.request,  self.directory,  self.__pyconfigs)
            tester.scram_arch = self.scram_arch
            if tester.test():
                #self.__tarobj.add(self.directory)
                self.logger.inject('Runtime Test Job successfully completed !', handler=self.hname)
                #print 'JOB completed successfully'
                flag = True
        
        
            else:
                #    print 'JOB Failed. Check "/afs/cern.ch/work/n/nnazirid/public/prep2_submit_area/" for details'
                self.logger.inject('Runtime Test Job Failed. Check logs for details.', level='error', handler=self.hname) 
                flag = False

        if not flag:
            self.close()
            message='Runtest failed \n %s \n'%( tester.job_log_when_failed )
            self.request.test_failure(message)
            return False

        #if how_far and how_far=='test':
        #    self.close()
        #    return True

        # clean directory
        #self.__clean_directory()    

        # clean up
        #self.close()

	#flag = True
        
        # inject config to couch
        if flag:
            self.logger.inject('Creating Injection...', handler=self.hname)

            # initialize injector object with the finalized tarball
            injector = None
            #try:
            #injector = package_injector(self.tarball.split('/')[-1],  self.request.get_attribute('cmssw_release')+":"+self.scram_arch)
            injector = package_injector(self.request.get_attribute('prepid'),  self.request.get_attribute('cmssw_release')+":"+self.scram_arch)
            #except:
            #    self.logger.inject('Injection failed', level='warning', handler=self.hname)
            #    self.request.test_failure(message)
            #    flag = False

            self.logger.inject('Injecting...', handler=self.hname)
            if injector.inject():
                if injector.requestNames:
                    self.logger.inject('Injection successful !', handler=self.hname)
                    flag = True
                    
                    added=[]
                    for request in injector.requestNames:
                        added.append({'name':request,'content':{'pdmv_prep_id':self.request.get_attribute('prepid') }})
                    ## put it in the request object
                    requests=self.request.get_attribute('reqmgr_name')
                    requests.extend(added)
                    self.request.set_attribute('reqmgr_name',requests)

                    cf_ids= self.request.get_attribute('config_id')
                    cf_ids.append( injector.config_ids )
                    self.request.set_attribute('config_id', cf_ids)
                    hash_ids = database('configs')
                    for (step_i,docid) in enumerate(injector.config_ids):
                        hash_id=self.request.configuration_identifier(step_i)
                        if not hash_ids.document_exists( hash_id ):
                            ##then save that in the db for future usage
                            new_hash_doc={'_id': hash_id,
                                          'docid' : docid,
                                          'prepid' : self.request.get_attribute('prepid'),
                                          'unique_string' : self.request.unique_string(step_i)
                                          }
                            saved = hash_ids.save( new_hash_doc )
                            if not saved:
                                self.logger.inject('Could not save the has document %s'%( hash_id ), level='warning', handler=self.hname)
                                return False
                            
                        
                    ##put it also in the batch DB
                    bdb = database('batches')
                    b=batch(bdb.get(self.batchName))
                    b.add_requests(added)
                    note=[]

                    if self.request.get_attribute('extension'):
                        note.append(' is an extension')
                    if len(self.request.get_attribute('reqmgr_name'))>1: #>1 because you just added that submission request a few lines above
                        note.append(' is a resubmission')
                    if len(note):
                        b.add_notes('\n%s: %s'%(self.request.get_attribute('prepid'),
                                              ','.join(note)))
                    b.update_history({'action':'updated'})

                    ##save all only at the end with all suceeding to not have half/half
                    rdb = database('requests')

                    #the status is set only if there is actually a request in the request manager !
                    self.request.update_history({'action':'inject'})
                    self.request.set_status(with_notification=True)
                    rdb.update(self.request.json())
                    bdb.update(b.json())
                    for request in added:
                        self.logger.inject('Request %s send to %s'%(request['name'],self.batchName))
                else:
                    message='Injection has succeeded but no request manager names were registered. Check with administrators'
                    self.logger.inject(message, level='warning', handler=self.hname)
                    self.request.test_failure(message)

            else:
                message='Injection failed'
                self.logger.inject(message, level='warning', handler=self.hname)
                self.request.test_failure(message)
                flag = False

        return flag
