#!/usr/bin/env python

import json
from Page import Page
from couchdb_layer.prep_database import database
from rest_api.RequestPrepId import RequestPrepId
from json_layer.request import request
from json_layer.campaign import campaign
from json_layer.chained_request import chained_request
from json_layer.chained_campaign import chained_campaign
from json_layer.flow import flow

class Create(Page):
    def create(self, db_name, campaign, chainid):
        try:
            self.db_name = db_name
            self.db = database(db_name)
            self.chainid = chainid
        except database.DatabaseNotFoundException(db_name) as ex:
            print str(ex)
            return
        except database.DatabaseAccessError(db_name) as ex:
            print str(ex)
            return
        self.campaign_id = campaign
        self.object = None
        return self.header() + self.create_object() + self.footer()

    def create_object(self):
        self.object = self.detect_object_type()
        if not self.object:
            return ''
        result =  '<script>var jsondata='+json.dumps(self.object)+';</script>'
        result += '<script>$(document).ready(function() {$(".selectables").selectable({selected: function(events, ui){edit_composite_object(ui.selected.id);}}); addHover("li"); addHover(".comp_btn"); });</script>'
        result += '<body><table class="ui-widget" id="editor">'
        result += '<thead class="ui-widget-header"><td>Attribute</td><td>Value</td></thead>'
        result += '<tbody class="ui-widget-content">'
        for key in self.object:
            result += '<tr><td>'+str(key)+'</td><td>'
            result += str(self.build_parameter(key))
            result += '</td></tr>'
        result += '</tbody>'
        result += '</table><br><a class="ui-state-default ui-corner-all" href="javascript:save_object(\''+self.db_name+'\');">Commit</a></body>'            
        return result

    def present_list(self, li, key):
            if not li:
                    return ''
            res = '<ol class="selectables" id="'+key+'">'
            index = 0
            if type(li) == list:
                    for ob in li:
                            if key == 'comments':
                                    res += self.build_comment(ob, index)
                            elif key == 'approvals':
                                    res += self.build_approval(ob, index)
                            elif key == 'sequences':
                                    s = self.build_sequence(ob, index)
                                    if s:
                                            res += s
                                    else:
                                            continue
            elif key == 'generator_parameters':
                res += self.build_generator_parameters(ob, index)
            elif key == 'chain' or key == 'member_of_chain':
                res += self.build_one_line_list(key, ob, index)
                index += 1
            elif type(li) == dict:
                    if key == 'submission_details':
                            res += '<li>'+li['author_name']+'<p>'+li['submission_date']+'</p></li>'
            res += '</ol>'
            return res

    def build_one_line_list(self, key, ob, index):
            res = "<li id='"+str(key)+"_"+str(index)+"' class='ui-widget-content'>"+str(ob)+"</li>"
            return res

    def build_generator_parameters(self, ob, index):
        res = "<li id='generator_parameters_"+str(index)+"' class='ui-widget-content'>"+ob['submission_details']['author_name']
        res += " ("+ob['submission_details']['submission_date']+")"
        res += "</li>"
        return res

    def build_comment(self, ob, index):
                res = "<li id='comments_"+str(index)+"' class='ui-widget-content'>"+ob['submission_details']['author_name']
                res += " ("+ob['submission_details']['submission_date']+")"
                res += "<p>"+ob['message']+"</p>"
                return res + "</li>"

    def build_approval(self, ob, index):
            res = "<li id='approvals_"+str(index)+"' class='ui-widget-content'>"+ob['approver']['author_name']
            res += "(" + ob["approver"]['submission_date'] + ")"
            res += "<p>" + ob["approval_step"] + "</p>"
            return res + "</li>"

    def build_sequence(self, ob, index):
            s = ''
            res = ''
            for seq in ob['sequence']:
                    s += seq + ','
            if s:
                    if s[-1] == ',':
                            s = s[:len(s)-1]
            if s != '':
                    res += '<li id="sequences_'+str(index)+'" class="ui-widget-content">' + s
            return res + "</li>"

    def build_parameter(self, key):
        protected = ['_id', 'submission_details',  'next_campaign']
        inherited = ['process_string', 'type', 'cmssw_release', 'sequences', 'generators', 'pileup_dataset_name']
        
        if key == 'chain':      
            return self.present_list(self.campaign["campaigns"], key)       
    
        elif type(self.object[key]) == list or type(self.object[key]) == dict:
            return self.present_list(self.object[key], key)
        
        elif key == 'pwg': # fix for the working groups
            return self.build_select(key, ['BPH', 'BTV', 'EGM', 'EWK', 'EXO', 'FWD', 'HIG', 'HIN', 'JME', 'MUO', 'QCD', 'SUS', 'TAU', 'TRK', 'TOP'])
        
        elif key in inherited:
            if 'requests' == self.db_name:
                return self.build_select(key, self.campaign[key])
            else:
                if type(self.object[key]) == list or type(self.object[key]) == dict:
                    return self.present_list(self.object[key], key)
                else:
                    result = '<textarea class="ui-widget-content" id="'+str(key)+'" '
                    result += 'cols=100 rows='+str(len(str(self.object[key]))/100)
                    if key in protected:
                        result += ' readonly="readonly"'
                    result += '>'+str(self.object[key])+'</textarea>'
                    return result
        else:
            result = '<textarea class="ui-widget-content" id="'+str(key)+'" '
            result += 'cols=100 rows='+str(len(str(self.object[key]))/100)
            if key in protected:
                result += ' readonly="readonly"'
            result += '>'+str(self.object[key])+'</textarea>'
            return result

    def build_select(self, key, lst):
        res = '<select class="ui-widget-content" id="'+key+'">'
        for l in lst:
            res += "<option"
            if l == self.object[key]:
                res += " selected='selected'"
            res += ">"+str(l)+"</option>"
        res += "</select>"
        return res              
    
    # detect what attributes and databases are needed for
    # the handling of the object
    def detect_object_type(self):
        object = None
        if self.db_name == 'requests':
            object = request('')
            db_name = 'campaigns' 
        elif self.db_name == 'chained_requests':
            object = chained_request('')    
            db_name = 'chained_campaigns'
        elif self.db_name == 'campaigns':
            object = campaign('')
            return object.json()
        elif self.db_name == 'chained_campaigns':
            object = chained_campaign('')
            return object.json() 
        elif self.db_name == 'flows':
            object = flow('')
            return object.json()
        else:
            return None
        try:
            cdb = database(db_name)
            if not cdb.document_exists(self.campaign_id):
                return None
        except database.DatabaseNotFoundException(db_name) as ex:
            print str(ex)
            return
        except database.DatabaseAccessError(db_name) as ex:
            print str(ex)
            return
        
        # if there is a chain init chained_requests database
        if self.db_name == 'requests' and self.chainid:
            try:
                chdb = database("chained_requests")
                if not chdb.document_exists(self.chainid):
                    return None
            except database.DatabaseNotFoundException("chained_requests") as ex: 
                print str(ex)
                return
            except database.DatabaseAccessError("chained_requests") as ex:
                print str(ex)
                return
            member_of_chain = object.get_attribute("member_of_chain")
            if not member_of_chain:
                object.set_attribute('member_of_chain', [self.chainid])
            else: 
                object.set_attribute('member_of_chain', member_of_chain.append(self.chainid))
            
            # get the chain and inherit
            chain = chdb.get(self.chainid)
            object.set_attribute("generators", chain["generators"])
            object.set_attribute("total_events", chain["total_events"])
            object.set_attribute("dataset_name", chain["dataset_name"])
            object.set_attribute("pwg", chain["pwg"])
            object.set_attribute("priority", chain["priority"]) 
            chain_field = chain["chain"]
            
            # get the new prepid and append it to the chain
            if not chain_field:
                chain["chain"] = [json.loads(RequestPrepId().generate_prepid(object.get_attribute("pwg"), self.campaign_id))["prepid"]]
            elif self.chainid in chain_field:
                pass
            else:
                chain["chain"].append(json.loads(RequestPrepId().generate_prepid(object.get_attribute("pwg"), self.campaign_id))["prepid"])
            chdb.update(doc=chain)  

        object.set_attribute('member_of_campaign', self.campaign_id)
        self.campaign = cdb.get(self.campaign_id)
        
        return object.json()

    def default(self, db_name, campaign_id, chainid=''):
        return self.create(db_name, campaign_id, chainid)

    default.exposed = True  
 
