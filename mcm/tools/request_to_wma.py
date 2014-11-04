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

    def get_chain_dict(self, arg0):
        crdb = database('chained_requests')
        rdb = database('requests')
        def request_to_tasks( r , base, depend):
            events_per_lumi = settings().get_value('events_per_lumi')
            ts=[]
            for si in range(len(r.get_attribute('sequences'))):
                task_dict={"TaskName": "%s_%d"%( r.get_attribute('prepid'), si),
                           "KeepOutput" : True,
                           "ConfigCacheID" : None,
                           "GlobalTag" : r.get_attribute('sequences')[si]['conditions'],
                           "CMSSWVersion" : r.get_attribute('cmssw_release'),
                           "ScramArch": r.get_scram_arch(),
                           "PrimaryDataset" : r.get_attribute('dataset_name'),
                           "AcquisitionEra" : r.get_attribute('member_of_campaign'),
                           "ProcessingString" : r.get_processing_string(si),
                           "ProcessingVersion" : r.get_attribute('version'),
                           "TimePerEvent" : r.get_attribute("time_event"),
                           "SizePerEvent" : r.get_attribute('size_event'),
                           "Memory" : r.get_attribute('memory'),
                           "FilterEfficiency" : r.get_efficiency()
                           }
                
                if len(r.get_attribute('config_id'))>si:
                    task_dict["ConfigCacheID"] = r.get_attribute('config_id')[si]

                if len(r.get_attribute('keep_output'))>si:
                    task_dict["KeepOutput"] = r.get_attribute('keep_output')[si]

                if r.get_attribute('pileup_dataset_name'):
                    task_dict["MCPileup"] = r.get_attribute('pileup_dataset_name')
                    
                if si==0:
                    if base:
                        task_dict.update({"SplittingAlgo"  : "EventBased",
                                          "RequestNumEvents" : r.get_attribute('total_events'),
                                          "Seeding" : "AutomaticSeeding",
                                          "EventsPerLumi" : events_per_lumi,
                                          "LheInputFiles" : r.get_attribute('mcdb_id')>0
                                          })
                        ## temporary work-around for request manager not creating enough jobs
                        ## https://github.com/dmwm/WMCore/issues/5336
                        ## inflate requestnumevents by the efficiency to create enough output
                        max_forward_eff = r.get_forward_efficiency()
                        task_dict["EventsPerLumi"] /= task_dict["FilterEfficiency"] #should stay nevertheless as it's in wmcontrol for now
                        task_dict["EventsPerLumi"] /= max_forward_eff #this does not take its own efficiency
                        task_dict["RequestNumEvents"] /= task_dict["FilterEfficiency"] #should disappear with the above getting resolved

                    else:
                        if depend:
                            task_dict.update({"SplittingAlgo"  : "EventAwareLumiBased",
                                              "InputFromOutputModule" : None,
                                              "InputTask" : None})
                        else:
                            task_dict.update({"SplittingAlgo"  : "EventAwareLumiBased",
                                              "InputDataset" : r.get_attribute('input_dataset')})
                else:
                    task_dict.update({"SplittingAlgo"  : "EventAwareLumiBased",
                                      "InputFromOutputModule" : ts[-1]['output_'],
                                      "InputTask" : ts[-1]['TaskName']})
                task_dict['output_'] = "%soutput"%(r.get_attribute('sequences')[si]['eventcontent'][0])
                task_dict['priority_'] = r.get_attribute('priority')
                task_dict['request_type_'] = r.get_wmagent_type()
                ts.append(task_dict)    
            return ts

        if not crdb.document_exists( arg0 ):
            ## it's a request actually, pick up all chains containing it
            mcm_r = rdb.get( arg0 )
            #mcm_crs = crdb.query(query="root_request==%s"% arg0) ## not only when its the root of
            mcm_crs = crdb.query(query="contains==%s"% arg0)
            task_name = 'task_'+arg0
        else:
            mcm_crs = [crdb.get( arg0 )]
            task_name = arg0

        if len(mcm_crs)==0:  return {}
            
        tasktree = {}
        ignore_status=False
        
        if 'scratch' in argv:
            ignore_status = True
        veto_point=None
        if 'upto' in argv:
            veto_point=int(argv['upto'])

        for mcm_cr in mcm_crs:
            starting_point=mcm_cr['step']
            if ignore_status: starting_point=0
            for (ir,r) in enumerate(mcm_cr['chain']):
                if (ir<starting_point) : 
                    continue ## ad no task for things before what is already done
                if veto_point and (ir>veto_point):
                    continue
                mcm_r = request( rdb.get( r ) )
                if mcm_r.get_attribute('status')=='done' and not ignore_status:
                    continue

                if not r in tasktree:
                    tasktree[r] = { 
                        'next' : [],
                        'dict' : [],
                        'rank' : ir
                        }
                base=(ir==0) ## there is only one that needs to start from scratch
                depend=(ir>starting_point) ## all the ones later than the starting point depend on a previous task
                if ir<(len(mcm_cr['chain'])-1):
                    tasktree[r]['next'].append( mcm_cr['chain'][ir+1])

                tasktree[r]['dict'] = request_to_tasks( mcm_r, base, depend)

        for (r,item) in tasktree.items():
            for n in item['next']:
                tasktree[n]['dict'][0].update({"InputFromOutputModule" : item['dict'][-1]['output_'],
                                                       "InputTask" : item['dict'][-1]['TaskName']})

        wma={
            "RequestType" : "TaskChain",
            "inputMode" : "couchDB",
            "Group" : "ppd",
            "Requestor": "pdmvserv",
            "OpenRunningTimeout" : 43200,
            "TaskChain" : 0,
            "ProcessingVersion": 1,
            "RequestPriority" : 0,
            "SubRequestType" : "MC" 
            }

        task=1
        for (r,item) in sorted(tasktree.items(), key=lambda d: d[1]['rank']):
            for d in item['dict']:
                if d['priority_'] > wma['RequestPriority']:  wma['RequestPriority'] = d['priority_']
                if d['request_type_'] in ['ReDigi']:  wma['SubRequestType'] = 'ReDigi'
                for k in d.keys():
                    if k.endswith('_'):
                        d.pop(k)
                wma['Task%d'%task] = d
                task+=1
        wma['TaskChain'] = task-1

        if wma['TaskChain'] == 0:
            return {}
        
        for item in ['CMSSWVersion','ScramArch','TimePerEvent','SizePerEvent','GlobalTag','Memory']:
            wma[item] = wma['Task%d'% wma['TaskChain']][item]

        wma['Campaign' ] = wma['Task1']['AcquisitionEra']
        wma['PrepID' ] = task_name
        wma['RequestString' ] = wma['PrepID']
        return wma



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
            match_by_lumi = True
            if match_by_lumi:
                (lumimask,stat) = dbs3.match_stats_by_lumi( mcm_r.get_attribute('input_dataset'), 
                                                            mcm_r.get_attribute('total_events'),
                                                            0.05)#match within 5%
                schema['LumiList'] = lumimask
            else:
                blocks = dbs3.match_stats_by_block( mcm_r.get_attribute('input_dataset'), 
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
