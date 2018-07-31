import os


class locator:
    def __init__(self):
        pass

    def isDev(self):
        return not (self.isInt() or self.isProd())

    def isInt(self):
        host = os.environ['HOSTNAME']
        return host in ['vocms082.cern.ch']  # Int machine

    def isProd(self):
        host = os.environ['HOSTNAME']
        return host in ['vocms093.cern.ch']  # Prod machine

    def dbLocation(self):
        if self.isDev():
            return 'http://vocms085.cern.ch:5984/'  # dev instance
        else:
            return 'http://vocms090.cern.ch:5984/'  # prod instance

    def workLocation(self):
        if self.isDev():
            return '/afs/cern.ch/cms/PPD/PdmV/work/McM/dev-submit/'
            # legacy directory return '/afs/cern.ch/cms/PPD/PdmV/tools/prep2/prep2_submit_area/'
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
