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
from json_layer.action import action

class Actions(Page):
    def actions(self,  page):
        self.page = page
        try:
            self.db = database('actions')
        except database.DatabaseNotFoundException('actions') as ex:
            print str(ex)
            return
        except database.DatabaseAccessError('actions') as ex:
            print str(ex)
            return
            
        try:
            self.cdb = database('chained_campaigns')
        except database.DatabaseNotFoundException('requests') as ex:
            print str(ex)
            return
        except database.DatabaseAccessError('requests') as ex:
            print str(ex)
            return        
        
        try:
            self.crdb = database('chained_requests')
        except database.DatabaseNotFoundException('requests') as ex:
            print str(ex)
            return
        except database.DatabaseAccessError('requests') as ex:
            print str(ex)
            return             
            
        return self.header() + self.result +self.create_actions() + self.footer()
    
    def create_actions(self):
        actions = self.db.get_all(self.page) # do not pagify
        acobs = map(lambda x: x['value'],  actions)
        ccamps = map(lambda x: x['value'],  self.cdb.get_all(-1))
        cc_pos = []
        result =''
        
        # build action buttons
        result += self.build_buttons()
        
        # build actions table
        result += '<body><table class="ui-widget" id="actions_table">'
        result += '<thead class="ui-widget-header"><td>Actions</td>'
        
        # build header using all chained_campaigns
        for cc in ccamps:
            if cc['alias']:
                result +='<td><a href="javascript:new_tab_redirect(\'/edit/chained_campaigns/'+cc['_id']+'\');">'+cc['alias']+'</a>'
            else:
                result += '<td><a href="javascript:new_tab_redirect(\'/edit/chained_campaigns/'+cc['_id']+'\');">'+cc['_id']+'</a>'
            result += '<a class="gen_buttons" href="javascript:generate_requests(\''+cc['_id']+'\');">gen</a></td>'

            # store position
            cc_pos.append(cc['_id'])
            
        # init tbody
        result += '</thead><tbody class="ui-widget-content">'
            
        # build table rows
        for a in acobs:
            result += self.build_action_rows(a,  cc_pos)
            
        result += '</tbody>'
        result += '</table>'
        
        return result
    
    def build_buttons(self):
        result = ''
        result += '<a class="ui-state-default ui-corner-all" href="javascript:refresh_all_chains();">Refresh Chains</a>'
        return result
    
    # takes an action dictionary and the dictionary of positions
    # and builds an action table row
    def build_action_rows(self,  act,  poslist):
        # init row
        res = '<tr><td>'+act['prepid']+'<a class="gen_buttons" href="javascript:generate_requests(\''+act['prepid']+'\');">gen</a></td>'
        chains = act['chains']
        
        for key in poslist:
            
            # init cell
            res += '<td>'
            
            if key in chains:
                # if is selected
                res += '<input id="'+act['_id']+'.'+str(key)+'" class="ui-widget-content action_value" type="checkbox"'
                
                # if chain is previously defined (checked)
                if chains[key] > 0:
                    res += 'checked="checked"'
                res += '>'
                
                # add link to chained request
                creqs = map(lambda x: x['value'], self.crdb.query('root_request=='+act['_id']))
                for cr in creqs:
                    if key == cr['_id'].split('-')[1]:
                        res += '<a class="gen_buttons" href="javascript:new_tab_redirect(\'/edit/chained_requests/'+cr['_id']+'/\');">show</a>'
            else:
                # else None / Applicable
                res += '<input class="ui-widget-content" type="checkbox" disabled="disabled" >'
            
            # close cell
            res += '</td>'
        # close row
        res += '</tr>'
        
        # return results
        return res
    
    def index(self,  page=0):
        return self.actions(int(page))
    
    def default(self,  page=0):
        return self.actions(int(page))

    default.exposed = True  
    index.exposed = True
