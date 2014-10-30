#from tools.logger import logfactory
import httplib,urllib2
import urllib
from simplejson import dumps
from tools.json import threaded_loads


class cmsweb_interface:
    #logger = logfactory
    class X509CertOpen(urllib2.AbstractHTTPHandler):
        def default_open(self, req):
            return self.do_open(cmsweb_interface.X509CertAuth, req)

    class X509CertAuth(httplib.HTTPSConnection):
        def __init__(self, host, *args, **kwargs):
            x509_path = self.proxy
            key_file = cert_file = x509_path
            httplib.HTTPSConnection.__init__(self, host,key_file = key_file,cert_file = cert_file,**kwargs)

    def __init__( self , proxy):
        cmsweb_interface.X509CertAuth.proxy = proxy

    def generic_call(self, url,header=None, load=True, data=None, delete=False):
        opener=urllib2.build_opener(cmsweb_interface.X509CertOpen())
        url = url.replace('#','%23')
        datareq = urllib2.Request(url)
        if data:
            if type(data) == dict:
                preencoded = {}
                for (k,v) in data.items():
                    if type(v) == dict:
                        preencoded[k] = dumps(v)
                    else:
                        preencoded[k] = v
                encoded = urllib.urlencode( preencoded, False )
            else:
                encoded = data
            print encoded 
            datareq.add_data( encoded )
            #datareq.get_method = lambda: 'PUT'

        if delete:
            datareq.get_method = lambda: 'DELETE'

        if header:
            for (k,v) in header.items():
                datareq.add_header(k,v)

        try:
            requests_list_str=opener.open(datareq).read()
            if load:
                return threaded_loads(requests_list_str)
            else:
                return requests_list_str
        except:
            import traceback
            print "generic_call %s failed for %s"%( datareq.get_method(), url)
            print traceback.format_exc()
        return None

