#!/usr/bin/env python

from jinja2 import Environment, PackageLoader
from Page import Page

class Results(Page):
    def index(self, db_name='campaigns', query='', page=0):
        res_tmpl = self.environment.get_template('results.tmpl')
        self.result = res_tmpl.render(db_input=db_name, query_input='"'+query.strip('"')+'"', page_input=page)
        return self.header() + self.result + self.footer()
    index.exposed = True    
