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


class GetLocksInfo(RESTResource):
   def __init__(self):
       self.access_limit = access_rights.administrator
       self.before_request()
       self.count_call()

   def get(self):
       from tools.locker import locker
       data = {"RLocks" : locker.lock_dictionary, "Locks" : locker.thread_lock_dictionary}
       return {"locks_len": len(data), "locks_data": str(data)}

class GetQueueInfo(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        self.before_request()
        self.count_call()

    def get(self):
        from tools.handlers import submit_pool
        data = {"submission_len": submit_pool.get_queue_length()}
        return data
