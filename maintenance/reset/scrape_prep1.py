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
	new['gen_fragment'] = req_json['genFragment']
	new['version'] = 0
	new['type'] = req_json['type']
	new['generators'] = req_json['generators']

	new['submission_details'] = { 'author_name': req_json['authorName'], 'author_cmsid' : req_json['authorCMSid'], 'author_inst_code': req_json['authorInstCode'], 'submission_date': convert_date(req_json['requestDate'].split(' ')[0], req_json['requestDate'].split(' ')[1]), 'author_project': ''}

	new['comments'] = []  

	new['sequences'] = [{'index':0, 'step': req_json['step'], 'beamspot':'', 'geometry':'', 'magnetic_field':'', 'conditions':[req_json['conditions']], 'pileup_scenario':[req_json['pileupScenario']], 'datamixer_scenario':[req_json['dataMixerScenario']], 'scenario':'', 'customize_name':req_json['customizeName1'], 'customize_function':req_json['customizeFunction1'], 'slhc':'', 'event_content':[req_json['eventContent']], 'data_tier':[req_json['dataTier']], 'sequence':[req_json['sequence1']]}, {'index':1, 'step': req_json['step'], 'beamspot':'', 'geometry':'', 'magnetic_field':'', 'conditions':[req_json['conditions']], 'pileup_scenario':[req_json['pileupScenario']], 'datamixer_scenario':[req_json['dataMixerScenario']], 'scenario':'', 'customize_name':req_json['customizeName2'], 'customize_function':req_json['customizeFunction2'], 'slhc':'', 'event_content':[req_json['eventContent']], 'data_tier':[req_json['dataTier']], 'sequence':[req_json['sequence2']]} ]

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
	
if __name__=='__main__':

	import os

	datadir = 'data/'

	#camps = ['Summer12_LHE', 'Summer12', 'Summer12_DR53X']
	camps = ['Summer12']
	for camp in camps:

		# created dedicated directory for each campaign
		if not os.path.exists(datadir + 'requests/'+camp):
			os.makedirs(datadir + 'requests/'+camp)
				
		res = get_requests(camp, limit=10, constraints='MCDBid != -1')
		final = morph_requests(res)

		for r in final:
			f = open(datadir + 'requests/' + camp + '/' + r['_id'], 'w')
			f.write(json.dumps(r))
			f.close()		 
	
