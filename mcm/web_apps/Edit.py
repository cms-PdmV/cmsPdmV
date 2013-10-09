#!/usr/bin/env python

from Page import Page
import json
import cherrypy
from couchdb_layer.mcm_database import database
from json_layer.request import request
from json_layer.sequence import sequence
from json_layer.campaign import campaign
from json_layer.chained_request import chained_request
from json_layer.chained_campaign import chained_campaign
from json_layer.flow import flow



class Edit(Page):
    def edit(self, db_name, id):
	self.authenticator.set_limit(3)
	if not self.authenticator.can_access(cherrypy.request.headers['ADFS-LOGIN']):
		raise cherrypy.HTTPError(403, 'You cannot access this page')

        try:
            self.db_name = db_name
            self.db = database(db_name)
            self.id = id
            self.campaign = {}
            self.approval_steps = []
        except database.DatabaseNotFoundException(db_name) as ex:
            print str(ex)
            return
        except database.DatabaseAccessError(db_name) as ex:
            print str(ex)
            return
        if not self.db.document_exists(id):  
            print 'Error: Id', id, 'was not found in the database.'  
            return
        self.object = self.db.get(id)
        self.render_template('edit.tmpl')
        return self.header() + self.result + self.edit_object() + self.footer()

    def edit_object(self):
        self.detect_object_type()
        if not self.object:
            return ''

        # loading the json of the object to be edited. Also, the name of the database. These are
        # publicly accessible from javascript.
        result = '<script>var jsondata='+json.dumps(self.object)+'; var db_name="'+self.db_name+'";</script>'

        # onload script
        result += '<script>'
        result += '$(document).ready(function() { '
        result +='$(".selectables").selectable({selected: function(events, ui){edit_composite_object(ui.selected.id);}});'
        result += '$("#chain").selectable({selected: function(events, ui) {add_to_chain("'+self.object["prepid"]+'", $("#"+ui.selected.id).html());}});'
        result +='addHover("li"); '
        result +='addHover(".comp_btn"); '
        
        # add approval steps to approval dialog
        result += '$("#approvals_approvals").empty();'
        i = 0
        for app in self.approval_steps:
            result += '$("<option value='+str(i)+'>'+str(app)+'</option>").appendTo("#approvals_approvals");'
            i += 1
        
        
        result += '});</script>'
        
        # build the attribute table
        result += '<body><table class="ui-widget" id="editor">'
        result += '<thead class="ui-widget-header"><td>Attribute</td><td>Value</td></thead>'
        result += '<tbody class="ui-widget-content">' 
        for key in self.object:
            result += '<tr><td>'+str(key)+'</td><td>'
            result += str(self.build_parameter(key))
            result += '</td></tr>'
        result += '</tbody>'
        result += '</table><br><a class="ui-state-default ui-corner-all" href="javascript:update_object(\''+self.db_name+'\');">Commit</a><a class="ui-state-default ui-corner-all" style="float: right;" href="javascript:delete_object(\''+self.db_name+'\', \''+self.object["prepid"]+'\');">Delete</a></body>'
        
        return result

    def present_list(self, li, key):
        if not li:
            return ''
        if key =='sequences':
            res = '<ul class="selectables" id="'+key+'">'
        else:
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
                elif key == 'status':
                    res += self.build_status(ob,  index)

                elif key == 'generator_parameters':
                                        res += self.build_generator_parameters(ob, index)
                elif key == 'generators' or key =='process_string' or key == 'type' or key == 'cmssw_release' or key=='campaigns' or key=='chain' or key=='member_of_chain':
                    res += str(self.build_one_line_list(key, ob, index))
                elif key == 'campaigns':
                    res += '<li>'+ob[0]+','+ob[1]+'</li>'
                elif key == 'allowed_campaigns':
                    res += '<li>'+ob+'</li>'
                index += 1
        elif type(li) == dict:
            if key == 'submission_details':
                res += '<li>'+li['author_name']+'<p>'+li['submission_date']+'</p></li>'
            elif key == 'request_parameters':
                for key in li:
                    res += '<li>'+str(key)+' : '+str(li[key])+'</li>'
            elif key == 'action_parameters':
                for key in li:
                    res += '<li>'+str(key) + "</li>"
                    res += '<ul>'
                    for k in li[key]:
                        res += '<li>' + str(k) + ' : ' + str(li[key][k])+'</li>'
                    res += '</ul>'
            elif key == 'sequences':
                for key in sorted(li.keys()):
                    #res += "<li class='sequences_unselectable'><ul>"  
                    index = -1
                    for k in li[key]:
                        index += 1
                        res += self.build_sequence(li[key][k],  (k, key))
                    #res += "</ul></li>"
                res += '</ul>'
        if key == 'sequences':
            pass
        else:
            res += '</ol>'
        return res
    
    def build_one_line_list(self, key, ob, index):
        if key == 'chain':
            for req in self.object[key]:
                if str(ob) in req:
                    if self.reqdb.document_exists(str(req)):
                        res = "<li id='"+str(key)+"_"+str(index)+"' class='ui-widget-content'>"+str(req)+"</li>"
                        return res
                    else:
                        self.object[key].remove(req)
                        break
                
        res = "<li id='"+str(key)+"_"+str(index)+"' class='ui-widget-content'>"+str(ob)+"</li>"
        return res
    
    def build_generator_parameters(self, ob, index):
        res = "<li id='generator_parameters_"+str(index)+"' class='ui-widget-content'>"+ob['submission_details']['author_name']
        #res += " ("+ob['submission_details']['submission_date']+")"
        res += "</li>"
        return res

    def build_comment(self, ob, index):
        res = "<li id='comments_"+str(index)+"' class='ui-widget-content'>"+str(ob['submission_details']['author_name'])
        #res += "("+str(ob['submission_details']['submission_date'])+")"
        res += "<p>"+str(ob['message'])+"</p>"
        #res += "<a class='iconholder ui-state-default ui-corner-all' href='javascript:delete_composite_object(\"comments_"+str(index)+"\");'><span class='ui-icon ui-icon-close'></span></a></li>"
        return res  + "</li>"

    def build_approval(self, ob, index):
        res = "<li id='approvals_"+str(index)+"' class='ui-widget-content'>"#+ob['approver']['author_name']
        #res += "(" + ob["approver"]['submission_date'] + ")"
        res += "<p>" + ob["approval_step"] + "</p>"
        #res += "<a class='iconholder ui-state-default ui-corner-all' href='javascript:delete_composite_object(\"approvals_"+str(index)+"\");'><span class='ui-icon ui-icon-close'></span></a></li>"
        return res + "</li>"
        
    def build_status(self,  ob,  index):
        res = "<li id='status_"+str(index)+"' class='ui-widget-content'>"
        res += "<p>"+ob["status"]+"</p>"
        res += "</li>"
        return res

    def build_sequence(self, ob, index):
        thesequence=sequence(json_input=ob)
        s = '' + thesequence.build_cmsDriver()
        res = ''
        #for seq in ob['sequence']:
        #            s += seq + ','
        if s:
            if s[-1] == ',':
                s = s[:len(s)-1]
        if s != '':
            if type(index) == type((0, 0)):
                res += '<li id="sequences_'+str(index[1])+'_'+str(index[0])+'" class="ui-widget-content sequences_selectable">' +str(index[0])+': '+ s  + "</li>"
            else:
                res += '<li id="sequences_'+str(index)+'" class="ui-widget-content sequences_selectable">' + s + "</li>"
        #   res += "<a class='iconholder ui-state-default ui-corner-all' href='javascript:delete_composite_object(\"sequences_"+str(index)+"\");'><span class='ui-icon ui-icon-close'></span></a></li>"
        return res 

    def build_parameter(self, key):
        protected = ['_id', 'submission_details', 'pwg', 'prepid', 'member_of_campaign', 'chain']
        inherited = ['process_string', 'type', 'cmssw_release', 'sequences', 'generators', 'pileup_dataset_name']

        if key == 'chain':
            return self.present_list(self.campaign["campaigns"], key)
    
        elif type(self.object[key]) == list or type(self.object[key]) == dict:
            result = self.present_list(self.object[key], key)
            
            if key not in protected:
                if key != 'sequences' or self.db_name != 'requests':
                    result += '<a href="javascript:create_composite_object(\''+key+'\');" class="comp_btn iconholder ui-state-default ui-corner-all"><span class="ui-icon ui-icon-plus"></span>add ' + key + '</a>'                    
                else:
                    result += '<a href="javascript:alert(1);" class="comp_btn iconholder ui-state-default ui-corner-all"><span class="ui-icon ui-icon-plus"></span>choose ' + key + '</a>'
            return result
    
        elif key in inherited:
            if 'requests' == self.db_name:
                return self.build_select(key, self.campaign[key],  self.object[key])
            else:
                if type(self.object[key]) == list or type(self.object[key]) == dict:
                    result = self.present_list(self.object[key], key)
                    if key not in protected:
                        result += '<a href="javascript:create_composite_object(\''+key+'\');" class="comp_btn iconholder ui-state-default ui-corner-all"><span class="ui-icon ui-icon-plus"></span>add ' + key + '</a>'
                    return result
                else:
                    result = '<textarea class="ui-widget-content" id="'+str(key)+'" '
                    result += 'cols=100 rows='+str(len(str(self.object[key]))/100)
                    if key in protected:
                        result += ' readonly="readonly"'
                    result += '>'+str(self.object[key])+'</textarea>'
                    return result
        else:
            if key == 'valid':
                result = '<input type="checkbox" class="ui-widget-content" id="'+str(key)+'" '
                if self.object[key]:
                    result += 'checked="checked" >'
            else:
                result = '<textarea class="ui-widget-content" id="'+str(key)+'" '
                result += 'cols=100 rows='+str(len(str(self.object[key]))/100)
                if key in protected:
                    result += ' readonly="readonly"'
                result += '>'+str(self.object[key])+'</textarea>'
        return result
        
    def build_select(self, key, lst,  oblist=None):
        res = '<select class="ui-widget-content" id="'+key+'">'
        if type(lst) != list:
            res += "<option selected='selected' class='ui-widget-content'>"+str(lst)+"</option>"
        elif type(lst) == list:        
            for l in lst:
                if self.object[key] == l:
                    res += "<option selected='selected' class='ui-widget-content'>"+str(l)+"</option>"
                else:
                    res += "<option class='ui-widget-content'>"+str(l)+"</option>"
            
            if not lst:
                if oblist:
                    res += "<option selected='selected' class='ui-widget-content'>"+str(oblist)+"</option>"
            
        res += "</select>"
        return res

    def detect_object_type(self):
        if not self.object:
            return None
            
        object = None
        if self.db_name == 'requests':
                object = request('',  json_input=self.object)
                db_name = 'campaigns'
                self.approval_steps = object.get_approval_steps()
        elif self.db_name == 'chained_requests':
                object = chained_request('',  json_input=self.object)
                db_name = 'chained_campaigns'
                self.approval_steps = object.get_approval_steps()
        elif self.db_name == 'campaigns':
                object = campaign('',  json_input=self.object)
                self.approval_steps = object.get_approval_steps()
                self.object = object.json()
                return object.json()
        elif self.db_name == 'chained_campaigns':
                object = chained_campaign('',  json_input=self.object)
                self.approval_steps = object.get_approval_steps()
                self.object = object.json()
                return object.json()
        elif self.db_name == 'flows':
                object = flow('',  json_input=self.object)
                self.approval_steps = object.get_approval_steps()
                self.object = object.json()
                return object.json()
        else:
                return None
        try:
                cdb = database(db_name)
                if not cdb.document_exists(self.object['member_of_campaign']):
                        return None
        except database.DatabaseNotFoundException(db_name) as ex:
                print str(ex)
                return
        except database.DatabaseAccessError(db_name) as ex:
                print str(ex)
                return

        if self.db_name == 'chained_requests':
            try:
                self.reqdb = database("requests")
            except database.DatabaseNotFoundException(db_name) as ex:
                print str(ex)
                return
            except database.DatabaseAccessError(db_name) as ex:
                print str(ex)
                return
                
        self.campaign = cdb.get(self.object['member_of_campaign'])
        self.object = object.json()
        return object.json()


    def default(self, db_name, id):
        return self.edit(db_name, id)

    default.exposed = True  
 
