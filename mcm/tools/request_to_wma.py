from tools.locator import locator
from tools.ssh_executor import ssh_executor
from couchdb_layer.mcm_database import database


class request_to_wmcontrol:
    """
    performs the translation of an McM request to wmcontrol
    """

    def __init__(self):
        pass

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

        def efficiency(mcm_r):
            feff = mcm_r.get_attribute('generator_parameters')[-1]['filter_efficiency']
            meff = mcm_r.get_attribute('generator_parameters')[-1]['match_efficiency']
            return float(feff) * float(meff)

        if wmagent_type == 'MonteCarlo':
            # calculate eff dev
            command += ' --filter-eff %s' % ( efficiency(mcm_r) )

            command += ' --number-events %s' % (mcm_r.get_attribute('total_events'))
            command += ' --primary-dataset %s' % (mcm_r.get_attribute('dataset_name'))
        elif wmagent_type == 'MonteCarloFromGEN':
            # calculate eff dev                
            command += ' --filter-eff %s' % ( efficiency(mcm_r) )

            command += ' --input-ds %s' % (mcm_r.get_attribute('input_dataset'))

            command += ' --primary-dataset %s' % (mcm_r.get_attribute('dataset_name'))

            if mcm_r.get_attribute('block_white_list'):
                command += ' --blocks "' + ','.join(mcm_r.get_attribute('block_white_list')) + '"'
            if mcm_r.get_attribute('block_black_list'):
                command += ' --blocks_black "' + ','.join(mcm_r.get_attribute('block_black_list')) + '"'

            command += ' --number-events %s' % (mcm_r.get_attribute('total_events'))

        elif wmagent_type == 'LHEStepZero':

            command += ' --number-events %s' % (mcm_r.get_attribute('total_events'))
            command += ' --primary-dataset %s' % (mcm_r.get_attribute('dataset_name'))
            command += ' --filter-eff %s' % ( efficiency(mcm_r) )

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
