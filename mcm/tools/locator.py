import os

class locator:
    def __init__(self):
        pass

    def isDev(self):
        host = os.environ['HOSTNAME']

        if host in ['vocms085.cern.ch']: ## openstack -dev machine
            return True
        elif host in ['cms-pdmv-mcm', 'cms-pdmv-mcmint', 'vocms087.cern.ch']:
            return False ## cms-pdmv-mcmint has to be removed after migration
        return True

    def isInt(self):
        host = os.environ['HOSTNAME']

        if host in ['cms-pdmv-mcmint', 'vocms087.cern.ch']:
            return True
        else:
            return False

    def dbLocation(self):
        if self.isDev():
            host = os.environ['HOSTNAME']
            ## needed while migration to openstack is going
            return 'http://vocms085.cern.ch:5984/'
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
