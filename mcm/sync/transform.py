#!/usr/bin/env python

import json
import subprocess
import ast

class transformer:
    def __init__(self, jstr=''):
        self.data = jstr#self.__load(jstr)

# creates a python dictionary from a prep1 json string
    def __load(self, jstr=''):
        if not jstr:
            print 'Error: Did not receive any results.'
            return {}
        print jstr['code']
        try:
            self.data = ast.literal_eval(jstr)
            return self.data
        except ValueError as ex:
            print 'Error: ast module complains for '+str(ex)
            return {}

# raises ValueError if no prepid is present or the request contents
    def __validate_json(self):
        if 'request' not in self.data:
            raise ValueError('Object does not contain "request" parameter.')
        if 'code' not in self.data:
            raise ValueError('Object does not contain "code" parameter.')

# removes the annoying 'request_' part from each parameter's name and
# also, brings the prepid of the request in the prep1_json['request'] json.
    def prepare_json(self):
        new = {}
        rall = []
        try:
            pass#self.__validate_json()
        except ValueError as ex:
            print 'Error: '+str(ex)
            return {}
        for req in self.data:
            for key in req['request']:
                k = key
                if 'request_' in key:
                    k = key.split('request_')[1]
                new[k] = req['request'][key]

            new['code'] = req['code']

            rall.append(new)

        return rall#new

# re_morph() takes a prep1 json and returns a prep2 request dictionary
    def re_morph(self,req_json):
        if not req_json:
            return {}
        new = {}
        new['_id'] = req_json['code'].replace('_', '')
        new['prepid'] = req_json['code'].replace('_', '')
        new['priority'] = int(req_json['priority'])
        new['status'] = ''#req_json['status'].lower()
        p_status= req_json['status'].lower()
        if p_status == 'new':
            new['status'] = p_status
            new['approval'] = 'none'
        elif p_status == 'defined':
            new['status'] = p_status
            new['approval'] = 'validation'
        elif p_status == 'gen':
            new['status'] = 'approved'
            new['approval'] = 'submit'
        elif p_status == 'submit':
            new['status'] = 'submitted'
            new['approval'] = 'submit'
        elif p_status == 'done':
            new['status'] = p_status        
            new['approval'] = 'submit'


        new['completion_date'] = ''
        new['cmssw_release'] = req_json['swrelease']
            
        if req_json['inputfilename'] and req_json['inputfilename']!='None':
            new['input_filename'] = req_json['inputfilename']
            
        new['pwg'] = req_json['pwg']
        new['dataset_name'] = req_json['datasetname']
        if 'pileupdatasetname' in req_json and req_json['pileupdatasetname'] and req_json['pileupdatasetname']!='None':
            new['pileup_dataset_name'] = req_json['pileupdatasetname']
        else:
            new['pileup_dataset_name'] = ''
        new['www'] = ''#req_json['www']

        if 'processstr' in req_json and req_json['processstr'] and req_json['processstr'] != 'None':
            new['process_string'] = req_json['processstr']
        else:
            new['process_string'] = ''

        if 'inputblock' in req_json:
            new['input_block'] = req_json['inputblock']
        else:
            new['input_block'] = ''
        if req_json['genproductiontag'] and req_json['genproductiontag']!='None':
            new['fragment_tag'] = req_json['genproductiontag']

        new['pvt_flag'] = ''#req_json['PVTflag']
        new['pvt_comment'] = ''#req_json['PVTcomment']
        new['mcdb_id'] = int(req_json['mcdbid'])
        new['notes'] = req_json['description']
        #new['description'] = req_json['description']
        new['remarks'] = ''#req_json['remarks']
        new['completed_events'] = -1
        new['total_events'] = req_json['nbEvent']
        new['member_of_chain'] = []
        new['member_of_campaign'] = req_json['campaign_id'].replace('_', '')
        new['time_event'] = req_json['timeEvent']
        new['size_event'] = req_json['sizeEvent']
        #new['nameorfragment'] = req_json['genfragment']
        new['type'] = req_json['type']
        if new['type']!='MCReproc':
            new['name_of_fragment'] = req_json['genfragment']
        new['version'] = 0

        if req_json['generators']:
            new['generators'] = req_json['generators'].split(',')
        else:
            new['generators'] = []
        new['block_black_list'] = []
        new['block_white_list'] = []

        #new['submission_details'] = {}#{ 'author_name': req_json['authorName'], 'author_cmsid' : req_json['authorCMSid'], 'author_inst_code': req_json['authorInstCode'], 'submission_date': self.convert_date(req_json['requestDate'].split(' ')[0], req_json['requestDate'].split(' ')[1]), 'author_project': ''}

        new['history'] = self.build_comments(req_json['comments'])
        #new['comments'] = self.build_comments(req_json['comments'])

        customize1 = self.splitPrep1String(req_json['customizename1'])
        customizeF1 = self.splitPrep1String(req_json['customizefunction1'])
        cust1 = []
        for index in range(len(customize1)):
          cust1.append(customize1[index].split('.py')[0]+'.'+customizeF1[index])

        customize2 = self.splitPrep1String(req_json['customizename2'])
        customizeF2 = self.splitPrep1String(req_json['customizefunction2'])
        cust2 = []
        for index in range(len(customize2)):
          cust2.append(customize2[index].split('.py')[0]+'.'+customizeF2[index])

        # split sequences
        se1 = {}
        tok1 = req_json['sequence1'].split('--')
        for tok in tok1:
            if ',' in tok:
                se1['step'] = self.splitPrep1String(tok.strip())
            else:
                atts = tok.split(' ')
                if len(atts) > 1:
                    se1[atts[0].strip('--')] = atts[1]
                else:
                    se1[atts[0].strip('--')] = ""

        se2 = {}
        tok2 = []
        if req_json['sequence2']:
            tok2 = req_json['sequence2'].split(' ')
        for tok in tok2:
            if ',' in tok:
                se2['step'] = self.splitPrep1String(tok.strip())
            else:
                atts = tok.split(' ')
                if len(atts) > 1:
                    se2[atts[0].strip('--')] = atts[1]
                else:
                    se2[atts[0].strip('--')] = ""

        pu  = req_json['pileupScenario']
        if pu and ';' in pu:
            pu = pu.split(';')[0]

        co = req_json['conditions']
        if co and ';' in co:
            co = co.split(';')[0]
        if co and not co.endswith('::All'):
            co+='::All'

        new['sequences'] = [{"slhc": "",
                             "pileup": pu,
                             "beamspot": "",
                             "magField": "",
                             "step": self.splitPrep1String(req_json['sequence1']),
                             "datatier": '',
                             "scenario": "",
                             "geometry": "",
                             "customise": cust1,
                             "datamix": req_json['dataMixerScenario'],
                             "eventcontent": self.splitPrep1String(req_json['eventcontent']),
                             "conditions": co}]

        if req_json['sequence2']:
            new['sequences'].append({"slhc": "",
                                     "pileup": pu,
                                     "beamspot": "",
                                     "magField": "",
                                     "step": self.splitPrep1String(req_json['sequence2']),
                                     "datatier": '',
                                     "scenario": "",
                                     "geometry": "",
                                     "customise": cust2,
                                     "datamix": "",
                                     "eventcontent": self.splitPrep1String(req_json['eventcontent']),
                                     "conditions": co})

        keep = []
        for i, seq in enumerate(new['sequences']):
            keep.append(False)
            for att in seq:
                if i == 0:
                    if att in se1:
                        seq[att] = se1[att]
                elif i == 1:
                    if att in se2:
                        seq[att] = se2[att]

        keep[-1]=True
        new['keep_output'] = keep
        ## copy a few things from the campaign sequences as it is in McM
        camp = self.get_campaign(new['member_of_campaign'])

        if not new['cmssw_release'] or new['cmssw_release']=='None':
            new['cmssw_release'] = camp['cmssw_release']

        for i, seqs in enumerate(camp['sequences']):
            for att in seqs['default']:
                ##do not copy over the sequence of conditions
                #if att == 'conditions':
                #    continue
                #if att == 'sequence':
                #    continue                
                if not att in ['eventcontent','datatier']:
                    continue

                new['sequences'][i][att] = seqs['default'][att]


        new['generator_parameters'] = [{'version':0, 'submission_details':{'author_username':'automatic'}, 
                                        'cross_section':float(req_json['crossSection']), 
                                        'filter_efficiency': float(req_json['filterEff']),
                                        'filter_efficiency_error': float(req_json['filterEffError']), 
                                        'match_efficiency': float(req_json['matchEff']),
                                        'match_efficiency_error': -1.}]

        new['energy'] = camp['energy']
        new['reqmgr_name'] = []

        return new

        #convert comma separated strings in prep1 in lists for prep2
    def splitPrep1String(self, thestring):
        if not thestring:
            return []
        stringsplit = thestring.split(',')
        li=[]
        for step in stringsplit:
          item = step.split(' ', 1)[0]
          li.append(item)
        return li

    # aux: converts the date format to the prep2 date format
    def convert_date(self, date,  time=''):
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

    def build_approvals(self, appstr):
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

    def build_comments(self, comments={}):
        if not comments:
            return []
        res = []
        for key in comments:
            try:
                body = comments[key]['body']
                date = comments[key]['date']
                if ' ' in date:
                    new_date = self.convert_date(date.split()[0], date.split()[1])
                else:
                    new_date = self.conver_date(date)
                res.append({'message':body, 'submission_details':{'author_name':'automatic', 'submission_date':new_date}})
            except Exception:
                continue
        return res

    def get_campaign(self, cid):
        try:
            from couchdb_layer.prep_database import database
            cdb=database('campaigns')
            return cdb.get(cid)
            #return json.loads(open('sync/campaigns/%s.json' % (cid)).read())
        except:
            return {}

    # transform is a static method that reads string representations of jsons generated from prep XMLs
    # and returns a json object ready to be uploaded to prep2
    @classmethod
    def transform(cls, jstr=''):
        ob = cls(jstr)
        rall = ob.prepare_json()
        final = []
        for r in rall:
            final.append(ob.re_morph(r))
        return final

if __name__=='__main__':
# since it's static then you just need to call it with the prep1 json string repr
    #print transformer.transform(open('example.json', 'r').read())
    print get_campaign('Summer12')
