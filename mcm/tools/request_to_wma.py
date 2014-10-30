from tools.locator import locator
from tools.ssh_executor import ssh_executor
from tools.dbs3_interface import dbs3_interface
from couchdb_layer.mcm_database import database
from json_layer.request import request
from tools.settings import settings 

class request_to_wmcontrol:
    """
    performs the translation of an McM request to wmcontrol
    """

    def __init__(self):
        pass

    def get_dict(self, mcm_r):
        ## the batch number does not matter anymore
        request_dict = {}
        ## get the schema from where it belongs ?

        static_schemas={
            'MonteCarlo' : {
                'FirstEvent' : 1,
                'FirstLumi' : 1,
                'EventsPerLumi' : 
                },
            'MonteCarloFromGEN' : {
                'BlockBlacklist' : [],
                'RunBlacklist' : []
                },
            'ReDigi' : {
                }
            }
        schemas = { 
            'MonteCarlo' : { 
                'FilterEfficiency' : 'get_efficiency',
                'LheInputFiles' : 'get_lhe_input',
                'RequestNumEvents' : 'total_events',
                'FilterEfficiency' : 'get_efficiency',
                },
            'MonteCarloFromGEN' : {
                'BlockWhitelist' : 'block_white_list',
                'FilterEfficiency' : 'get_efficiency',
                'InputDataset' : 'input_dataset',
                },
            'ReDigi': {
                'MCPileup' : 'pileup_dataset',
                }
            }
        ## dependencies
        schemas['ReDigi'].update( schema['MonteCarloFromGEN'] )
        
        static_block ={
            'DbsUrl' : '',
            'CouchURL' : '',
            'ConfigCacheURL' : '',
            'inputMode' : 'couchDB',
            'RequestString' : '',
            'Requestor' : 'pdmvserv',
            'Group' : 'ppd',
            'OpenRunningTimeout' : 43200,
            'TotalTime' : 28800,
            }

        common = { 
            'ScramArch' : 'get_scram_arch',
            'CMSSWVersion' : 'cmssw_release',
            'Version' : 'version',
            'TimePerEvent' : 'time_event',
            'SizePerEvent' : 'size_event',
            'Memory' : 'memory',
            'PrimaryDataset' : 'dataset_name',
            'PrepID' : 'prepid',
            'Campaign' : 'member_of_campaign',
            'RequestPriority' : 'priority',
            'AcquisitionEra' : 'member_of_campaign',
            }

        for (t,schema) in schemas.items():
            schema.update( common )


        ## figure out the block white list if need be
        if mcm_r.get_attribute('input_dataset'):
            dbs3 = dbs_interface()
            blocks = dbs3.match_stats( mcm_r.get_attribute('input_dataset'), 
                                       mcm_r.get_attribute('total_events'),
                                       0.05)#match within 5%
            mcm_r.set_attribute('block_white_list', blocks)

        ## then figure it out
        wmagent_type = mcm_r.get_wmagent_type()
        schema = schemas[wmagent_type]
        for (k,spec) in schema.items():
            
            if hasattr( mcm_r, spec):
                ## this is something that can be called from the request object
                schema[k] = getattr(mcm_r, spec)()
            else:
                schema[k] = mcm_r.get_attribute( spec )

        # add things schema dependent but not request dependent
        schema.update( static_block )
        scheme.update( static_schemas[wmagent_type] )

        ## then the last few modifications
        schema['RequestString'] = 'something funny'
        if 'LheInputFiles' in schema and schema['LheInputFiles']:
            schema['EventsPerJob'] = 500000
        if 'EventsPerLumi' in schema:
            events_per_lumi = settings().get_value('events_per_lumi')
            ## forward looking into the chain to adjust that number
            max_forward_eff = mcm_r.get_forward_efficiency() # will be one if nothing forward. gets the max efficiency if any
            schema['EventsPerLumi'] = events_per_lumi / max_forward_eff

        schema['GlobalTag'] = mcm_r.get_attribute('sequences')[0]['conditions']
        schema['ProcessingString'] = mcm_r.get_processing_string(0)
        step_words=['Zero','One','Two','Three', 'Four','Five','Six','Seven','Eight','Nine']
        docids = mcm_r.get_attribute('config_id')
        keeps = mcm_r.get_attribute('keep_output')
        eventcontentlist = mcm_r.get_first_output()
        for (istep,sname) in enumerate(step_words):
            if istep == 0:
                schema['ConfigCacheID'] = docids[istep]
            else:
                schema['Step%sConfigCacheID'%sname] = docids[istep]
                schema['KeepStep%sOutput'%sname] = keeps[istep]
                schema['Step%sOutputModuleName'%sname] = eventcontentlist[istep]
        return schema
                
    def get_command(self, mcm_r, batchNumber, to_execute=False):
        command = ''

        ##JR in order to inject into the testbed instead of the production machine
        l_type = locator()
        if to_execute:
            # set path to proxy certificate
            command += 'cd %s\n' % ( l_type.workLocation() )
            command += 'export X509_USER_PROXY=/afs/cern.ch/user/p/pdmvserv/private/$HOSTNAME/voms_proxy.cert\n'
            command += mcm_r.make_release()
            #command += 'eval `scram runtime -sh`\n'
            command += 'source /afs/cern.ch/cms/PPD/PdmV/tools/wmclient/current/etc/wmclient.sh\n'

        wmagent_type = mcm_r.get_wmagent_type()
        command += 'export PATH=/afs/cern.ch/cms/PPD/PdmV/tools/wmcontrol:${PATH}\n'
        command += 'wmcontrol.py --release %s' % (mcm_r.get_attribute('cmssw_release'))
        command += ' --arch %s' % (mcm_r.get_scram_arch())
        command += ' --conditions %s' % (mcm_r.get_attribute('sequences')[0]['conditions'])
        command += ' --version %s' % (mcm_r.get_attribute('version'))
        if mcm_r.get_attribute('priority') >= 1:
            command += ' --priority %s' % (mcm_r.get_attribute("priority"))
        command += ' --time-event %s' % (mcm_r.get_attribute('time_event'))
        command += ' --size-event %s' % (mcm_r.get_attribute('size_event'))
        command += ' --memory %s' % (mcm_r.get_attribute('memory'))
        ##that type has disappeared
        if wmagent_type == 'LHEStepZero':
            command += ' --request-type MonteCarlo'
        else:
            command += ' --request-type %s' % wmagent_type

        config_id_from_hashkey = []

        ## check on the presence of docId ?...
        if len(mcm_r.get_attribute('config_id')):
            command += ' --step1-docID %s' % ( mcm_r.get_attribute('config_id')[0])
        else:
            ## get the config ID from hash instead of cfg.py
            hash_ids = database('configs')
            hash_id = mcm_r.configuration_identifier(0)
            if hash_ids.document_exists(hash_id):
                hash_doc = hash_ids.get(hash_id)
                config_cache_id = hash_doc['docid']
                command += ' --step1-docID %s' % config_cache_id
                config_id_from_hashkey = [config_cache_id]
            else:
                command += ' --step1-cfg %s_1_cfg.py' % (mcm_r.get_attribute('prepid'))

        command += ' --request-id %s' % (mcm_r.get_attribute('prepid'))

        if l_type.isDev():
            command += ' --wmtest '

        command += ' --user pdmvserv '
        command += ' --group ppd '
        command += ' --batch %s' % batchNumber

        processString = mcm_r.get_attribute('process_string')
        processingString = mcm_r.get_processing_string(0)


        max_forward_eff = mcm_r.get_forward_efficiency()
        events_per_lumi = settings().get_value('events_per_lumi')
        
        if wmagent_type == 'MonteCarlo':

            # calculate eff dev
            command += ' --filter-eff %s' % ( mcm_r.get_efficiency() )
            command += ' --events-per-lumi %s' % ( events_per_lumi / max_forward_eff )
            command += ' --number-events %s' % (mcm_r.get_attribute('total_events'))
            command += ' --primary-dataset %s' % (mcm_r.get_attribute('dataset_name'))
        elif wmagent_type == 'MonteCarloFromGEN':
            # calculate eff dev                
            command += ' --filter-eff %s' % ( mcm_r.get_efficiency() )

            command += ' --input-ds %s' % (mcm_r.get_attribute('input_dataset'))

            command += ' --primary-dataset %s' % (mcm_r.get_attribute('dataset_name'))

            if mcm_r.get_attribute('block_white_list'):
                command += ' --blocks "' + ','.join(mcm_r.get_attribute('block_white_list')) + '"'
            if mcm_r.get_attribute('block_black_list'):
                command += ' --blocks_black "' + ','.join(mcm_r.get_attribute('block_black_list')) + '"'

            command += ' --number-events %s' % (mcm_r.get_attribute('total_events'))
            command += ' --events-per-lumi 100'

        elif wmagent_type == 'LHEStepZero':

            command += ' --number-events %s' % (mcm_r.get_attribute('total_events'))
            command += ' --events-per-lumi %s' % ( events_per_lumi / max_forward_eff )

            command += ' --primary-dataset %s' % (mcm_r.get_attribute('dataset_name'))
            command += ' --filter-eff %s' % ( mcm_r.get_efficiency() )

            if mcm_r.get_attribute('mcdb_id') <= 0:
                numberOfEventsPerJob = mcm_r.numberOfEventsPerJob()
                if not numberOfEventsPerJob:
                    raise ValueError('Number of events per job could not be retrieved')
                command += ' --events-per-job %s' % numberOfEventsPerJob
            else:
                command += ' --lhe '
                if not processString:
                    processString = ''
                processString += 'STEP0ATCERN'

        elif wmagent_type == 'ReDigi':

            command += ' --input-ds %s' % (mcm_r.get_attribute('input_dataset'))

            command += ' --primary-dataset %s' % (mcm_r.get_attribute('dataset_name'))

            ## if PU dataset name is defined : add it
            if mcm_r.get_attribute('pileup_dataset_name') and mcm_r.get_attribute('pileup_dataset_name').strip():
                command += ' --pileup-ds ' + mcm_r.get_attribute('pileup_dataset_name')

            ## provide the total number of events requested: by default it is the amount in the input dataset.
            # and wmcontrol / wma should understand that we want partial statistics if that number is lower than expected
            command += ' --number-events %s' % (mcm_r.get_attribute('total_events'))
            # temp ev cont holder
            eventcontentlist = mcm_r.get_first_output()

            keeps = mcm_r.get_attribute('keep_output')
            if not keeps[-1]:
                raise ValueError('Is not set to save the output of last task')

            for (i, content) in enumerate(eventcontentlist):
                if i < 2: #trick to NOT add for step3 and more:
                    if keeps[i]:
                        command += ' --keep-step' + str(i + 1) + ' True'

                if i > 0:
                    processingString = mcm_r.get_processing_string(i)
                    if len(mcm_r.get_attribute('config_id')):
                        command += ' --step%d-docID %s' % (i + 1, mcm_r.get_attribute('config_id')[i])
                    else:
                        hash_id = mcm_r.configuration_identifier(i)
                        if hash_ids.document_exists(hash_id):
                            hash_doc = hash_ids.get(hash_id)
                            config_cache_id = hash_doc['docid']
                            command += ' --step%d-docID %s' % (i + 1, config_cache_id)
                            config_id_from_hashkey.append(config_cache_id)
                        else:
                            command += ' --step%d-cfg %s_%d_cfg.py' % ( i + 1, mcm_r.get_attribute('prepid'), i + 1)

                # set the output of 
                if i < len(eventcontentlist) - 1:
                    command += ' --step' + str(i + 1) + '-output ' + content

            if mcm_r.get_attribute('block_white_list'):
                command += ' --blocks "' + ','.join(mcm_r.get_attribute('block_white_list')) + '"'
            if mcm_r.get_attribute('block_black_list'):
                command += ' --blocks_black "' + ','.join(mcm_r.get_attribute('block_black_list')) + '"'
            

        if processString:
            command += ' --process-string ' + processString

        command += ' --processing-string ' + processingString
        command += '|| exit $? ;'
        command += '\n'

        if len(config_id_from_hashkey):
            mcm_r.set_attribute('config_id', config_id_from_hashkey)

        return command

    def get_requests(self, mcm_r):
        ssh = ssh_executor(location.location(), mcm_r.get_attribute('prepid'))
        stdin, stdout, stderr = ssh.execute('bash %s' % test_script)

        fullOutPutText = stdout.read()
        error = stderr.read()
        Exceptions = []
        for line in error.split('\n'):
            if '[wmcontrol exception]' in line:
                Exceptions.append(line)

        if len(Exceptions):
            self.logger.error('Executed \n %s' % fullOutPutText)
            self.logger.error('Errors returned: %s' % error)
            return False

        requestNames = []
        for line in fullOutPutText.split('\n'):
            if line.startswith('Injected workflow:'):
                requestNames.append(line.split()[2])

        if not len(requestNames):
            self.logger.error('There were no request manager name recorded \n %s' % fullOutPutText)
            return False

        self.logger.log('Injection output: %s' % fullOutPutText)

        return True
