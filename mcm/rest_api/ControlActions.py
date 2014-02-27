from RestAPIMethod import RESTResource
from tools.ssh_executor import ssh_executor
from tools.user_management import access_rights
from tools.settings import settings
from json import dumps
from tools.locker import locker
from tools.communicator import communicator
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
    Super-generic search through database
    """

    def search(self, db_name, query, page, query_list=[], limit=20):
        return self.run_query(database(db_name), query, query_list, int(page), int(limit))

    def run_query(self, db, query, query_list, page, limit):
        results = dict()
        results['results'] = []
        if len(query_list):
            results_list = db.queries(query_list, limit)
            results['results'] = results_list
        else:
            if not query or query == '""':
                res = db.get_all(page_num=page, limit=limit)
            else:
                res = db.query(query, page_num=page, limit=limit)

            query_result = db.unique_res(res)
            results['results'] = query_result
        return simplejson.dumps(results)

    def GET(self, **args):
        db_name = 'requests'
        query = ''
        query_list = []
        page = 0
        limit = 20
        if 'db_name' in args:
            db_name = args['db_name']
            args.pop('db_name')
        if 'query' in args:
            query = args['query']
            args.pop('query')
        if 'page' in args:
            page = args['page']
            args.pop('page')
        if 'limit' in args:
            limit = args['limit']
            args.pop('limit')
        # retrieve the _design/object document
        odb = database(db_name)
        design = odb.get('_design/%s' % (db_name))
        allowed_key_search = design['views'].keys()

        vetoed_keys = []
        for (view, f) in design['views'].items():
            if 'for(' in f['map'] or 'for (' in f['map']:
                vetoed_keys.append(view)
        allowed_key_search.sort()
        multiple_view = []
        ####
        ## to switch on/off the view creation on the fly
        simple_search = (not locator().isDev())
        simple_search = False
        ####
        for key in filter(lambda s: '-' not in s, allowed_key_search):
            if key in args:
                if key in vetoed_keys or simple_search:
                    query_list.append('%s==%s' % (key, args[key]))
                else:
                    if args[key].isdigit():
                        multiple_view.append((key, args[key]))
                    else:
                        multiple_view.append((key, '"' + args[key] + '"'))

                args.pop(key)

        if len(multiple_view) > 1:
            multiple_search = '-'.join(map(lambda p: p[0], multiple_view))
            ## faster query with multiple keys
            if not multiple_search in allowed_key_search:
                ## try harder to find it
                really_not_there = True
                m_set = set(map(lambda p: p[0], multiple_view))
                for key in filter(lambda s: '-' in s, allowed_key_search):
                    ## parse all composite view
                    if set(key.split('-')) == m_set:
                        #we found one that has the same search in absolute, just the order is different
                        # then re-order multiple_view so as to map to the existing view
                        new_multiple_view = []
                        for sv in key.split('-'):
                            new_multiple_view.append(filter(lambda e: e[0] == sv, multiple_view)[0])
                        multiple_view = new_multiple_view
                        multiple_search = '-'.join(map(lambda p: p[0], multiple_view))
                        really_not_there = False
                        break
                if really_not_there:
                    #tempatively add the view to the design
                    new_func = "function(doc){ emit([%s], doc._id);}" % (
                    ','.join(map(lambda k: "doc.%s" % (k), map(lambda p: p[0], multiple_view))))
                    design['views'][multiple_search] = {"map": new_func}
                    saved = odb.update(design)
                    ##### NOTE ####
                    ## the query that will follow will be super slow because the view needs to be re-build

            m_query = '%s==[%s]' % (multiple_search,
                                    ','.join(map(lambda p: p[1], multiple_view))
            )
            query_list.append(m_query)
        #query_list =[]
        elif len(multiple_view) == 1:
            m_query = '%s==%s' % ( multiple_view[0][0], multiple_view[0][1])
            query_list.append(m_query)

        #revert to simple query for one query only
        if len(query_list) == 1:
            query = query_list[0]
            query_list = []

        if len(args):
            ## check whether the key is actually a member of the object in db and put back the view in the odb design
            return simplejson.dumps(args)
        #return simplejson.dumps(design['views'].keys())
        return self.search(db_name, query, page, query_list, limit)

