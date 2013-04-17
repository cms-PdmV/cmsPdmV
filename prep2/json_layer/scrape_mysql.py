#!/usr/bin/env python 

import MySQLdb
import simplejson
from request import request
from campaign import campaign
from approval import approval
from json_base import submission_details
from comment import comment

# MySQL db and cursor for queries init
db = MySQLdb.connect(host="devdb", user="prepdb", passwd="Testprepdb", db="MonteCarlo")
cursor = db.cursor(cursorclass=MySQLdb.cursors.DictCursor)

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
convert_date('2012/03/27', '23:12:21')

def get_campaign_key(campid):
    q_get_campkey = 'select PrKeyPF from Campaign where id=' + '\'' + str(campid) + '\';'
    cursor.execute(q_get_campkey)
    kjson = cursor.fetchone()
    
    return kjson['PrKeyPF']

# query builder
def get_all_requests(campid):
    key = get_campaign_key(campid)
    q1 = '''select Request.PrKeyPF as id, Request.priority, Request.code as prepid, Request.authorName as author_name, Request.authorCMSid as author_cmsid, Request.authorInstCode as author_inst_code,
                Request.pwg, Request.status, Request.statusFlow as status_flow, Request.validation, Request.type, Request.swrelease as cmssw_release, Request.inputFileName as input_filename, Request.dataTier as data_tier, 
                Request.eventContent as event_content, Request.genFragment as gen_fragment, Request.dataSetName as dataset_name, Request.pileupDatasetName as pileup_dataset_name, Request.www,
                Request.processStr as process_string, Request.inputBlock as input_block, Request.preSteps as pre_steps, Request.cvsTag as cvs_tag, Request.inputCMSgen as input_cms_gen, Request.PVTflag as pvt_flag,
                Request.PVTcomment as pvt_comment, Request.conditions, Request.generators, Request.pileupScenario as pileup_scenario, Request.datamixerScenario as datamixer_scenario, Request.MCDBid as mcdb_id,
                Request.notes, Request.description, Request.remarks, Request.approvals, Request.runRange as run_range, Request.ALCA as alca, Request.SKIM as skim, Request.SKIMinput as skim_input, Request.cmsGEn as cms_gen,
                Request.cmsGENfile as cms_gen_file, requestDate as submission_date
                from Request where campaignKey=''' + str(key) + ';'
    q2 = '''select customizeName1 as customize_name, customizeFunction1 as customize_function, sequence1 as sequence, kcustomizeName1 as kcustomize_name,
                kcustomizeFunction1 as kcustomize_function, ksequence1 as ksequence from Request where code='''
    q3 = '''select customizeName2 as customize_name, customizeFunction2 as customize_function, sequence2 as sequence, kcustomizeName2 as kcustomize_name,
                kcustomizeFunction2 as kcustomize_function, ksequence2 as ksequence from Request where code='''
    q4 = '''select step from RequestOptions where forRequest='''
    q5 = '''select nbEvents as total_events, nbEventsCompleted as completed_events, timeEvent as time_event, sizeEvent as size_event, TP as tp, unit 
                from Resources where forRequest='''
    q6 = '''select version, ptMax as pt_max, ptMin as pt_min, ptHatMax as pt_hat_max, ptHatMin as pt_hat_min, sHatMax as s_hat_max, sHatMin as s_hat_min, mInvMin as m_inv_min,
                mInvMax as m_inv_max,crossSection as cross_section, filterEff as filter_efficiency, filterEffError as filter_efficiency_error, matchEff as match_efficiency,
                updateDate as submission_date, updaterCMSid as author_cmsid, updaterName as author_name, updaterInstCode as author_inst_code, updaterProject as author_project
                from Resources where forRequest=24445'''
    q7 = '''select authorCMSid as author_cmsid, authorName as author_name, authorInstCode as author_inst_code, commentDate as submission_date, body as message
                from Comment where forKey='''
    q8 = '''select cmsid as author_cmsid, name as author_name, instCode as author_inst_code, project as approval_step, approvalDate as submission_date
                from ApprovalStep where status="OK" and forKey='''
    
    cursor.execute(q1)
    requests = cursor.fetchall()
    for req in requests:
        prepid = '\'' + req['prepid'] + '\';'
        key = str(req['id']) + ';'
        sequences = []
        approvals = []
        gen_params = []
        comments = []

        # get approvals
        cursor.execute(q8+key)
        apps = cursor.fetchall()
        for app in apps:
            appro = approval(app['author_name'],  app['author_cmsid'],  app['author_inst_code'])
            subby = appro.get_attribute('approver')
            subby['submission_date'] = convert_date(app['submission_date'])
            appro.set_attribute('approver', subby)
            a = appro.build(app['approval_step'])
            approvals.append(a)

        # custs
        # get seq1
        cursor.execute(q2+prepid)
        seq1 = cursor.fetchone()
        seq = {'index':1}
        custname = []
        custfunc = []
        sequ = ''
        for assoc_key in seq1:
            if 'customizeName' in assoc_key:
                if seq1[assoc_key]:
                    custname.append(seq1[assoc_key])
            if 'customizeFunction' in assoc_key:
                if seq1[assoc_key]:
                    custfunc.append(seq1[assoc_key])
            if 'sequence' in assoc_key:
                sequ = seq1[assoc_key]
            seq['customize_name'] = custname
            seq['customize_function'] = custfunc
            seq['sequence'] = sequ
        sequences.append(seq)

        # get seq2
        cursor.execute(q3+prepid)
        seq2 = cursor.fetchone()
        seq = {'index':1}
        custname = []
        custfunc = []
        sequ = ''
        for assoc_key in seq2:
            if 'customizeName' in assoc_key:
                if seq2[assoc_key]:
                    custname.append(seq2[assoc_key])
            if 'customizeFunction' in assoc_key:
                if seq2[assoc_key]:
                    custfunc.append(seq2[assoc_key])
            if 'sequence' in assoc_key:
                sequ = seq2[assoc_key]
            seq['customize_name'] = custname
            seq['customize_function'] = custfunc
            seq['sequence'] = sequ
        sequences.append(seq)

        # options
        cursor.execute(q4+key)
        ops = cursor.fetchall()
        req['step'] = ops[-1]['step'] # get latest

        # resources (main)
        cursor.execute(q5+key)
        ress = cursor.fetchall() 
        res = ress[-1] # get latest
        for assoc_key in res:
            req[assoc_key] = res[assoc_key]

        # gen parameters
        cursor.execute(q6+key)
        gens = cursor.fetchall()
        for gen in gens:
            if not gen['author_name']:
                gen['author_name'] = req['author_name']
            s = submission_details().build(gen['author_name'],  gen['author_cmsid'],  gen['author_inst_code'],  gen['author_project'])
            s['submission_date'] = gen['submission_date']
            gen['submission_details'] = s
            g = generator_parameters(gen['author_name'])
            for assoc_key in gen:
                try:
                    g.set_attribute(assoc_key,  gen[assoc_key])
                except Exception as ex:
                    continue
            gen_params.append(g.json())

        # get comments
        cursor.execute(q7 + key)
        comms = cursor.fetchall()
        for comm in comms:
            c = comment(comm['author_name'],  comm['author_cmsid'],  comm['author_inst_code']).build(comm['message'])
            temp = c['submission_details']
            temp['submission_date'] = convert_date(comm['submission_date'])
            c['submission_details'] = temp
            comments.append(c)

        # build request
        rt = request(req['author_name'],  req['author_cmsid'],  req['author_inst_code'])
        s = rt.get_attribute('submission_details')
        date, time = req['submission_date'].rsplit(' ')
        s['submission_date'] = convert_date(date,  time)
        rt.set_attribute('submission_details',  s)
        rt.set_attribute('approvals',  approvals)
        rt.set_attribute('sequences',  sequences)
        rt.set_attribute('generator_parameters',  gen_params)
        rt.set_attribute('comments',  comments)

        for assoc_key in req:
            try:
                if assoc_key == 'approvals':
                    continue
                rt.set_attribute(assoc_key, req[assoc_key])
            except Exception as ex:
                continue
#        rt.print_self()
#        print 
#        print '###########################################'
#        print        

        yield rt

def get_campaign(campid):
    key = get_campaign_key(campid)
    q1 = '''select id as prepid, authorName as author_name,startDate as start_date, endDate as end_date, energy, type, prodType as production_type, 
    reprType as repr_type, swrelease as cmssw_release, description, remarks, validation, pileupDatasetName as pileup_dataset_name, 
    processStr as process_string, conditions, generators, pileupScenario as pileup_scenario, datamixerScenario as datamixer_scenario, inputFileName as input_filename, 
    www, preSteps as pre_steps, dataTier as data_tier, eventContent as event_content, nbEvt as total_events, nbEvtCompleted as completed_events, approvals, 
    authorCMSid as author_cmsid, authorInstCode as author_inst_code
    from Campaign where id=''' + '\'' + str(campid) + '\';'

    q2 = '''select sequence1 as sequence,  customizeName1 as customize_name,  customizeFunction1 as customize_function from Campaign where id=''' + '\'' + str(campid) + '\';'
    q3  = '''select sequence2 as sequence,  customizeName2 as customize_name,  customizeFunction2 as customize_function from Campaign where id=''' + '\'' + str(campid) + '\';'
    q4 = '''select authorCMSid as author_cmsid, authorName as author_name, authorInstCode as author_inst_code, commentDate as submission_date, body as message
                from Comment where forKey=''' + str(key) + ';'
    q5 = '''select cmsid as author_cmsid, name as author_name, instCode as author_inst_code, project as approval_step, approvalDate as submission_date
                from ApprovalStep where status="OK" and forKey=''' + str(key) + ';'
    approvals = []
    sequences = []
    comments = []
    
    
    # get campaign
    cursor.execute(q1)
    camp_json = cursor.fetchone()
    
    # get comments
    cursor.execute(q4)
    comms = cursor.fetchall()
    for comm in comms:
        c = comment(comm['author_name'],  comm['author_cmsid'],  comm['author_inst_code']).build(comm['message'])
        temp = c['submission_details']
        date, time = comm['submission_date'].rsplit(' ')
        temp['submission_date'] = convert_date(date, time)
        c['submission_details'] = temp
        comments.append(c)
        
    # custs
    # get seq1
    cursor.execute(q2)
    seq1 = cursor.fetchone()
    seq = {'index':1}
    custname = []
    custfunc = []
    sequ = ''
    for assoc_key in seq1:
        if 'customizeName' in assoc_key:
            if seq1[assoc_key]:
                custname.append(seq1[assoc_key])
        if 'customizeFunction' in assoc_key:
            if seq1[assoc_key]:
                custfunc.append(seq1[assoc_key])
        if 'sequence' in assoc_key:
            sequ = seq1[assoc_key]
        seq['customize_name'] = custname
        seq['customize_function'] = custfunc
        seq['sequence'] = sequ
    sequences.append(seq)
    
    # get seq2
    cursor.execute(q3)
    seq2 = cursor.fetchone()
    seq = {'index':1}
    custname = []
    custfunc = []
    sequ = ''
    for assoc_key in seq2:
        if 'customizeName' in assoc_key:
            if seq2[assoc_key]:
                custname.append(seq2[assoc_key])
        if 'customizeFunction' in assoc_key:
            if seq2[assoc_key]:
                custfunc.append(seq2[assoc_key])
        if 'sequence' in assoc_key:
            sequ = seq2[assoc_key]
        seq['customize_name'] = custname
        seq['customize_function'] = custfunc
        seq['sequence'] = sequ
    sequences.append(seq)
    
    # get approvals
    allowed = ['SIM',  'HLT',  'L1',  'ALCA',  'RECO',  'Start'] # campaign hack
    cursor.execute(q5)
    apps = cursor.fetchall()
    for app in apps:
        appro = approval(app['author_name'],  app['author_cmsid'],  app['author_inst_code'])
        subby = appro.get_attribute('approver')
        subby['submission_date'] = convert_date(app['submission_date'])
        appro.set_attribute('approver', subby)
        if app['approval_step'] not in allowed:
            allowed.append(app['approval_step'])
        appro.set_approval_steps(allowed)        
        a = appro.build(app['approval_step'])
        approvals.append(a)

    camp_json['approvals'] = approvals
    camp_json['sequences'] = sequences
    camp_json['comments'] = comments
    campy = campaign(camp_json['author_name'],  camp_json['author_cmsid'],  camp_json['author_inst_code'])
    #print simplejson.dumps(camp_json,  sort_keys=True, indent=4)
    for key in camp_json:
        try:
            if key == 'start_date' or key == 'end_date':
                campy.set_attribute(key,  convert_date(camp_json[key]))
                continue
            campy.set_attribute(key,  camp_json[key])
        except Exception as ex:
            continue
            
    campy.set_attribute('id',  key)
    #campy.print_self()
    return campy

def get_campaign_ids():
    q1 = 'select id from Campaign;'
    cursor.execute(q1)
    ids = cursor.fetchall()
    for id in ids:
        camp = get_campaign(id['id'])
        print camp.get_attribute('prepid')
        req = get_all_requests(id['id'])
    
        try:
            f = open('campaign_'+camp.get_attribute('prepid'),  'w')
            f.write(simplejson.dumps(camp.json()))
            f.close()
        
            for r in req:
                try:
                    f = open('request_' + camp.get_attribute('prepid')+'_'+ r.get_attribute('prepid'), 'w')
                    f.write(simplejson.dumps(r.json()))
                    f.close()
                except Exception as ex:
                    continue
        except Exception as ex:
            continue

get_campaign_ids()
db.close()

    
