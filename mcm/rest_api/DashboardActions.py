#!/usr/bin/env python
import os

from RestAPIMethod import RESTResource
from tools.ssh_executor import ssh_executor
from tools.user_management import access_rights

class GetBjobs(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        self.before_request()
        self.count_call()

    def get(self, options=''):
        """
        Get bjobs information regarding the condor clusters
        """
        ssh_exec = ssh_executor()
        try:
            stdin, stdout, stderr = ssh_exec.execute(self.create_command(options))
            out = stdout.read()
            err = stderr.read()
            if err:
                return {"results": err}
            return {"results": out}
        finally:
            ssh_exec.close_executor()

    def create_command(self, options):
        bcmd = 'condor_q'
        for opt in options.split(','):
            bcmd += opt.strip()
        return bcmd


class GetLogFeed(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        self.before_request()
        self.count_call()

    def get(self, filename, lines=-1):
        """
        Gets a number of lines from given log.
        """
        name = os.path.join('logs', os.path.basename(filename))
        return self.read_logs(name, lines)

    def read_logs(self, name, nlines):

        with open(name) as log_file:
            try:
                data = log_file.readlines()
            except IOError as ex:
                self.logger.error('Could not access logs: "{0}". Reason: {1}'.format(name, ex))
                return {"results": "Error: Could not access logs."}

        if nlines > 0:
            data = data[-nlines:]
        return {"results": ''.join(data)}


class GetRevision(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        self.before_request()
        self.count_call()

    def get(self):
        """
        returns the current tag of the software running
        """
        import subprocess
        output = subprocess.Popen(["git", "describe", "--abbrev=0"], stdout=subprocess.PIPE)
        revision = output.communicate()[0]
        return revision


class GetStartTime(RESTResource):
    def __init__(self, start_time):
        self.time = start_time
        self.before_request()
        self.count_call()

    def get(self):
        """
        Get the time at which the server was started.
        """
        return {"results": self.time}


class GetLogs(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        self.path = "logs"
        self.before_request()
        self.count_call()

    def get(self):
        """
        Gets a list of logs sorted by date.
        """

        files_dates = sorted([{"name": filename, "modified": os.path.getmtime(os.path.join(self.path, filename))}
                              for filename in os.listdir(self.path)
                              if os.path.isfile(os.path.join(self.path, filename))], key=lambda x: x["modified"],
                             reverse=True)

        return {"results": files_dates}


#class TestConnection(RESTResource):
#    ## a rest api to make a creation test of a request
#    def __init__(self):
#        self.counter = 0
#
#    def GET(self, *args):
#        """
#        this is test of connection through ssh to /node/iterations
#        """
#        sta=0
#        sto=0
#        spend=[]
#        server=args[0]
#        N=int(args[1])
#        success=0
#        fail=0
#        for i in range(N):
#            sta=time.time()
#            connect = ssh_executor(server=server)
#            try:
#                _, stdout, stderr = connect.execute('ls $HOME')
#                out = stdout.read()
#                err = stderr.read()
#                if ('private' in out and 'public' in out and 'PdmV' in out):
#                    success+=1
#                    self.logger.info("test: %s SUCCESS \n out:\n%s \n err:\n %s" % (i, out,err))
#                else:
#                    tail+=1
#                    self.logger.info("test: %s failed \n out:\n%s \n err:\n %s" % (i, out,err))
#            except:
#                fail+=1
#                self.logger.error("test: %s failed %s" % (i, traceback.format_exc()))
#
#            sto=time.time()
#            spend.append( sto - sta )
#
#        mean = sum(spend) / len(spend)
#        rms = sqrt(sum( map( lambda v : (v-mean)*(v-mean), spend)) / len(spend))
#
#        return dumps({"server" : server,
#                      "trials" : N,
#                      "time": spend,
#                      "mean": mean,
#                      "rms": rms,
#                      "success" : success,
#                      "fail" : fail,
#                      "max" : max(spend),
#                      "min": min(spend),
#                      "total" : sum(spend)
#                      })

#class ListReleases(RESTResource):
#    def __init__(self):
#        pass
#    def GET(self, *args):
#        """
#        Give out the list of releases that are being used through McM campaigns in optional status /status
#        """
#        status=None
#        if len(args):
#            status=args[0]
#        cdb = database('campaigns')
#
#        if status:
#            __query = cdb.construct_lucene_query({'status' : status})
#            cs = cdb.full_text_search('search', __query, page=-1)
#        else:
#            cs = cdb.get_all()
#
#        releases_set=set()
#        releases=defaultdict(lambda : list())
#        for c in cs:
#            if c['cmssw_release'] and not c['cmssw_release'] in releases[c['status']]:
#                releases[c['status']].append(c['cmssw_release'])
#                releases_set.add(c['cmssw_release'])
#
#
#        ##extend to submitted requests, or chained requests that will get in the system ?
#
#        return dumps({"results" : releases, "set" : list(releases_set)})


#class GetLocksInfo(RESTResource):
#   def __init__(self):
#       self.access_limit = access_rights.administrator

#   def GET(self, *args):
#       from tools.locker import locker
#       data = {"RLocks" : locker.lock_dictionary, "Locks" : locker.thread_lock_dictionary}
#       return dumps({"locks_len": len(data), "locks_data": str(data)})

class GetQueueInfo(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        self.before_request()
        self.count_call()

    def get(self):
        from tools.handlers import submit_pool
        data = {"submission_len": submit_pool.get_queue_length()}
        return data
