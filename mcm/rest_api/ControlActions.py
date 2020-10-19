import flask

from collections import defaultdict

from rest_api.RestAPIMethod import RESTResource
from tools.ssh_executor import ssh_executor
from tools.user_management import access_rights, authenticator
import tools.settings as settings
from json import dumps, loads

from tools.communicator import communicator
from couchdb_layer.mcm_database import database


class RenewCertificate(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        """
        Renew certificates on our request upload/injection machines
        """
        # machines = ["cms-pdmv-op.cern.ch"]
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


class ChangeVerbosity(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, level):
        """
        Change verbosity of logger
        """
        if settings.set_value('log_verbosity', level):
            # TO-DO:
            # do we really need this?
            self.logger.info("We want to set log verbosity to: %s" % (level))
            # self.logger.set_verbosity(level)
        else:
            return {"results": False, "message": "Couldn't save new verbosity to database"}
        return {"results": True, "message": "New verbosity for logger: {0}".format(level)}


class Communicate(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, message_number=0):
        """
        Trigger the accumulated communications from McM, optionally above /N messages
        """
        com = communicator()
        res = com.flush(message_number)
        return {'results': True, 'subject' : res}


class Search(RESTResource):
    """
    Super-generic search through database (uses __all__ attribute in __init__.py of json_layer package)
    """

    access_limit = access_rights.user

    def __init__(self):
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
        include_fields = ''
        db_name = args.pop('db_name', 'requests').strip()
        page = int(args.pop('page', 0))
        limit = int(args.pop('limit', 20))
        get_raw = args.pop('get_raw', False) # Unused
        include_fields = args.pop('include_fields', '').strip()
        if 'keep_output' in args:
            args['keep_output'] = args['keep_output'].replace(',', '_')

        if page == -1 and not args and db_name == 'requests':
            return {'results': False, 'message': 'Why you stupid? Don\'t be stupid...'}

        res = self.search(args, db_name=db_name, page=page, limit=limit, include_fields=include_fields)
        return {'results': res}

    def search(self, args, db_name, page=-1, limit=0, include_fields=''):
        db = database(db_name)
        if args:
            args = self.prepare_typed_args(args, db_name)
            lucene_query = db.construct_lucene_query(args)
            res = db.full_text_search('search',
                                      lucene_query,
                                      page=page,
                                      limit=limit,
                                      include_fields=str(include_fields))
        else:
            res = db.get_all(page, limit)

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
                self.__add_previous_to_search(search, previous[i:i + 100], i)
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
            self.__add_previous_to_search(search, previous[i:i + 100], i)
            partial_result = self.search(search['search'], search['db_name'])
            current_len += len(partial_result)
            if start_adding:
                subskip += len(partial_result)
                res.extend(partial_result)
            if current_len >= skip and not start_adding:
                subskip = current_len - skip
                start_adding = True
                res.extend(partial_result)
            if current_len >= skip + limit:
                break
        return {"results": res[-subskip:len(res) - subskip + limit] if page != -1 else res}


class CacheInfo(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        """
        Get information about cache sizes in McM
        """
        db = database('requests')
        db_cache_length, db_cache_size = db.cache_size()
        settings_cache_length, settings_cache_size = settings.cache_size()
        user_cache_length, user_cache_size = authenticator.cache_size()
        return {'results': {'db_cache_length': db_cache_length,
                            'db_cache_size': db_cache_size,
                            'settings_cache_length': settings_cache_length,
                            'settings_cache_size': settings_cache_size,
                            'user_cache_length': user_cache_length,
                            'user_cache_size': user_cache_size}}

class CacheClear(RESTResource):

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        """
        Clear McM cache
        """
        db = database('requests')
        db.clear_cache()
        settings.clear_cache()
        authenticator.clear_cache()
        db_cache_length, db_cache_size = db.cache_size()
        settings_cache_length, settings_cache_size = settings.cache_size()
        user_cache_length, user_cache_size = settings.cache_size()
        return {'message': 'Cleared caches',
                'results': {'db_cache_length': db_cache_length,
                            'db_cache_size': db_cache_size,
                            'settings_cache_length': settings_cache_length,
                            'settings_cache_size': settings_cache_size,
                            'user_cache_length': user_cache_length,
                            'user_cache_size': user_cache_size}}
