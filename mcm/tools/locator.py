import os

class locator:
    def __init__(self):
        #self.locations = {
        #    'dev':{ 'servers' : ['preptest'],
        #            'dbLocation' : 'http://preptest.cern.ch:5984/'},
        #    'prod':{ 'servers' : ['cms-pdmv-mcm'],
        #             'dbLocation' : 'http://cms-pdmv-mcm-db:5984/'}
        #    }
        pass

    def isDev(self):
        host = os.environ['HOSTNAME']
        #for (l_type,spec) in self.locations.items():
        #    if host in spec['servers']:
        #        return 
        if host in ['preptest']:
            return True
        elif host in ['cms-pdmv-mcm']:
            return False
        return True

    def dbLocation(self):
        if self.isDev():
            return 'http://preptest.cern.ch:5984/'
        else:
            return 'http://cms-pdmv-mcm-db:5984/'
    def workLocation(self):
        if self.isDev():
            return '/afs/cern.ch/cms/PPD/PdmV/work/McM/dev-submit/'
            ## legacy directory return '/afs/cern.ch/cms/PPD/PdmV/tools/prep2/prep2_submit_area/'
        else:
            return '/afs/cern.ch/cms/PPD/PdmV/work/McM/submit/'
    def baseurl(self):
        if self.isDev():
            return 'https://cms-pdmv-dev.cern.ch/mcm/'
        else:
            return 'https://cms-pdmv.cern.ch/mcm/'
        
