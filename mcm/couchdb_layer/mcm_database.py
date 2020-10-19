import time
import os
import ast
import logging
import sys
import json
import urllib
from tools.locator import locator
from collections import defaultdict
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class database:
    logger = logging.getLogger("mcm_error")

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

    def __init__(self, db_name, url=None, lucene_url=None):
        if not db_name:
            raise self.DatabaseNotFoundException(db_name)

        if url is None:
            url = locator().database_url()

        url = url.rstrip('/')
        if lucene_url is None:
            lucene_url = locator().lucene_url()

        lucene_url = lucene_url.rstrip('/')
        self.db_name = db_name
        self.couchdb_url = '%s/%s' % (url, db_name)
        self.lucene_url = '%s/local/%s' % (lucene_url, db_name)
        self.auth_header = None
        self.allowed_operators = ['<=',  '<',  '>=',  '>',  '==',  '~=']

    def __make_request(self, url, data=None, method='GET', get_raw=False):
        """
        Make a HTTP request to the actual database api
        """
        if data is not None:
            data = json.dumps(data)

        req = Request(url, data=data, method=method)
        if method in ('POST', 'PUT') and data is not None:
            data = data.encode("utf-8")
            req.add_header('Content-Type', 'application/json')

        if self.auth_header:
            req.add_header('Authorization', self.auth_header)

        self.logger.info('Will make %s request to %s', method, url)
        response = urlopen(req, data=data).read().decode('utf-8')
        # self.logger.info(response)
        if get_raw:
            return response

        # Parse string and return JSON
        response = json.loads(response)
        return response

    def get(self, prepid):
        try:
            url = '%s/%s' % (self.couchdb_url, prepid)
            doc = self.__make_request(url)
            return doc
        except Exception as ex:
            self.logger.warning('Document "%s" was not found. Reason: %s' % (prepid, ex))
            return {}

    def document_exists(self, prepid):
        try:
            # Do only HEAD request
            url = '%s/%s' % (self.couchdb_url, prepid)
            doc = self.__make_request(url, method='HEAD', get_raw=True)
            return True
        except Exception as ex:
            self.logger.debug('Document exist check threw an exception: %s', (ex))
            return False

    def delete(self, prepid):
        self.logger.info('Will delete document "%s"' % (prepid))
        try:
            doc = self.get(prepid)
            doc['_deleted'] = True
            return self.update(doc)
        except Exception as ex:
            self.logger.error('Could not delete document %s. Reason: %s ' % (prepid, ex))
            return False

    def update(self, doc):
        try:
            prepid = doc['prepid']
            doc['_id'] = prepid
            url = '%s/%s' % (self.couchdb_url, prepid)
            response = self.__make_request(url, doc, method='PUT')
            return bool(response)
        except Exception as ex:
            self.logger.error('Could not update document %s. Reason: %s' % (doc.get('prepid', '<unknown>'), ex))
            return False

    def save(self, doc):
        try:
            prepid = doc['prepid']
            doc['_id'] = prepid
            url = '%s/%s' % (self.couchdb_url, prepid)
            response = self.__make_request(url, doc, method='PUT')
            return bool(response)
        except Exception as ex:
            self.logger.error('Could not save document %s. Reason: %s' % (doc.get('prepid', '<unknown>'), ex))
            return False

    def query_view(self, view_name, view_doc=None, options=None, get_raw=False):
        if not view_doc:
            view_doc = self.db_name

        # Link to view
        url = '%s/_design/%s/_view/%s' % (self.couchdb_url, view_doc, view_name)
        # Add query arguments
        if options:
            if options.get('startkey') and options['startkey'][0] != '"':
                options['startkey'] = '"%s' % (options['startkey'])

            if options.get('startkey') and options['startkey'][-1] != '"':
                options['startkey'] = '%s"' % (options['startkey'])

            if options.get('endkey') and options['endkey'][0] != '"':
                options['endkey'] = '"%s' % (options['endkey'])

            if options.get('endkey') and options['endkey'][-1] != '"':
                options['endkey'] = '%s"' % (options['endkey'])

            url += '?%s' % (self.dict_to_query(options))

        results = self.__make_request(url, get_raw=get_raw)
        if get_raw:
            return results

        results = results['rows']
        if options and options.get('include_docs', False):
            return [x['doc'] for x in results]

        return results

    def get_all(self, page_num=-1, limit=20, get_raw=False):
        try:
            limit, skip = self.__pagify(page_num, limit)
            options = {'limit': limit, 'skip': skip, 'include_docs': True}
            return self.query_view('all', options=options, get_raw=get_raw)
        except Exception as ex:
            self.logger.error('Error getting all for %s. Reason: %s' % (self.db_name, ex))
            return []

    def query_view_uniques(self, view_name, options=None):
        results = self.query_view(view_name=view_name,
                                  view_doc='unique',
                                  options=options)
        return {'results': [str(x['key']) for x in results]}

    def query(self, query=None, page_num=0, limit=20):
        if not query:
            result = self.get_all(page_num, limit)
            return result

        try:
            self.logger.debug('Executing query view code')
            try:
                tokens = self.__extract_operators(query)
            except Exception as ex:
                self.logger.error('Could not parse query %s. Reason: %s', query, ex)
                return []

            if not tokens:
                return []

            view_name, view_opts = self.__build_query(tokens)
            if not view_name or not view_opts:
                return []

            limit, skip = self.__pagify(page_num, limit)
            view_opts['limit'] = limit
            view_opts['skip'] = skip
            view_opts['include_docs']=True
            return self.query_view(view_name, options=view_opts)
        except Exception as ex:
            self.logger.error('Could not load view for query: <%s> . Reason: %s' % (query, ex))
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
        """
        Return page size and number of documents to skip
        For page < 0 return first page and large page size
        """
        if page_num < 0:
            return 1499, 0

        limit = max(1, limit)
        return limit, limit * page_num

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
        elif isinstance(val, bytes):
            kval = val.decode('ascii')
        else:
            kval = str(val)
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

    def construct_lucene_query(self, query, boolean_operator="AND"):
        """
        constructs key:value dictionary to couchDB lucene query
        """
        constructed_query = ""
        for param in query:
            if isinstance(query[param], list):
                for ind, el in enumerate(query[param]):
                    constructed_query += param + ':' + self.escapeLuceneArg(el.replace(" ", "+"))
                    if ind != len(query[param]) - 1:
                        ##we are not adding AND in the end of partially constructed query
                        constructed_query += "+%s+" % boolean_operator
            else:
                query[param] = query[param].replace(" ", "+")
                constructed_query += param + ':' + self.escapeLuceneArg(query[param])
            if constructed_query != "":
                constructed_query += '+%s+' % boolean_operator
        ##we remove the +AND+ in the end of query
        return constructed_query[:-(len(boolean_operator) + 2)]

    def construct_lucene_complex_query(self, query):
        """
        constructs key:value dictionary to couchDB lucene query
        input Query format:
        [
            (param1, {
                value: [val1,val2,val3],
                join_list_with: 'OR',
                open_parenthesis: True
            }),
            (param2, {
                join_operator: 'OR',
                value: 'val1',
                close_parenthesis: True
            }),
            (param3, {
                join_operator: 'AND',
                value: [val1,val2,val3],
                join_list_with: 'AND'
            })
        ]
        Output: ((param1:val1+OR+param1:val2+OR+param1:val3)+OR+param2:val1)+AND+(param3:val1+AND+param3:val2+AND+param3:val3)
        """
        constructed_query = ""
        boolean_operator = ""
        for pair in query:
            param = pair[0]
            if constructed_query != "":
                boolean_operator = pair[1]['join_operator'] if 'join_operator' in pair[1] else 'AND'
                constructed_query += '+%s+' % boolean_operator
            open_parenthesis = '(' if 'open_parenthesis' in pair[1] and pair[1]['open_parenthesis'] else ''
            constructed_query += open_parenthesis
            value = pair[1]['value']
            if isinstance(value, list):
                join_list_with = pair[1]['join_list_with'] if 'join_list_with' in pair[1] else 'OR'
                constructed_query += '('
                for ind, el in enumerate(value):
                    constructed_query += param + ':' + self.escapeLuceneArg(el.replace(" ", "+"))
                    if ind != len(value) - 1:
                        constructed_query += "+%s+" % join_list_with
                constructed_query += ')'
            else:
                value = value.replace(" ", "+")
                constructed_query += param + ':' + self.escapeLuceneArg(value)
            close_parenthesis = ')' if 'close_parenthesis' in pair[1] and pair[1]['close_parenthesis'] else ''
            constructed_query += close_parenthesis
        return constructed_query

    def full_text_search(self, index_name, query, page=0, limit=20, include_fields=None, sort=None):
        """
        queries loadView method with lucene interface for full text search
        """
        self.logger.info('%s %s %s %s', index_name, query, page, limit)
        limit, skip = self.__pagify(page, limit)
        try:
            options = {'limit': limit,
                       'skip': skip,
                       'include_docs': True,
                       'sort': '_id<string>'}
            options.pop('sort', None)
            if include_fields:
                options['include_fields'] = include_fields

            if sort:
                options['sort'] = sort

            data = self.load_lucene_view(query, view_name=index_name, options=options)
        except Exception as ex:
            self.logger.error('DB: %s Index: %s lucene query: %s error: %s',
                              self.db_name,
                              index_name,
                              query,
                              ex)
            return []

        if include_fields:
            return [x['fields'] for x in data['rows']]

        return [x['doc'] for x in data['rows']]

    def dict_to_query(self, args):
        options_str = dict()
        for key, value in args.items():
            if isinstance(value, str):
                options_str[key] = value
            else:
                options_str[key] = json.dumps(value)

        return urllib.parse.urlencode(options_str)

    def load_lucene_view(self, query, view_doc=None, view_name=None, options=None):
        """
        Example: localhost:5985/local/campaigns/_design/lucene/search?q=prepid:Run3*&include_docs=true
        """
        if view_doc is None:
            view_doc = 'lucene'

        if view_name is None:
            view_name = 'search'

        url = '%s/_design/%s/%s?q=%s' % (self.lucene_url, view_doc, view_name, query)

        if options:
            url += '&%s' % (self.dict_to_query(options))

        results = self.__make_request(url)
        return results
