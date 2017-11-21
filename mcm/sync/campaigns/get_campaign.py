#!/usr/bin/env python

from download import downloader
from transform import convert
from simplejson import dumps

class prep_scraper:
    def __init__(self, prep='http://cms.cern.ch/iCMS/prep/'):
        self.downloader = downloader(prep)
        self.request = None

    def get(self, pid=''):
        try:
           self.request = self.downloader.download(pid)
        except Exception as ex:
            print 'Error: Could not retrieve results. Reason: '+str(ex)
            return None
        return convert(self.request)

if __name__=='__main__':
    prep = prep_scraper()
    #print stringify(prep.get(argv[1]))
    cl = ['Summer12', 'Summer11', 'Summer12_DR53X', 'Fall11_R1', 'Fall11_R2', 'Summer12_WMLHE', 'Summer12_FS53' ]
    for c in cl:
        print c
        f = open('%s.json' % (c.replace('_', '')), 'w')
        f.write(dumps(prep.get(c)))
        f.close()

