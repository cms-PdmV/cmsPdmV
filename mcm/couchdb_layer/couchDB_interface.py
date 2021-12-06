from json import dumps, loads

import urllib
import urllib2
import logging
import time

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
        # self.logger.debug('Request: %s %s', method, self.__dburl + url)
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
        # self.logger.debug('Lucene request: %s %s', method, self.__luceneurl + url)
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
            if isinstance(params[p], (basestring, str)):
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
                return loads(data.read())
            except urllib2.HTTPError as e:
                code = e.code
                if code == 404:
                    return None

                if i == 2:
                    raise

                time.sleep(1.5)
            except Exception as ex:
                if i == 2:
                    raise

                time.sleep(1.5)

        return None

    def bulk_get(self, ids):
        db_request = self.construct_request("%s/_bulk_get" % (self.__dbname),
                                            method='POST',
                                            data={'docs': [{'id': x} for x in ids]})
        data = self.opener.open(db_request)
        results = loads(data.read())['results']
        results = [r['docs'][-1]['ok'] for r in results if r.get('docs') if r['docs'][-1].get('ok')]
        return results

    def prepid_is_used(self, doc_id):
        """
        Return whether such prepid is already used - either such document
        exists or it was deleted
        """
        request = self.construct_request('%s/%s' % (self.__dbname, doc_id))

        for i in range(3):
            try:
                response = self.opener.open(request)
                data = response.read()
                data = loads(data)
                exists = '_id' in data
                # self.logger.debug('%s exists, code %s', doc_id, response.code)
                return True
            except urllib2.HTTPError as e:
                data = e.read()
                code = e.code
                if code == 404:
                    # If never existed: "error":"not_found","reason":"missing"
                    # If was deleted: "error":"not_found","reason":"deleted"
                    data_json = loads(data)
                    if data_json['error'] == 'not_found':
                        if data_json['reason'] == 'deleted':
                            # Document was deleted, but prepid is used
                            return True
                        if data_json['reason'] == 'missing':
                            # Document never existed, prepid is unused
                            return False

                elif code == 500:
                    self.logger.warning('Code %s, cannot check if %s is used', code, doc_id)
                    if i == 2:
                        raise

                    self.logger.info('Sleep and try %s again', doc_id)
                    time.sleep(3)
                    continue

                reason = e.reason
                self.logger.warning('HTTP error, doc_id: %s, code: %s reason: %s, response: %s',
                                    doc_id,
                                    code,
                                    e.reason,
                                    data)
            except Exception as ex:
                self.logger.warning('Exception %s', ex)
                if i == 2:
                    raise
                else:
                    time.sleep(1.5)

        return False


    def loadView(self, viewname, options=None):
        """
        Query CouchDB view
        """
        if options is None:
            db_request = self.construct_request("%s/%s" % (self.__dbname, viewname))
        else:
            db_request = self.construct_request("%s/%s?%s" %(self.__dbname, viewname, self.to_json_query(options)))

        data = self.opener.open(db_request).read()
        return loads(data)

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
        uri = "%s/%s" % (self.__dbname, id)
        if rev:
            uri += '?rev=%s' %(rev)
        try:
            db_request = self.construct_request(uri, method='HEAD')
            retval = self.opener.open(db_request)
            return True
        except Exception as ex:
            return False

    def lucene_search(self, viewname, options=None):
        """
        Query CouchDB-lucene
        """
        if 'key' in options:
            options['key'] = '"%s"' % (options['key'])

        # For some reason if options end in parentheses or something
        # non-alphanumeric, like parentheses, couchdb-lucene crashes
        options = '&' + self.to_json_query(options) + '&'
        self.logger.debug(options)
        db_request = self.construct_lucene_request('local/%s/%s' % (self.__dbname, viewname),
                                                   method='POST',
                                                   headers={'Content-Type': 'application/x-www-form-urlencoded'},
                                                   data=options)
        data = self.opener.open(db_request).read()
        return loads(data)

    def unique_search(self, field, key, limit):
        """
        Query CouchDB view
        """
        startkey = '"%s"' % (key)
        endkey = '"%s\ufff0"' % (key)
        options = {'limit': limit,
                   'group': True,
                   'startkey': startkey,
                   'endkey': endkey}
        options = self.to_json_query(options)
        url = '%s/_design/unique/_view/%s?%s' % (self.__dbname, field, options)
        db_request = self.construct_request(url)
        try:
            data = loads(self.opener.open(db_request).read())
            return [r.get('key') for r in data['rows']]

        except Exception as ex:
            self.logger.error(ex)
            return []

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
