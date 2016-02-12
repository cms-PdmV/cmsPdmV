import os

class locator:
    def __init__(self):
        pass

    def isDev(self):
        host = os.environ['HOSTNAME']

        if host in ['vocms085.cern.ch']: ## openstack -dev machine
            return True
        elif host in ['vocms093.cern.ch', 'vocms087.cern.ch']: ## prod and int machines
            return False
        return True

    def isInt(self):
        host = os.environ['HOSTNAME']

        if host in ['vocms087.cern.ch']: ## int machine
            return True
        else:
            return False

    def dbLocation(self):
        if self.isDev():
            return 'http://vocms085.cern.ch:5984/' ## dev instance
        else:
            return 'http://vocms090.cern.ch:5984/' ## prod instance
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
