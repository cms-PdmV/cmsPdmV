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
        if host in ['cms-pdmv-mcmdev']:
            return True
        elif host in ['cms-pdmv-mcm', 'cms-pdmv-mcmint']:
            return False
        return True

    def isInt(self):
        host = os.environ['HOSTNAME']
        if host in ['cms-pdmv-mcmint']:
            return True
        else:
            return False

    def dbLocation(self,inverted=False):
        dev = self.isDev()
        if inverted:
            dev = not dev
        if dev:
            return 'http://cms-pdmv-mcmdev.cern.ch:5984/'
            #return 'http://188.184.20.242:5984/'
        else:
            return 'http://cms-pdmv-mcm-db:5984/'
            #return 'http://188.184.23.164:5984/'
    def workLocation(self):
        if self.isDev():
            return '/afs/cern.ch/cms/PPD/PdmV/work/McM/dev-submit/'
            ## legacy directory return '/afs/cern.ch/cms/PPD/PdmV/tools/prep2/prep2_submit_area/'
        else:
            return '/afs/cern.ch/cms/PPD/PdmV/work/McM/submit/'

    def baseurl(self):
        if self.isDev():
            return 'https://cms-pdmv-dev.cern.ch/mcm/'
        elif self.isInt():
            return 'https://cms-pdmv-int.cern.ch/mcm/'
        else:
            return 'https://cms-pdmv.cern.ch/mcm/'
        
    def cmsweburl(self):
        if self.isDev():
            return 'https://cmsweb-testbed.cern.ch/'
        else:
            return 'https://cmsweb.cern.ch/'
