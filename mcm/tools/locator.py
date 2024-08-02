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
        return host in ['vocms093.cern.ch', 'vocms0493.cern.ch']  # Prod machine

    def database_url(self):
        if self.isDev():
            return 'http://localhost:5984/'  # dev instance
        raise RuntimeError('This should not happen')

    def lucene_url(self):
        if self.isDev():
            return 'http://localhost:5985/'  # dev instance
        raise RuntimeError('This should not happen')

    def workLocation(self):
        if self.isDev():
            return '/afs/cern.ch/cms/PPD/PdmV/work/McM/dev-submit/'
            # legacy directory return '/afs/cern.ch/cms/PPD/PdmV/tools/prep2/prep2_submit_area/'
        raise RuntimeError('This should not happen')

    def baseurl(self):
        if self.isDev():
            return 'https://ggonzr-personal-proxy.web.cern.ch/mcm/'
        raise RuntimeError('This should not happen')

    def cmsweburl(self):
        if self.isDev():
            return 'https://cmsweb-testbed.cern.ch/'
        raise RuntimeError('This should not happen')
