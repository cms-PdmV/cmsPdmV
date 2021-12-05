#!/usr/bin/env python

import time
import os
import ast
import logging
import sys
import socket
import base64

from json import dumps
from json import load as json_load
from tools.locator import locator
from collections import defaultdict
from couchDB_interface import *
from tools.locker import locker

from cachelib import SimpleCache

class database:
    logger = logging.getLogger("mcm_error")
    # Cache timeout in seconds
    CACHE_TIMEOUT = 60 * 60
    IP_CACHE_TIMEOUT = 15 * 60
    cache = SimpleCache()
    ip_cache = SimpleCache()

    class DatabaseNotFoundException(Exception):
        def __init__(self,  db=''):
            self.db = str(db)
            database.logger.error('Database "%s" was not found.' % (self.db))

        def __str__(self):
            return 'Error: Database ',  self.db,  ' was not found.'

    class DatabaseAccessError(Exception):
        def __init__(self,  db=''):
            self.db = str(db)
            database.logger.error('Could not access database "%s".' % (self.db))

        def __str__(self):
            return 'Error: Could not access database ',  self.db

    class DocumentNotFoundException(Exception):
        def __init__(self,  name=''):
            self.name = name
            database.logger.error('Document "%s" was not found.' % (self.name))

        def __str__(self):
            return 'Error: Document ',  self.name,  ' was not found.'

    class MapReduceSyntaxError(Exception):
        def __init__(self,  query=''):
            self.query = query
            database.logger.error('Invalid query <%s>' % (self.query))

        def __str__(self):
            return 'Error: Invalid query "' + self.query + '"'

    class InvalidOperatorError(Exception):
        def __init__(self,  op=''):
            self.op = str(op)
        def __str__(self):
            return 'Error: Operator "' + self.op + '" is invalid.'

    class InvalidParameterError(Exception):
        def __init__(self,  param=''):
            self.param = str(param)
        def __str__(self):
            return 'Error: Invalid Parameter: ' + self.param

    def __init__(self,  db_name='',url=None, lucene_url=None, cache_enabled=False):
        host = os.environ['HOSTNAME']
        auth_header = None
        if url is None:
            url = locator().dbLocation()
            auth_header = self.get_auth_header()
        if lucene_url is None:
            lucene_url = locator().lucene_url()

        url = self.resolve_hostname_to_ip(url)
        lucene_url = self.resolve_hostname_to_ip(lucene_url)
        if not db_name:
            raise self.DatabaseNotFoundException(db_name)
        self.db_name = db_name
        self.cache_enabled = cache_enabled
        if self.db_name in ['campaigns','chained_campaigns']:
            ## force cache for those.
            self.cache_enabled=True

        try:
            self.db = Database(db_name, url=url, lucene_url=lucene_url, auth_header=auth_header)
        except ValueError as ex:
            raise self.DatabaseAccessError(db_name)

        self.allowed_operators = ['<=',  '<',  '>=',  '>',  '==',  '~=']

    def get_auth_header(self):
        with open('/home/pdmvserv/private/couchdb_credentials_json.txt') as json_file:
            credentials = json_load(json_file)

        b64 = '%s:%s' % (credentials['username'], credentials['password'])
        b64 = base64.b64encode(b64)
        return 'Basic %s' % (b64)

    def resolve_hostname_to_ip(self, hostname):
        cached = self.ip_cache.get(hostname)
        if cached:
            return cached

        host = hostname.split('//', 1)[-1].split(':', 1)[0].split('/', 1)[0]
        ip = socket.gethostbyname(host)
        with_ip = hostname.replace(host, ip)
        self.ip_cache.set(hostname, with_ip, timeout=self.IP_CACHE_TIMEOUT)
        self.logger.info('Will cache %s as %s', hostname, with_ip)
        return with_ip

    def __is_number(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

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

    def get(self,  prepid=''):

        result = self.__get_from_cache(prepid)
        if result: return result

        try:
            doc = self.db.document(id=prepid)
            self.__save_to_cache( prepid, doc)
            return doc
        except Exception as ex:
            self.logger.error('Document "%s" was not found. Reason: %s' % (prepid, ex))
            return {}

    def __save_to_cache(self, key, value):
        if self.cache_enabled:
            with locker.lock(key):
                cache_key = 'mcm_database_' + key
                self.cache.set(cache_key, value, timeout = self.CACHE_TIMEOUT)

    def __get_from_cache(self, key):
        if self.cache_enabled:
            with locker.lock(key):
                cache_key = 'mcm_database_' + key
                return self.cache.get(cache_key)
        else:
            return None

    def __document_exists(self,  doc):
        if not doc:
            self.logger.info('Trying to locate empty string.')
            return False
        id = ''
        if 'prepid' not in doc:
            if '_id' not in doc:
                self.logger.error('Document does not have an "_id" parameter.')

                return False
            id = doc['_id']
        elif '_id' not in doc:
            if 'prepid' not in doc:
                self.logger.error('Document does not have an "_id" parameter.')

                return False
            id = doc['prepid']
        id = doc['_id']
        return self.__id_exists(prepid=id)

    def document_exists(self, prepid=''):
        return self.__id_exists(prepid)

    def __id_exists(self,  prepid=''):
        try:
            if self.__get_from_cache(prepid) or self.db.documentExists(id=prepid):
                return True
            self.logger.error('Document "%s" does not exist.' % (prepid))
            return False
        except Exception as ex:
            self.logger.error('Document "%s" was not found on CouchError Reason: %s trying a second time with a time out' % (prepid, ex))
            time.sleep(0.5)
            return self.__id_exists(prepid)
        except Exception as ex:
            self.logger.error('Document "%s" was not found. Reason: %s' % (prepid, ex))
            return False

    def delete(self, prepid=''):
        if not prepid:
            return False
        if not self.__id_exists(prepid):
            return False

        self.logger.info('Trying to delete document "%s"...' % (prepid))
        try:
            self.db.delete_doc(id=prepid)
            self.__save_to_cache(prepid, None)

            return True
        except Exception as ex:
            self.logger.error('Could not delete document: %s . Reason: %s ' % (prepid, ex))
            return False

    def update(self,  doc={}):
        if '_id' in doc:
            self.logger.info('Updating document "%s" in "%s"' % (doc['_id'], self.db_name))
        if self.__document_exists(doc):
            ##JR the revision in the cache is not the one in the DB at this point
            # will be retaken at next get
            self.__save_to_cache(doc['_id'], None)
            return self.save(doc)
        self.logger.error('Failed to update document: %s' % (dumps(doc)))
        return False

    def update_all(self,  docs=[]):
        if not docs:
            return False

        for doc in docs:
            if self.__document_exists(doc):
                self.db.queue(doc)
        try:
            self.db.commit()
            return True
        except Exception as ex:
            self.logger.error('Could not commit changes to database. Reason: %s' % (ex))
            return False

    def get_all(self, page_num=-1, limit=20, with_total_rows=False):
        try:
            limit, skip = self.__pagify(page_num, limit=limit)
            url = "_design/%s/_view/%s" % (self.db_name, "all")
            if limit >= 0 and skip >= 0:
                result = self.db.loadView(url, options={'limit': limit,
                        'skip': skip, 'include_docs': True})

            else:
                result = self.db.loadView(url, options={'include_docs': True})

            rows = [r['doc'] for r in result['rows']]
            if with_total_rows:
                res_total_rows = result["total_rows"]
                return {'total_rows': res_total_rows,
                        'rows': rows}
            else:
                return rows
        except Exception as ex:
            self.logger.error('Could not access view. Reason: %s' % (ex))
            return []

    def query(self,  query='', page_num=0, limit=20):
        if not query:
            result = self.get_all(page_num, limit=limit)
            return result
        try:
            result = self.__query(query, page=page_num, limit=limit)
            return result
        except Exception as ex:
            self.logger.error('Could not load view for query: <%s> . Reason: %s' % (
                        query, ex))

            return []

    def __extract_operators(self,  query=''):
        if not query:
            return ()
        clean = []
        tokens = []
        for op in self.allowed_operators:
            if op in query:
                tokens = query.rsplit(op)
                tokens.insert(1,  op)
            else:
                continue
            for tok in tokens:
                if len(tok) < 1:
                    continue
                clean.append(tok.strip().strip('"'))
            if len(clean) != 3:
                raise self.MapReduceSyntaxError(query)
            return clean
        raise self.MapReduceSyntaxError(query)

    def __pagify(self, page_num=0, limit=20):
        if page_num < 0:         ##couchdb-lucene dy default return limited resutlts
            return 16384, 0 ## we set it to very high numer
        skip = limit * page_num
        return limit, skip

    def __execute_query(self, tokenized_query='', page=-1, limit=20):
            tokens = []
            try:
                tokens = self.__extract_operators(tokenized_query)
            except Exception as ex:
                self.logger.error('Could not parse query. Reason: %s' % (ex))
                return []
            if tokens:
                view_name, view_opts = self.__build_query(tokens)
                if not view_name or not view_opts:
                    return []
                if page > -1:
                    view_opts['limit'] = limit
                    view_opts['skip'] = page*limit
                view_opts['include_docs']=True
                url = "_design/%s/_view/%s"%(self.db_name, view_name)
                result = self.db.loadView(url, options=view_opts)['rows']
                res = map(lambda r: r['doc'], result)
                return res
            else:
                return []

    def raw_query(self, view_name, options={}):
        url = "_design/%s/_view/%s"%(self.db_name, view_name)
        return self.db.loadView(url, options)['rows']

    def __get_op(self, oper):
        if oper == '>':
            return lambda x,y: x > y
        elif oper == '>=':
            return lambda x,y: x >= y
        elif oper == '<':
            return lambda x,y: x < y
        elif oper == '<=':
            return lambda x,y: x <= y
        elif oper == '==':
            return lambda x,y: x == y
        else:
            return None

    def __filter(self, tokenized_query=[], view_results=[]):
        if len(tokenized_query) != 3:
            return view_results
        prn = tokenized_query[0]
        op = tokenized_query[1]
        if self.__is_number(tokenized_query[2]):
            val = float(tokenized_query[2])
        else:
            val = tokenized_query[2]
        f = self.__get_op(op)
        return filter(lambda x: f(x[prn], val), view_results)

    def __query(self, query='', page=0, limit=20):
        t_par = []
        results = []
        if not t_par:
             t_par = [query]
        if len(t_par) == 1:
            return self.__execute_query(t_par[0], page, limit)
        elif len(t_par) == 0:
            return []
        res = self.__execute_query(t_par[0])
        if len(res) == 0:
            return []
        for i in range(1,len(t_par)):
            tq = self.__extract_operators(t_par[i])
            res = self.__filter(tq, res)
        return res[page*limit:page*limit+20]

    def __build_query(self, tokens=[]):
        if not tokens:
            return None, None
        if len(tokens) != 3:
            raise self.MapReduceSyntaxError(tokens)
        param = tokens[0]
        op = tokens[1]
        kval = tokens[2]
        try:
            view_opts = self.__build_options(op, kval)
        except Exception as ex:
            self.logger.error('Value types are not compatible with operator %s value %s Error: %s' % (
                    op, kval, str(ex)))

            return None, None
        return param, view_opts

    def __build_options(self, op, val):
        # options dictionary
        opts = {}

        def is_number(s):
            try:
                float(s)
                return True
            except ValueError:
                return False

        if val.startswith('[') and val.endswith(']'):
            if op == '==':
                try:
                    e = ast.literal_eval(val)
                    opts['key'] = e
                except:
                    opts['key'] = val
            return opts

        num_flag = False
        if is_number(val):
            num_flag = True
            kval = float(val)
        else:
            kval = val.decode('ascii')
        if '>' in op:
            if '=' in op:
                opts['startkey'] = kval
            else:
                if num_flag:
                    opts['startkey'] = kval + 1
                else:
                    opts['startkey'] = kval
            if num_flag:
                opts['endkey'] = 99999999 # assume its numeric
            else:
                opts['endkey'] = kval + u'\u9999'
        elif '<' in op:
            if '=' in op:
                opts['endkey'] = kval
            else:
                if num_flag:
                    opts['endkey'] = kval - 1
                else:
                    opts['endkey'] = kval
            if num_flag:
                opts['startkey'] = -99999999
            else:
                opts['startkey'] = ''

        elif '==' == op:
            opts['key'] = kval
        elif '~=' == op:
            if kval[-1] == '*':
                opts['startkey'] = kval[:len(kval)-1]
                opts['endkey'] = kval[:len(kval)-1]+u'\u9999'
        return opts

    def save_all(self, docs=[]):
        if not docs:
            return False
        for doc in docs:
            self.db.queue(doc)
        try:
            self.db.commit()
            return True
        except Exception as ex:
            self.logger.error('Could not save_all changes to database. Reason: %s' % (ex))
            return False

    def save(self, doc={}):
        if not doc:
            self.logger.error('Tried to save empty document.')
            return False
        try:
            saved = self.db.commitOne(doc)
            return True
        except Exception as ex:
            ##display _rev id for doc we are saving so to ease debugging
            self.logger.error('Could not save changes %s to database. Reason: %s' % (
                    doc['_id'], ex))

            return False

    def count(self):
        try:
            return len(self.db.allDocs())
        except Exception as ex:
            self.logger.error('Could not count documents in database. Reason: %s' % (ex))
            return -1

    def escapedSeq(self, term):
        """ Yield the next string based on the
            next character (either this char
            or escaped version """
        escapeRules = {'-': r'\-',
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
        for char in term:
            if char in escapeRules.keys():
                yield escapeRules[char]
            else:
                yield char

    def escapeLuceneArg(self, term):
        """ Apply escaping to the passed in query terms
            escaping special characters like : , etc"""
        term = term.replace('\\', r'\\')   # escape \ first
        return "".join([nextStr for nextStr in self.escapedSeq(term)])

    def make_query(self, args):
        """
        Make query for given args dictionary
        args dictionary may look like this:
        {
            arg1: [val1, val2, val3] # arg1 is val1 OR val2 OR val3
            # AND
            arg2: val4 # arg2 is val4
            # AND
            arg3: [!val5] # arg3 is not val5
        }
        """
        query = []
        for attribute, value in args.items():
            attribute = attribute.rstrip('_')
            if not isinstance(value, list):
                value = [value]

            positive = [v for v in value if v[0] != '!']
            if positive:
                query.append('(%s:(%s))' % (attribute, ' '.join(v for v in positive)))
                # If there is something positive, don't need to query for negative
                continue

            negative = [v.lstrip('!') for v in value if v[0] == '!']
            if negative:
                query.append('(%s:(* %s))' % (attribute, ' '.join('-%s' % (v) for v in negative)))

        return 'AND'.join(query)

    def full_text_search(self, index_name, query, page=0, limit=20, with_total_rows=False, include_fields='', sort='', sort_asc=True):
        """
        queries loadView method with lucene interface for full text search
        """
        __retries = 3
        limit, skip = self.__pagify(int(page), limit=int(limit))
        # This needs to have include_docs
        url = "_design/lucene/%s?include_docs=True" % (index_name)
        data = {'rows': [], 'total_rows': 0}
        for i in xrange(1, __retries + 1):
            try:
                options = {
                    'limit': limit,
                    'skip': skip,
                    'sort': '_id<string>',
                    'q': query,
                }
                if include_fields != '':
                    options['include_fields'] = str(include_fields)

                if sort != '':
                    self.logger.warning('Setting sort to %s', sort)
                    options['sort'] = sort
                if not sort_asc:
                    options['sort'] = '\\%s' % (options['sort'])

                data = self.db.lucene_search(url, options=options)
                break
            except Exception as ex:
                self.logger.info("lucene DB query: %s failed %s. retrying: %s out of: %s" % (url,
                                                                                             ex,
                                                                                             i,
                                                                                             __retries))
            # if we are retrying we should wait little bit
            time.sleep(0.5)

        if include_fields != '':
            rows = [r["fields"] for r in data['rows']]
        else:
            rows = [r["doc"] for r in data['rows']]

        if with_total_rows:
            res_total_rows = data["total_rows"]
            return {'total_rows': res_total_rows,
                    'rows': rows}
        else:
            return rows

    def raw_view_query(self, view_doc, view_name, options={}, cache=True):
        sequence_id = "%s/%s" % (view_doc, view_name)
        current_update_seq = self.update_sequence()
        cache_id = "_design/%s/_view/%s" % (view_doc, view_name)
        if cache:
            cached_sequence = self.__get_from_cache(sequence_id)
            if cached_sequence == current_update_seq:
                result = self.__get_from_cache(cache_id)
                self.logger.info('Accessing cache for:%s. Results : %s' % (
                        cache_id, len(result)))

                if result: return result
            else:
                self.__save_to_cache(sequence_id, current_update_seq)
        try:
            self.logger.info('Raw query to the view. Accessed view: %s/%s' % (
                    view_doc, view_name))

            url = "_design/%s/_view/%s" % (view_doc, view_name)
            result = self.db.loadView(url, options)['rows']
            self.__save_to_cache(cache_id, result)
            return result
        except Exception as ex:
            self.logger.error('Document "%s" was not found. Reason: %s' % (cache_id, ex))
            return {}

    def query_unique(self, field_name, key, limit=10):
        """
        Get unique values of key for given field
        """
        return self.db.unique_search(field_name, key, limit)

    def raw_view_query_uniques(self, view_name, options={}, cache=True):
        result = self.raw_view_query("unique", view_name, options, cache)
        if "results" in result:
            return result
        parsedResult = {"results": [str(elem["key"]) for elem in result]}
        cache_id = "_design/unique/_view/%s" % (view_name)
        self.__save_to_cache(cache_id, parsedResult)
        return parsedResult

    def update_sequence(self, options={}):
        result = self.db.UpdateSequence()
        return result
