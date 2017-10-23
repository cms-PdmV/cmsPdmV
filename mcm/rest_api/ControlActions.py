import flask

from collections import defaultdict

from RestAPIMethod import RESTResource
from tools.ssh_executor import ssh_executor
from tools.user_management import access_rights
from tools.settings import settings
from json import dumps, loads

from tools.locker import locker
from tools.communicator import communicator
from couchdb_layer.mcm_database import database
from tools.locator import locator


class RenewCertificate(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator
        self.before_request()
        self.count_call()

    def get(self):
        """
        Renew certificates on our request upload/injection machines
        """
        #machines = ["cms-pdmv-op.cern.ch"]
        machines = ["vocms081.cern.ch"]
        for elem in machines:
            ssh_exec = ssh_executor(server=elem)
            try:
                self.logger.info("Renewing certificate for: %s" % (elem))
                stdin, stdout, stderr = ssh_exec.execute(self.create_command(elem))
                self.logger.info("Certificate renewed:\n{0}".format(stdout.read()))
            finally:
                ssh_exec.close_executor()

    def create_command(self, machine):
            # crab setup
            command = 'source /cvmfs/cms.cern.ch/crab3/crab.sh \n'
            # certificate
            command += 'cat /afs/cern.ch/user/p/pdmvserv/private/PdmVService.txt | voms-proxy-init -voms cms --valid 240:00 -pwstdin --key /afs/cern.ch/user/p/pdmvserv/private/$HOSTNAME/userkey.pem --cert /afs/cern.ch/user/p/pdmvserv/private/$HOSTNAME/usercert.pem --out /afs/cern.ch/user/p/pdmvserv/private/$HOSTNAME/voms_proxy.cert 2> /dev/null \n'
            command += 'cat /afs/cern.ch/user/p/pdmvserv/private/PdmVService.txt | voms-proxy-init -voms cms --valid 240:00 -pwstdin --key /afs/cern.ch/user/p/pdmvserv/private/personal/userkey.pem --cert /afs/cern.ch/user/p/pdmvserv/private/personal/usercert.pem --out /afs/cern.ch/user/p/pdmvserv/private/personal/voms_proxy.cert 2> /dev/null \n'
            return command


#class ChangeVerbosity(RESTResource):
#    def __init__(self):
#        self.access_limit = access_rights.administrator
#
#    def GET(self, *args):
#        """
#        Change verbosity of logger
#        """
#        if not args:
#            return dumps({"results": False, "message": "No new verbosity given"})
#        try:
#            lvl = int(args[0])
#        except ValueError:
#            return dumps({"results": False, "message": "New verbosity was not an integer"})
#
#        if settings().set_value('log_verbosity', lvl):
#            ##TO-DO:
#            # do we really need this?
#            self.logger.info("We want to set log verbosity to: %s" % (lvl))
#            #self.logger.set_verbosity(lvl)
#        else:
#            return dumps({"results": False, "message": "Couldn't save new verbosity to database"})
#        return dumps({"results": True, "message": "New verbosity for logger: {0}".format(lvl)})


#class TurnOffServer(RESTResource):
#    def __init__(self):
#        self.access_limit = access_rights.administrator
#
#    def GET(self, *args):
#        """
#        Turn off server.
#        """
#        self.logger.info("Shutting down the server")
#        cherrypy.engine.exit()


#class ResetRESTCounters(RESTResource):
#    def __init__(self):
#        self.access_limit = access_rights.administrator
#
#    def GET(self, *args):
#        """
#        Reset counters
#        """
#        res = {}
#        with locker.lock("rest-call-counter"):
#            for arg in args:
#                if arg in RESTResource:
#                    RESTResource.counter[arg] = 0
#                    res[arg] = True
#                else:
#                    res[arg] = False
#            if not args:
#                for key in RESTResource.counter:
#                    RESTResource.counter[key] = 0
#                    res[key] = True
#            return dumps(res)

class Communicate(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator
        self.before_request()
        self.count_call()

    def get(self, message_number=0):
        """
        Trigger the accumulated communications from McM, optionally above /N messages
        """
        com = communicator()
        res=com.flush(message_number)
        return {'results':True, 'subject' : res}

def output_text(data, code, headers=None):
    """Makes a Flask response with a plain text encoded body"""
    print 'hola'
    resp = flask.make_response(data, code)
    resp.headers.extend(headers or {})
    return resp

class Search(RESTResource):
    """
    Super-generic search through database (uses __all__ attribute in __init__.py of json_layer package)
    """

    def __init__(self):
        self.access_limit = access_rights.user
        self.before_request()
        self.casting = defaultdict(lambda: defaultdict(lambda: ""))
        self.type_dict = defaultdict(lambda: defaultdict(lambda: basestring))
        import json_layer
        for module in json_layer.__all__:
            mod_obj = getattr(json_layer, module)
            class_obj = getattr(mod_obj, module)
            key_name = module if module.endswith("s") else module + "s"  # key name that can be resolved to database name
            if module is 'batch':
                key_name = 'batches'  # bleh, special case
            schema = class_obj.class_schema()
            if schema:
                for schema_key in schema:
                    self.type_dict[key_name][schema_key] = type(schema[schema_key])
                    if type(schema[schema_key]) in [int, float]:
                        self.casting[key_name][schema_key] = "<" + type(schema[schema_key]).__name__ + ">"

    def get(self):
        args = flask.request.args.to_dict()
        db_name = 'requests'
        page = 0
        limit = 20
        get_raw = False
        include_fields = ''
        if 'db_name' in args:
            db_name = args['db_name']
            args.pop('db_name')
        if 'page' in args:
            page = int(args['page'])
            args.pop('page')
        if 'limit' in args:
            limit = int(args['limit'])
            args.pop('limit')
        if 'get_raw' in args:
            get_raw = True
            args.pop('get_raw')
        if 'include_fields' in args:
            include_fields = args['include_fields']
            args.pop('include_fields')
        res = self.search(args, db_name=db_name, page=page, limit=limit, get_raw=get_raw, include_fields=include_fields)
        if get_raw:
            self.representations = {'text/plain': output_text}
            return res
        else:
            return {"results": res}

    def search(self, args, db_name, page=-1, limit=0, get_raw=False, include_fields=''):
        odb = database(db_name)
        if args:
            args = self.prepare_typed_args(args, db_name)
            lucene_query = odb.construct_lucene_query(args)
            self.logger.info("lucene url: %s" % (lucene_query))
            res = odb.full_text_search("search", lucene_query, page=page,
                    limit=limit, get_raw=get_raw, include_fields=str(include_fields))

        else:
            res = odb.get_all(page, limit, get_raw=get_raw)
        return res

    def prepare_typed_args(self, args, db_name):
        for arg in args:
            args[arg + self.casting[db_name][arg]] = args.pop(arg)
        return args


class MultiSearch(Search):
    """
    Search getting all parameters from body of request and performing multiple searches
    takes in json containing list of consecutive searches. Page, limit and get_raw is
    taken into account only for last search:
    {
    page: PAGE,
    limit: LIMIT,
    searches: [
        {
            db_name: DBNAME1,
            use_previous_as: INPUT_PLACE_NAME1,
            return_field: OUTPUT_FIELD_NAME1,
            search: {search_dictionary1}
        },
        {
            db_name: DBNAME2,
            use_previous_as: INPUT_PLACE_NAME2 (so it's OUTPUT_FIELD_NAME1),
            return_field: OUTPUT_FIELD_NAME2,
            search: {search_dictionary2}
        }]
    }

    use_previous_as means how to use result of previous search query (on which field)
    return_field means value of which field should be used

    """

    @staticmethod
    def __add_previous_to_search(search, previous, iteration):
        if iteration:
            search['search'][search['use_previous_as']] = "(" + "+OR+".join(previous) + ")"
            return
        if 'use_previous_as' in search and search['use_previous_as']:
            if search['use_previous_as'] in search['search']:
                previous.append(search['search'][search['use_previous_as']])
            search['search'][search['use_previous_as']] = "(" + "+OR+".join(previous) + ")"

    def post(self):
        search_dicts = loads(flask.request.data)
        limit = 20
        page = 0
        if 'limit' in search_dicts:
            limit = int(search_dicts['limit'])
        if 'page' in search_dicts:
            page = int(search_dicts['page'])
        if page == -1:
            limit = 1000000000
            skip = 0
        else:
            skip = limit * page
        previous = []
        for search in search_dicts['searches'][:-1]:
            prev_len = len(previous)
            prev_len = prev_len if prev_len else 1
            new_previous = []
            flatten = self.type_dict[search['db_name']][search['return_field']] == list
            for i in range(0, prev_len, 100):
                self.__add_previous_to_search(search, previous[i:i+100], i)
                res = [x[search['return_field']] for x in self.search(search['search'], search['db_name'])]
                new_previous.extend([i for x in res for i in x] if flatten else res)

            previous = list(set(new_previous))

        search = search_dicts['searches'][-1]
        prev_len = len(previous)
        res = []
        current_len = 0
        subskip = 0
        start_adding = False
        # pagination by hand (so the whole thing won't break because of super-long queries)
        # MIGHT CAUSE DUPLICATIONS OF DOCUMENTS IN RESULTS!
        for i in range(0, prev_len, 100):
            self.__add_previous_to_search(search, previous[i:i+100], i)
            partial_result = self.search(search['search'], search['db_name'])
            current_len += len(partial_result)
            if start_adding:
                subskip += len(partial_result)
                res.extend(partial_result)
            if current_len >= skip and not start_adding:
                subskip = current_len - skip
                start_adding = True
                res.extend(partial_result)
            if current_len >= skip+limit:
                break
        return {"results": res[-subskip:len(res)-subskip+limit] if page != -1 else res}
