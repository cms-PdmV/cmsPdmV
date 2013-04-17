#!/usr/bin./env python
'''
[{'code': 'CAMP-Summer11-00001', 'campaign': {'campaign_type': 'Prod', 'campaign_dataMixerScenario': 'NODATAMIXER', 'campaign_swrelease': 'CMSSW_4_1_8_patch9', 'campaign_energy': '7.0', 'campaign_customizename2': None, 'campaign_nbrequests': '3446', 'campaign_comments': {'comment': {'date': '21/08/2012 10:49:53', 'body': 'Start ACCEPT , Removed X0Max;X0Min process string names'}, 'id': '178'}, 'campaign_customizename1': None, 'campaign_generators':
'pythia6;pythia8;herwig6;herwigpp;madgraph;alpgen;sherpa;powheg;pomwig;exhume;comphep;other', 'campaign_id': 'Summer11', 'campaign_pileupScenario': 'NoPileUp', 'campaign_conditions': 'START311_V2;MC_311_V2;DESIGN311_V2', 'campaign_description': 'Production targeted to 2011 dataset', 'campaign_sequence2': None, 'campaign_customizefunction1': None, 'campaign_customizefunction2': None, 'campaign_status': 'Started', 'campaign_sequence1': 'GEN,SIM --beamspot
Realistic7TeV2011Collision'}}]

'''

#convert comma separated strings in prep1 in lists for prep2
def splitPrep1String(thestring):
    if not thestring:
        return []
    stringsplit = thestring.split(',')
    li=[]
    for step in stringsplit:
        item = step.split(' ', 1)[0]
        li.append(item)
    return li


def convert(obj):

    prep2 = {}
    for ob in obj:

        camp = ob['campaign']

        prep2['prepid'] = camp['campaign_id'].replace('_', '')
        prep2['_id'] = prep2['prepid']

        prep2['type'] = camp['campaign_type']
        if prep2['type'] == 'Prod' or prep2['type'] == 'LHE':
            prep2['root'] = 0
        else:
            prep2['root'] = 1
        prep2['cmssw_release'] = camp['campaign_swrelease']
        prep2['energy'] = float(camp['campaign_energy'])
        prep2['generators'] = camp['campaign_generators'].split(';') if camp['campaign_generators'] else []

        prep2['description'] = camp['campaign_description']
        prep2['status'] = camp['campaign_status'].lower()
        prep2['history'] = camp['comments']

        customize1 = splitPrep1String(camp['campaign_customizename1'])
        customizeF1 =splitPrep1String(camp['campaign_customizefunction1'])
        cust1 = []
        for index in range(len(customize1)):
            cust1.append(customize1[index].split('.py')[0]+'.'+customizeF1[index])

        customize2 = splitPrep1String(camp['campaign_customizename2'])
        customizeF2 =splitPrep1String(camp['campaign_customizefunction2'])
        cust2 = []
        for index in range(len(customize2)):
            cust2.append(customize2[index].split('.py')[0]+'.'+customizeF2[index])


        # split sequences
        se1 = {}
        tok1 = camp['campaign_sequence1'].split('--')
        for tok in tok1:
            if ',' in tok:
                se1['step'] = splitPrep1String(tok.strip())
            else:
                atts = tok.split(' ')
                if len(atts) > 1:
                    se1[atts[0].strip('--')] = atts[1]
                else:
                    se1[atts[0].strip('--')] = ""

        se2 = {}
        tok2 = camp['campaign_sequence1'].split(' ')
        for tok in tok2:
            if ',' in tok:
                se2['step'] = splitPrep1String(tok)
            else:
                atts = tok.split(' ')
                if len(atts) > 1:
                    se2[atts[0].strip('--')] = atts[1]
                else:
                    se2[atts[0].strip('--')] = ""

        pu = camp['campaign_pileupScenario']
        if ';' in pu:
            pu = pu.split(';')[0]

        con = camp['campaign_conditions']
        if ';' in con:
            con = con.split(';')[0]

        prep2['sequences'] = [{'default':{'index':0, "slhc": "", "pileup": pu, "beamspot":"", "magField": "", "step": splitPrep1String(camp['campaign_sequence1']), "datatier": ['GEN-SIM'],"scenario": "", "geometry": "", "customise": cust1, "datamix": camp['campaign_dataMixerScenario'], "eventcontent": ['RAWSIM'], "conditions": con}}]

        if camp['campaign_sequence2']:
            prep2['sequences'].append({'default':{'index':0, "slhc": "", "pileup": pu,"beamspot":"", "magField": "", "step": splitPrep1String(camp['campaign_sequence2']), "datatier":'', "scenario": "", "geometry": "", "customise": cust2, "datamix": camp['campaign_dataMixerScenario'], "eventcontent": '', "conditions":con}})

        for i, seq in enumerate(prep2['sequences']):
            for att in seq['default']:
                if i == '1':
                    if att in se1:
                        seq['default'][att] = se1[att]
                elif i == '2':
                    if att in se2:
                        seq['default'][att] = se2[att]

        return prep2


if __name__=='__main__':
    import json
    print json.dumps(convert(json.loads(open('Summer11.json').read())), indent=4)
