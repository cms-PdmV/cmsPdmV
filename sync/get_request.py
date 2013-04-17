#!/usr/bin/env python

from sync.download import downloader
from sync.transform import transformer

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
        return transformer.transform(self.request)

