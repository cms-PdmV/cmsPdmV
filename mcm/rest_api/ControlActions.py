from RestAPIMethod import RESTResource
from tools.ssh_executor import ssh_executor
from tools.user_management import access_rights
from tools.settings import settings
from simplejson import dumps
from tools.locker import locker
from tools.communicator import communicator
from collections import defaultdict
import cherrypy
import simplejson
from couchdb_layer.mcm_database import database
from tools.locator import locator


class RenewCertificate(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Renew certificate on pdmvserv-test.cern.ch
        """
        ssh_exec = ssh_executor(server='pdmvserv-test.cern.ch')
        try:
            self.logger.log("Renewing certificate")
            stdin, stdout, stderr = ssh_exec.execute(self.create_command())
            self.logger.log("Certificate renewed:\n{0}".format(stdout.read()))
        finally:
            ssh_exec.close_executor()

    def create_command(self):
            # crab setup
            command = 'source /afs/cern.ch/cms/LCG/LCG-2/UI/cms_ui_env.sh ; source /afs/cern.ch/cms/ccs/wm/scripts/Crab/crab.sh \n'
            # certificate
            command += 'cat /afs/cern.ch/user/p/pdmvserv/private/PdmVService.txt | voms-proxy-init -voms cms --valid 240:00 -pwstdin --key /afs/cern.ch/user/p/pdmvserv/private/$HOST/userkey.pem --cert /afs/cern.ch/user/p/pdmvserv/private/$HOST/usercert.pem --out /afs/cern.ch/user/p/pdmvserv/private/$HOST/voms_proxy.cert 2> /dev/null \n'
            command += 'cat /afs/cern.ch/user/p/pdmvserv/private/PdmVService.txt | voms-proxy-init -voms cms --valid 240:00 -pwstdin --key /afs/cern.ch/user/p/pdmvserv/private/personal/userkey.pem --cert /afs/cern.ch/user/p/pdmvserv/private/personal/usercert.pem --out /afs/cern.ch/user/p/pdmvserv/private/personal/voms_proxy.cert 2> /dev/null \n'
            return command


class ChangeVerbosity(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Change verbosity of logger
        """
        if not args:
            return dumps({"results": False, "message": "No new verbosity given"})
        try:
            lvl = int(args[0])
        except ValueError:
            return dumps({"results": False, "message": "New verbosity was not an integer"})

        if settings().set_value('log_verbosity', lvl):
            self.logger.set_verbosity(lvl)
        else:
            return dumps({"results": False, "message": "Couldn't save new verbosity to database"})
        return dumps({"results": True, "message": "New verbosity for logger: {0}".format(lvl)})


class TurnOffServer(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Turn off server.
        """
        self.logger.log("Shutting down the server")
        cherrypy.engine.exit()


class ResetRESTCounters(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Reset counters
        """
        res = {}
        with locker.lock("rest-call-counter"):
            for arg in args:
                if arg in RESTResource:
                    RESTResource.counter[arg] = 0
                    res[arg] = True
                else:
                    res[arg] = False
            if not args:
                for key in RESTResource.counter:
                    RESTResource.counter[key] = 0
                    res[key] = True
            return dumps(res)

class Communicate(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Trigger the accumulated communications from McM, optionally above /N messages
        """
        N=0
        if len(args):
            N=args[0]
        com = communicator()
        res=com.flush(N)

        return dumps({'results':True, 'subject' : res})


class Search(RESTResource):
    """
    Super-generic search through database (uses __all__ attribute in __init__.py of json_layer package)
    """

    def __init__(self):
        self.casting = defaultdict(lambda: defaultdict(lambda: ""))
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
                    if type(schema[schema_key]) in [int, float]:
                        self.casting[key_name][schema_key] = "<" + type(schema[schema_key]).__name__ + ">"

    def GET(self, **args):
        db_name = 'requests'
        page = 0
        limit = 20
        get_raw = False
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
        res = self.search(args, db_name=db_name, page=page, limit=limit, get_raw=get_raw)
        return res if get_raw else dumps({"results": res})

    def search(self, args, db_name, page=-1, limit=0, get_raw=False):
        odb = database(db_name)
        if args:
            args = self.prepare_typed_args(args, db_name)
            lucene_query = odb.construct_lucene_query(args)
            self.logger.log("lucene url: %s" % (lucene_query) )
            res = odb.full_text_search("search", lucene_query, page=page, limit=limit, get_raw=get_raw)
        else:
            res = odb.get_all(page, limit, get_raw=get_raw)
        return res

    def prepare_typed_args(self, args, db_name):
        for arg in args:
            args[arg + self.casting[db_name][arg]] = args.pop(arg)
        return args
