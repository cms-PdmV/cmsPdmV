import time
import os
import logging
import sys
import socket
import base64
import json
import urllib2
import urllib
from tools.locator import locator
from tools.locker import locker
from cachelib import SimpleCache


class database:
    logger = logging.getLogger("mcm_error")
    # Cache timeout in seconds
    CACHE_TIMEOUT = 60 * 60
    IP_CACHE_TIMEOUT = 15 * 60
    MAX_READ = int(10e6)  # 10MB should be enough for anyone

    cache = SimpleCache()
    ip_cache = SimpleCache()

    def __init__(self, db_name, url=None, lucene_url=None, cache_enabled=False):
        if not url:
            url = locator().database_url()

        if not lucene_url:
            lucene_url = locator().lucene_url()

        if not db_name:
            raise Exception('Missing database name')

        self.db_name = db_name
        self.cache_enabled = cache_enabled or db_name in {'campaigns', 'chained_campaigns'}
        self.db_url = self.resolve_hostname_to_ip(url)
        self.lucene_url = self.resolve_hostname_to_ip(lucene_url)
        self.auth_header = self.get_auth_header()
        self.opener = urllib2.build_opener(urllib2.HTTPHandler)
        self.max_attempts = 3

    def get_auth_header(self):
        """
        Return authentication to couchdb header
        """
        filename = '/home/pdmvserv/private/couchdb_credentials_json.txt'
        filename = os.getenv('COUCH_CRED', filename)
        with open(filename) as json_file:
            credentials = json.load(json_file)

        b64 = '%s:%s' % (credentials['username'], credentials['password'])
        b64 = base64.b64encode(b64)
        return 'Basic %s' % (b64)

    def resolve_hostname_to_ip(self, hostname):
        """
        Resolve hostname to IPv4 address
        """
        cached = self.ip_cache.get(hostname)
        if cached:
            return cached

        host = hostname.split('//', 1)[-1].split(':', 1)[0].split('/', 1)[0]
        ip = socket.gethostbyname(host)
        with_ip = hostname.replace(host, ip).rstrip('/') + '/'
        self.ip_cache.set(hostname, with_ip, timeout=self.IP_CACHE_TIMEOUT)
        self.logger.info('Will cache %s as %s', hostname, with_ip)
        return with_ip

    def cache_size(self):
        """
        Return number of elements in cache and cache size in bytes
        """
        return len(self.cache._cache), sys.getsizeof(self.cache._cache)

    def clear_cache(self):
        """
        Clear cache
        """
        size = self.cache_size()
        self.cache.clear()
        return size

    def __build_request(self, url, path, method, headers, data):
        """
        Build a HTTP request to CouchDB or couchdb-lucene
        """
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        if data is not None and isinstance(data, dict):
            data = json.dumps(data)

        full_url = url + path.lstrip('/')
        self.logger.debug('Built full url: %s', full_url)
        request = urllib2.Request(full_url, data=data)
        request.get_method = lambda: method
        for key, value in headers.items():
            request.add_header(key, value)

        return request

    def couch_request(self, path, method='GET', headers=None, data=None):
        """
        Build a HTTP request to CouchDB
        """
        request = self.__build_request(self.db_url, path, method, headers, data)
        if self.auth_header:
            request.add_header('Authorization', self.auth_header)

        return request

    def lucene_request(self, path, method='GET', headers=None, data=None):
        """
        Build a HTTP request to couchdb-lucene
        """
        request = self.__build_request(self.lucene_url, path, method, headers, data)
        return request

    def __fetch(self, document_id, include_deleted=False):
        """
        Return a document for given id
        If include deleted is true, then return remains of the deleted document
        """
        if not document_id:
            return None

        db_request = self.couch_request('%s/%s' % (self.db_name, document_id))
        for attempt in range(1, self.max_attempts + 1):
            try:
                data = self.opener.open(db_request)
                return json.loads(data.read(self.MAX_READ))
            except urllib2.HTTPError as http_error:
                code = http_error.code
                if code == 404 and include_deleted:
                    data = http_error.read(self.MAX_READ)
                    # Database returned 404 - not found
                    # Document might have never existed or it could be deleted
                    data_json = json.loads(data)
                    return data_json

                self.logger.error('HTTP error fetching %s: %s', document_id, http_error)
                if 400 <= code < 500:
                    # If it's HTTP 4xx - bad request, no point in retry
                    return None

                if attempt < self.max_attempts:
                    sleep = 2 ** attempt
                    time.sleep(sleep)
            except Exception as ex:
                self.logger.error('Error fetching %s: %s', document_id, ex)
                if attempt < self.max_attempts:
                    sleep = 2 ** attempt
                    time.sleep(sleep)

        return None

    def __save_to_cache(self, key, value):
        """
        Save value to cache if cache is enabled
        """
        if self.cache_enabled:
            with locker.lock(key):
                cache_key = 'mcm_database_' + key
                self.cache.set(cache_key, value, timeout=self.CACHE_TIMEOUT)

    def __get_from_cache(self, key):
        """
        Return value from cache if cache is enabled
        If cache is disabled or value could not be found, return None
        """
        if self.cache_enabled:
            with locker.lock(key):
                cache_key = 'mcm_database_' + key
                return self.cache.get(cache_key)
        else:
            return None

    def get(self, prepid):
        """
        Get a document from database
        """
        cached = self.__get_from_cache(prepid)
        if cached:
            return cached

        doc = self.__fetch(prepid)
        self.__save_to_cache(prepid, doc)
        return doc

    def bulk_get(self, ids):
        """
        Get multiple documents at once
        Non existing documents are changed with None
        Order is preserved
        """
        request = self.couch_request('%s/_bulk_get' % (self.db_name),
                                     method='POST',
                                     data={'docs': [{'id': x} for x in ids]})
        data = self.opener.open(request)
        results = json.loads(data.read(self.MAX_READ))['results']
        results = [r['docs'][-1]['ok'] for r in results if r.get('docs') if r['docs'][-1].get('ok')]
        return results

    def document_exists(self, prepid, include_deleted=False):
        """
        Return whether document with given prepid exists
        Optionally, include deleted items
        """
        self.logger.debug('Checking if document "%s" exists', prepid)
        doc = self.__fetch(prepid, include_deleted)
        if not doc:
            return False

        if not include_deleted and doc:
            return True

        error = doc.get('error')
        if not error:
            return True

        reason = doc.get('reason')
        return error == 'not_found' and reason == 'deleted'

    def delete(self, prepid):
        """
        Delete document with given _id from the database
        """
        self.logger.info('Deleting "%s" from "%s"...', prepid, self.db_name)
        doc = self.__fetch(prepid)
        if not doc:
            return False

        # Update cache just in case
        self.__save_to_cache(prepid, None)
        doc['_deleted'] = True
        self.update(doc)
        self.logger.info('Deleted "%s" from "%s"', prepid, self.db_name)
        return True

    def update(self, doc):
        doc_id = doc.get('_id')
        if not doc_id:
            self.logger.error('Could not find _id in document of "%s"', self.db_name)

        self.logger.info('Updating "%s" in "%s"...', doc_id, self.db_name)
        self.__save_to_cache(doc_id, None)
        saved = self.save(doc)
        if saved:
            self.logger.info('Updated "%s" in "%s"', doc_id, self.db_name)
        else:
            self.logger.info('Failed to update "%s" in "%s"', doc_id, self.db_name)

        return saved

    def save(self, doc):
        doc_id = doc.get('_id')
        if not doc_id:
            self.logger.error('Could not find _id in document of "%s"', self.db_name)

        doc_rev = doc.get('_rev')
        self.logger.info('Saving "%s" (%s) in "%s"...', doc_id, doc_rev, self.db_name)
        request = self.couch_request(self.db_name, 'POST', data=doc)
        try:
            data = self.opener.open(request).read(self.MAX_READ)
            data = json.loads(data)
            success = data.get('ok') is True
            if not success:
                self.logger.error(data)

            return success
        except Exception as ex:
            self.logger.error('Error saving %s: %s', doc_id, ex)
            return False

    def pagify(self, page_num=0, limit=20):
        """
        Return limit and skip values for given page and limit
        """
        if page_num < 0:
            # Page <0 means "all", but it still has to be limited to something
            return 1000, 0

        if limit < 0 or limit > 1000:
            # Always enforce a limit
            limit = 1000

        skip = limit * page_num
        return limit, skip

    def raw_query_view(self, design_doc, view_name, page, limit, options=None, with_total_rows=False):
        """
        Internal method for querying a CouchDB view
        """
        url = '%s/_design/%s/_view/%s' % (self.db_name, design_doc, view_name)
        limit, skip = self.pagify(page, limit)
        if options is None:
            options = {}

        if limit >= 0 and skip >= 0:
            options['limit'] = limit
            options['skip'] = skip

        if options.get('include_docs', True):
            options['include_docs'] = True

        if options.get('key'):
            key = options['key']
            if isinstance(key, list):
                key = json.dumps(key)
            else:
                key = '"%s"' % (key)

            options['key'] = key # (key.replace('"', '\\"'))

        if options:
            url += '?' + urllib.urlencode(options)

        self.logger.debug('Query view %s', url)
        request = self.couch_request(url)

        data = self.opener.open(request).read(self.MAX_READ)

        # Tell the user when MAX_READ is reached
        if len(data) == self.MAX_READ:
            raise ValueError('The database returned too much data')

        data = json.loads(data)
        if options.get('include_docs'):
            rows = [r['doc'] for r in data.get('rows', [])]
        elif design_doc == 'unique':
            rows = [r['key'] for r in data.get('rows', [])]
        else:
            rows = [r['value'] for r in data.get('rows', [])]

        if with_total_rows:
            total_rows = data.get('total_rows', 0)
            return {'rows': rows, 'total_rows': total_rows}

        return rows

    def get_all(self, page=-1, limit=20, with_total_rows=False):
        """
        Get all documents from specific database
        """
        return self.raw_query_view(self.db_name, 'all', page, limit, with_total_rows=with_total_rows)

    def query_view(self, key, value, page_num=0, limit=20):
        """
        Perform a simple query of CouchDB view
        """
        return self.raw_query_view(self.db_name,
                                   key,
                                   page_num,
                                   limit,
                                   {'key': value})

    def query_unique(self, field_name, key, limit=10):
        """
        Get unique values of key for given field
        """
        startkey = '"%s"' % (key)
        endkey = '"%s\ufff0"' % (key)
        options = {'limit': limit,
                   'group': True,
                   'startkey': startkey,
                   'endkey': endkey,
                   'include_docs': False}
        data = self.raw_query_view('unique',
                                   field_name,
                                   page=0,
                                   limit=limit,
                                   options=options,
                                   with_total_rows=False)
        return data

    def escaped_term(self, term):
        """
        Escape special characters in given term
        """
        rules = {'-': r'\-',
                 '&': r'\&',
                 '|': r'\|',
                 '!': r'\!',
                 '{': r'\{',
                 '}': r'\}',
                 '[': r'\[',
                 ']': r'\]',
                 '^': r'\^',
                 '~': r'\~',
                 '?': r'\?',
                 ':': r'\:',
                 '"': r'\"',
                 ';': r'\;',
                 ' ': r'\ ',
                 '/': r'\/'}

        # Escape backslash first?
        term = term.replace('\\', r'\\')
        return ''.join(rules.get(c, c) for c in term)

    def make_query(self, args):
        """
        Make query for given args dictionary
        args dictionary may look like this:
        {
            arg1: [val1, val2, val3] # arg1 is val1 OR val2 OR val3
            "AND"
            arg2: val4 # arg2 is val4
            "AND"
            arg3: [!val5] # arg3 is not val5
        }
        """
        query = []
        for attribute, value in args.items():
            attribute = attribute.rstrip('_')
            if not isinstance(value, list):
                value = [value]

            # Make tuples of escaped values and a flag whether they are postive
            values = [(self.escaped_term(v.lstrip('!')), v[0] != '!') for v in value]
            # Handle positive search first
            positive = [v[0] for v in values if v[1]]
            if positive:
                query.append('(%s:(%s))' % (attribute, ' '.join(v for v in positive)))
                # If there is something positive, don't need to query for negative
                continue

            # Negative search
            negative = [v[0] for v in values if not v[1]]
            if negative:
                query.append('(%s:(* %s))' % (attribute, ' '.join('-%s' % (v) for v in negative)))

        return 'AND'.join(query)

    def search(self, query_dict, page=0, limit=20, include_fields=None, total_rows=False, sort=None, sort_asc=True):
        """
        Query couchdb-lucene with given query dict. By default, returns a list of dicts.
        If total_rows is True, returns a dict of results "rows" and number of "total_rows" instead.

        Raises on error.
        """
        limit, skip = self.pagify(page, limit)
        query = self.make_query(query_dict)
        url = 'local/%s/_design/lucene/search' % (self.db_name)
        options = {'limit': limit,
                   'skip': skip,
                   'include_docs': True,
                   'sort': '_id<string>' if not sort else sort,
                   'q': query}
        if include_fields:
            # couchdb-lucene bug - _id must be always included when specifying
            # which fields to fetch because couchdb-lucene has "_id" hardcoded
            include_fields = set(include_fields.split(','))
            include_fields.add('_id')
            include_fields = ','.join(sorted(list(include_fields)))
            options['include_fields'] = include_fields

        if not sort_asc:
            options['sort'] = '\\%s' % (options['sort'])

        if options:
            self.logger.debug('Query options %s', options)
            options = '&%s&' % urllib.urlencode(options)
        else:
            options = ''

        self.logger.debug('Search url %s, options %s', url, options)
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        lucene_request = self.lucene_request(url,
                                             method='POST',
                                             headers=headers,
                                             data=options)
        for attempt in range(1, self.max_attempts + 1):
            try:
                data = self.opener.open(lucene_request).read(self.MAX_READ)
            except urllib2.HTTPError as http_error:
                code = http_error.code
                self.logger.error('HTTP error %s %s: %s', url, options, http_error)
                if 400 <= code < 500:
                    # If it's HTTP 4xx - bad request, no point in retry
                    raise

                if attempt < self.max_attempts:
                    sleep = 2 ** attempt
                    time.sleep(sleep)
                else:
                    raise
            except Exception as ex:
                self.logger.error('Error %s %s: %s', url, options, ex)
                if attempt < self.max_attempts:
                    sleep = 2 ** attempt
                    time.sleep(sleep)
                else:
                    raise

            # Tell the user when MAX_READ is reached
            if len(data) == self.MAX_READ:
                raise ValueError('The database returned too much data')

            data = json.loads(data)
            if total_rows:
                return {'rows': [r['doc'] for r in data.get('rows', [])],
                        'total_rows': data.get('total_rows', 0)}

            return [r['doc'] for r in data.get('rows', [])]

        if total_rows:
            return {'rows': [],
                    'total_rows': 0}

        return []
