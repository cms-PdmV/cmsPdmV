from json import dumps, loads

import urllib
import urllib2
import logging

class Database():
    """
    CoucDB interface class
    TO-DO: custom view queries; Error parsing ???
    """
    def __init__(self, dbname='database', url='http://localhost:5984/', lucene_url='http://localhost:5985', size=1000, auth_header=None):
        self.__dbname = dbname
        self.__dburl = url
        self.__luceneurl = lucene_url
        self.__queuesize = size
        self.__auth_header = auth_header
        self.opener = urllib2.build_opener(urllib2.HTTPHandler)

        self.reset_queue()
        self.logger = logging.getLogger('mcm_error')

    def reset_queue(self):
        self.__queue = []

    def construct_request(self, url, method='GET', headers={'Content-Type': 'application/json'}, data=None):
        """
        method to construct a HTTP reuqest to couchDB
        """
        self.logger.debug('Request: %s', self.__dburl + url)
        if data is None:
            request = urllib2.Request(self.__dburl + url)
        else:
            request = urllib2.Request(self.__dburl + url, data=dumps(data))
        request.get_method = lambda: method
        for key in headers:
            request.add_header(key, headers[key])

        if self.__auth_header:
            request.add_header('Authorization', self.__auth_header)

        return request

    def construct_lucene_request(self, url, method='GET', headers={'Content-Type': 'application/json'}, data=None):
        """
        method to construct a HTTP reuqest to couchDB
        """
        self.logger.debug('Lucene request: %s', self.__luceneurl + url)
        if data is None:
            request = urllib2.Request(self.__luceneurl + url)
        else:
            request = urllib2.Request(self.__luceneurl + url, data=dumps(data))
        request.get_method = lambda: method
        for key in headers:
            request.add_header(key, headers[key])
        return request

    def to_json_query(self, params):
        """
        converts object to properly encoded JSON in utf-8
        """
        stringfied = dict()
        for p in params:
            if isinstance(params[p], str):
                stringfied[p] = params[p]
            else:
                stringfied[p] = dumps(params[p])

        return urllib.urlencode(stringfied)

    def document(self, id, rev=None):
        """
        get single document from couchDB
        """
        doc_id = id
        if rev is None:
            db_request = self.construct_request("%s/%s" % (self.__dbname, doc_id))
        else:
            db_request = self.construct_request("%s/%s?rev=%s" %(self.__dbname, doc_id, rev))

        for i in range(3):
            try:
                data = self.opener.open(db_request)
            except Exception as ex:
                if i == 2:
                    raise
                else:
                    time.sleep(3)

        return loads(data.read())

    def loadView(self, viewname, options=None, get_raw=False):
        """
        query couchDB view with optional query parameters
        """
        if options is None:
            db_request = self.construct_request("%s/%s" % (self.__dbname, viewname))
        else:
            #db_request = self.construct_request("%s/%s?%s" %(self.__dbname, viewname, urllib.urlencode(options).replace('%27','%22')))
            db_request = self.construct_request("%s/%s?%s" %(self.__dbname, viewname, self.to_json_query(options)))
        data = self.opener.open(db_request)
        return data.read() if get_raw else loads(data.read())

    def commitOne(self, doc):
        """
        put single document to couchDB, _id can be specified in to-be written document object
        """
        db_request = self.construct_request("%s" % self.__dbname, method='POST', data=doc)
        retval = self.opener.open(db_request)
        return loads(retval.read())

    def delete_doc(self, id, rev=None):
        """
        mark document as deleted and commit to couchDB
        """
        docid = id
        tmp_doc = self.document(docid, rev)
        tmp_doc["_deleted"] = True
        retval = self.commitOne(tmp_doc)
        return retval

    def queue(self, doc):
        """
        add a document to queue list; if queue is full -> commitAll
        """
        if len(self.__queue) >= self.__queuesize:
            self.commit()
        self.__queue.append(doc)

    def commit(self, doc=None):
        """
        commit queue to DB. if wanted to commit single doc -> it is added to queue
        """
        if doc is not None:
            self.queue(doc)
        if len(self.__queue) == 0:
            return
        to_send = dict()
        to_send['docs'] = list(self.__queue)
        db_request = self.construct_request("%s/_bulk_docs/" %(self.__dbname), method='POST', data=doc)
        retval = self.opener.open(db_request)
        self.reset_queue()
        return loads(retval)

    def documentExists(self, id, rev=None):
        """
        Check if a document exists by ID. If specified check that the revision rev exists.
        """
        uri = "/%s/%s" % (self.__dbname, id)
        if rev:
            uri += '?rev=%s' %(rev)
        try:
            db_request = self.construct_request(uri, method='HEAD')
            retval = self.opener.open(db_request)
            return True
        except Exception as ex:
            return False

    def FtiSearch(self, viewname, options=None, get_raw=False):
        """
        query couchDB view with optional query parameters
        """
        if "key" in options:
            options["key"] = '"'+str(options["key"])+'"'
        db_request = self.construct_lucene_request('local/%s/%s&%s' % (self.__dbname, viewname, self.to_json_query(options)))
        data = self.opener.open(db_request)
        return data.read() if get_raw else loads(data.read())

    def UpdateSequence(self, options=None):
        """
        get database update sequence information
        """
        if options is None:
            options = {}
        options["_info"] = True
        db_request = self.construct_request("%s?%s" %(self.__dbname, self.to_json_query(options)))
        data = self.opener.open(db_request)
        return loads(data.read())["update_seq"]
