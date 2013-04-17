#!/usr/bin/env python

import urllib2
from xml.etree.ElementTree import parse

class downloader:
    def __init__(self, prep='http://cms.cern.ch/iCMS/prep/'):
        self.url = prep

        if not self.url:
            raise ValueError('URL given is None.')

        if '/' != self.url[-1]:
            self.url += '/'

        self.rdmod = 'requestxml?code='
        self.cdmod = 'campaignxml?campid='#'requestxml?campid='
        self.dmod = ''

        self.xml = None
        self.json = None

    def download(self, pid=''):
        if not pid:
            return None

        if '-' in pid:
            self.dmod = self.rdmod
        else:
            self.dmod = self.cdmod

        try:
            f = urllib2.urlopen(self.url + self.dmod + pid)
            self.xml = parse(f)
            #import json
            #print json.dumps(map(lambda x: self.__xml2json(x), list(self.xml.getroot())), indent=4)
            f.close()
        except urllib2.URLError as urx:
            print 'Error: Could not access '+self.url+self.dmod+pid
            print 'Reason: '+str(urx.reason)
            return None
        except urllib2.HTTPError as htex:
            print 'Error: Remote server responded with error code: '+str(htex.code)
            return None

        return self.translate2json(self.xml)

# this takes the root node of an xml element tree and produces a json representation
# of the tree
    def __xml2json(self, node):
        if node is None:
            return {}
        this = {}

        if node.tag == 'campaign_comments':
            this['comments'] = self.__get_comments(node)
            #return this

        if len(node) > 0:
            this[node.tag] = {}
            for ob in list(node):
                this[node.tag].update(self.__xml2json(ob))
        else:
            this[node.tag] = node.text
        for name, value in node.items():
            this[name] = value

        return this

    def __get_comments(self, node):
        if node is None:
            return {}
        comms = []
        for ob in list(node):
            comms.append({'updater': {'author_username':'automatic', 'author_name':'', 'author_email':'','submission_date':ob[0].text}, 'message':ob[1].text, 'action':'comment'})
        return comms

    def translate2json(self, xml):
        p = map(lambda x: self.__xml2json(x), list(self.xml.getroot()))
        return p

if __name__=='__main__':
    import json
    cl = ['Summer12', 'Summer11', 'Summer12_DR53X', 'Fall11_R1', 'Fall11_R2']
    d = downloader()

    for c in cl:
        f = open('%s.json' % (c), 'w')
        f.write(json.dumps(d.download(c)))
        f.close()
