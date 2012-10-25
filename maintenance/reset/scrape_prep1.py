#!/usr/bin/env python

# import MySQL connector for python
import MySQLdb

# json lib is only used for visualization of data
import json

# MySQL db and cursor for queries init (cursor is set to json)
db = MySQLdb.connect(host="devdb",user="prepdb", passwd="Testprepdb", db="MonteCarlo")
cursor = db.cursor(cursorclass=MySQLdb.cursors.DictCursor)

# returns the campaign primary key corresponding to the given campaign name
def get_campaign_key(campaign_name):
    q = 'select name, PrKeyPF from Campaign;'
    cursor.execute(q)
    camp_codes = cursor.fetchall()
    
    for ccode in camp_codes:
        if campaign_name == ccode['name']:
            return ccode['PrKeyPF']
    return -1  

# return the requests belonging to the given campaign 
def get_requests(campaign_name, limit=-1, constraints = ''): 

    results = []

    # find campaign key
    ckey = get_campaign_key(campaign_name)
    if ckey == -1:
        print 'Error: Campaign ' + str(campaign_name) + ' does not exist'
        return []   
    
    # find all requests that are are connected to another request (MCDBid != -1) 
    # limit 10 => returns only the first 10 requests
    q1 = 'select PrKeyPF from Request where campaignKey = '+str(ckey)
    if constraints:
        q1 += ' and ' + constraints
    if limit > 0:
        q1 += ' limit '+str(limit)
    q1 += ';'   

    # execute query
    cursor.execute(q1)

    # get all rows returned
    allrequests = cursor.fetchall()

    # iterate through all requests
    for req in allrequests:
    
        # find primary key      
        prk = req["PrKeyPF"]

        # build query that returns all information about a request in a single json (2 joins: Resources, Options)   
        q2 = 'select * from RequestResourcesRel left join Request on RequestResourcesRel.onRequest = Request.PrKeyPF left join Resources on RequestResourcesRel.resources = Resources.PrKeyPF left join RequestOptions on RequestResourcesRel.onRequest = RequestOptions.forRequest where Request.PrKeyPF='+str(prk)+';' 
    
        # execute query
        cursor.execute(q2)  
    
        # append campaign name in the json
        rows = cursor.fetchone()
        rows['member_of_campaign'] = campaign_name
        
        # collect results
        results.append(rows)

    return results     

#convert comma separated strings in prep1 in lists for prep2    
def splitPrep1String(thestring):
    stringsplit = string.split(',')
    li=[]
    for step in stringsplit:
      item = step.split(' ', 1)[0]
      li.append(item)
    return li  

# convert the json returned by the cursor to a request object in prep2 db 
def morph_requests(request_list):
    return map(lambda x: re_morph(x), request_list) 

# aux: converts the date format to the prep2 date format
def convert_date(date,  time=''):
    if '-' in date:
        return date
    toks = date.rsplit('/')
    new_date = ''
    for tok in reversed(toks):
        new_date += tok + '-' 
    toks = new_date.rsplit('-')
    if not time:
        for i in xrange(6-len(toks)):
            new_date += '0-'
    else:
        toks = time.rsplit(':')
        for i in reversed(range(len(toks)-1)):
            new_date += toks[i] + '-' 
    return new_date.rstrip('-')

# aux: internal conversion of json of mysql to prep2 json
def re_morph(req_json):
    new = {}
    new['_id'] = req_json['code']
    new['prepid'] = req_json['code']
    new['priority'] = req_json['priority']
    new['status'] = req_json['status']  
    new['completion_date'] = ''
    new['cmssw_release'] = req_json['swrelease']    
    new['input_filename'] = req_json['inputFileName']
    new['pwg'] = req_json['pwg']
    new['validation'] = req_json['validation']
    new['dataset_name'] = req_json['dataSetName']
    new['pileup_dataset_name'] = req_json['pileupDataSetName']
    new['www'] = req_json['www']
    new['process_string'] = req_json['processStr']
    new['input_block'] = req_json['inputBlock']
    new['cvs_tag'] = req_json['cvsTag']
    new['pvt_flag'] = req_json['PVTflag']
    new['pvt_comment'] = req_json['PVTcomment']
    new['mcdb_id'] = req_json['MCDBid']
    new['notes'] = req_json['notes']
    new['description'] = req_json['description']
    new['remarks'] = req_json['remarks']
    new['completed_events'] = -1
    new['total_events'] = req_json['nbEvents']
    new['member_of_chain'] = []
    new['member_of_campaign'] = req_json['member_of_campaign']
    new['time_event'] = req_json['timeEvent']
    new['size_event'] = req_json['sizeEvent']
    new['nameorfragment'] = req_json['genFragment']
    new['version'] = 0
    new['type'] = req_json['type']
    new['generators'] = req_json['generators']

    new['submission_details'] = { 'author_name': req_json['authorName'], 'author_cmsid' : req_json['authorCMSid'], 'author_inst_code': req_json['authorInstCode'], 'submission_date': convert_date(req_json['requestDate'].split(' ')[0], req_json['requestDate'].split(' ')[1]), 'author_project': ''}

    new['comments'] = []  

    customize1 = splitPrep1String(req_json['customizeName1'])
    customizeF1 = splitPrep1String(req_json['customizeFunction1'])
    cust1 = []
    for index in range(len(customize1)):
      cust1.append(customize1[index].split('.py')[0]+'.'+customizeF1[index])

    customize2 = splitPrep1String(req_json['customizeName2'])
    customizeF2 = splitPrep1String(req_json['customizeFunction2'])
    cust2 = []
    for index in range(len(customize2)):
      cust2.append(customize2[index].split('.py')[0]+'.'+customizeF2[index]) 

    new['sequences'] = [{'index':0, "slhc": "", "pileup_scenario": req_json['pileupScenario'], "beamspot": "Realistic8TeVCollision", "magnetic_field": "", "step": splitPrep1String(req_json['sequence1']), "data_tier": splitPrep1String(req_json['dataTier1']), "scenario": "", "geometry": "", "customise": cust1, "datamix": "", "event_content": splitPrep1String(req_json['eventContent1']), "conditions": req_json['conditions']},{'index':1, "slhc": "", "pileup_scenario": req_json['pileupScenario'], "beamspot": "Realistic8TeVCollision", "magnetic_field": "", "step": splitPrep1String(req_json['sequence2']), "data_tier": splitPrep1String(req_json['dataTier2']), "scenario": "", "geometry": "", "customise": cust2, "datamix": "", "event_content": splitPrep1String(req_json['eventContent2']), "conditions": req_json['conditions']}]
    
    #[{'index':0, 'step': req_json['step'], 'beamspot':'', 'geometry':'', 'magnetic_field':'', 'conditions':[req_json['conditions']], 'pileup_scenario':[req_json['pileupScenario']], 'datamixer_scenario':[req_json['dataMixerScenario']], 'scenario':'', 'customize_name':req_json['customizeName1'], 'customize_function':req_json['customizeFunction1'], 'slhc':'', 'event_content':[req_json['eventContent']], 'data_tier':[req_json['dataTier']], 'sequence':[req_json['sequence1']]}, {'index':1, 'step': req_json['step'], 'beamspot':'', 'geometry':'', 'magnetic_field':'', 'conditions':[req_json['conditions']], 'pileup_scenario':[req_json['pileupScenario']], 'datamixer_scenario':[req_json['dataMixerScenario']], 'scenario':'', 'customize_name':req_json['customizeName2'], 'customize_function':req_json['customizeFunction2'], 'slhc':'', 'event_content':[req_json['eventContent']], 'data_tier':[req_json['dataTier']], 'sequence':[req_json['sequence2']]} ]

    new['generator_parameters'] = [{'version':0, 'submission_details':{'author_name':'automatic'}, 'cross_section':req_json['crossSection'], 'filter_efficiency': req_json['filterEff'], 'filter_efficiency_error': req_json['filterEffError'], 'match_efficiency': req_json['matchEff'], 'match_efficiency_error': -1}] 

    new['reqmgr_name'] = []

    new['approvals'] = build_approvals(req_json['approvals']) # a list
    new['update_details'] = []  

    return new

def build_approvals(appstr):
    
    res = []    

    if ':' in appstr:
        toks = appstr.split(':')
        for i in range(len(toks)):
            appstep = toks[i]
            if 'GEN' in toks[i]:
                appstep = 'gen'
            elif 'Defined' in toks[i]:
                appstep = 'defined'
            elif 'SUBMIT' in toks[i]:
                appstep = 'inject'
            elif 'Done' in toks[i]:
                appstep = 'approved'
             
            app = {'index':i, 'approval_step': appstep, 'approver':{}}
            res.append(app)
    else:
        appstep = appstr
        if 'GEN' in appstr:
            appstep = 'gen' 
        elif 'Defined' in appstr:
            appstep = 'defined' 
        elif 'SUBMIT' in appstr:
            appstep = 'inject'
        elif 'Done' in appstr:
            appstep = 'approved'

        res.append({'index':0, 'approval_step':appstep, 'approver':{}}) 
    
    return res

# retrieve a campaign
def get_campaign(campaign_name):
    
    # results holder
    results = []

    # find campaign key
    ckey = get_campaign_key(campaign_name)
    if ckey == -1:
        print 'Error: Campaign ' + str(campaign_name) + ' does not exist'
        return []
    
    # build query to get the campaign details
    q1 = 'select * from Campaign where PrKeyPF = '+str(ckey)+';'
    
    # execute the query
    cursor.execute(q1)

    # get all rows returned
    camp = cursor.fetchone()
    
    return camp
    
def morph_campaign(camp):
    new = {}
    
    if not camp:
        return new
    
    new['_id'] = camp['name']
    new['prepid'] = camp['name']
    new['start_date'] = convert_date(camp['startDate'])
    new['end_date'] = convert_date(camp['endDate'])
    new['energy'] = camp['energy']
    new['type'] = [camp['type']]
    new['next'] = []
    new['production_type'] = camp['prodType']
    new['cmssw_release'] = [camp['swrelease']]
    new['description'] = camp['description']
    new['remarks'] = camp['remarks']
    new['status'] = camp['status']
    new['validation'] = camp['validation']
    new['pileup_dataset_name'] = camp['pileupDataSetName'].split(';')
    new['process_string'] = camp['processStr'].split(';')
    new['generators'] = [camp['generators']]
    new['input_filename'] = camp['inputFileName']
    new['www'] = camp['www']
    new['completed_events'] = -1
    new['total_events'] = camp['nbEvt']
    if 'LHE' in new['_id']:
        new['root'] = 0 # root
    elif 'DR' in new['_id']:
        new['root'] = 1 # non root
    else:
        new['root'] = -1 # possible root
    new['sequences'] = [{'index':0, 'step': -1, 'beamspot':'', 'geometry':'', 'magnetic_field':'', 'conditions':[camp['conditions']], 'pileup_scenario':[camp['pileupScenario']], 'datamixer_scenario':[camp['dataMixerScenario']], 'scenario':'', 'customize_name':camp['customizeName1'], 'customize_function':camp['customizeFunction1'], 'slhc':'', 'event_content':[camp['eventContent']], 'data_tier':[camp['dataTier']], 'sequence':[camp['sequence1']]}, {'index':1, 'step': -1, 'beamspot':'', 'geometry':'', 'magnetic_field':'', 'conditions':[camp['conditions']], 'pileup_scenario':[camp['pileupScenario']], 'datamixer_scenario':[camp['dataMixerScenario']], 'scenario':'', 'customize_name':camp['customizeName2'], 'customize_function':camp['customizeFunction2'], 'slhc':'', 'event_content':[camp['eventContent']], 'data_tier':[camp['dataTier']], 'sequence':[camp['sequence2']]} ]
    new['submission_details'] = { 'author_name': camp['authorName'], 'author_cmsid' : camp['authorCMSid'], 'author_inst_code': camp['authorInstCode'], 'submission_date': convert_date(camp['campaignDate']), 'author_project': ''}
    new['approvals'] = [{'index':0, 'approval_step':'start', 'approver':{}}] if 'Start' in camp['approvals'] else [{'index':0, 'approval_step':'start', 'approver':{}},{'index':1, 'approval_step':'stop', 'approver':{}}]    
    new['comments'] = []
    
    return new


# auto magic wrapper to get a campaign
def retrieve_campaign(campaign_name):
    return morph_campaign(get_campaign(campaign_name))
        
# auto magic wrapper for get_requests
def retrieve_requests(campaign_name, limit=-1, constraints=''):
    return morph_requests(get_requests(campaign_name, limit, constraints))
    

if __name__=='__main__':

    import os

    datadir = 'data/'

    #camps = ['Summer12_LHE', 'Summer12', 'Summer12_DR53X']
    camps = ['Summer12', 'Summer12_DR53X']
    for camp in camps:
        
        
        # create dedicated directory for campaigns
        if not os.path.exists(datadir + 'campaigns/'):
            os.makedirs(datadir + 'campaigns/')  
        
        # get campaign
        c = retrieve_campaign(camp)
        if c:
            f = open(datadir + 'campaigns/'+ c['_id'], 'w')
            f.write(json.dumps(c))
            f.close()                     
        
        # created dedicated directory for requests
        if not os.path.exists(datadir + 'requests/'):
            os.makedirs(datadir + 'requests/')
                
        res = get_requests(camp, limit=1, constraints='MCDBid != -1')
        final = morph_requests(res)
        print final

        #for r in final:
        #    f = open(datadir + 'requests/' + r['_id'], 'w')
        #    f.write(json.dumps(r))
        #    f.close()        
