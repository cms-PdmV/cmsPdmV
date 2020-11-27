#!/usr/bin/env python
import os

from RestAPIMethod import RESTResource
from tools.ssh_executor import ssh_executor
from tools.user_management import access_rights
import subprocess


class GetBjobs(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, options=''):
        """
        Get bjobs information regarding the condor clusters
        """
        with ssh_executor() as ssh_exec:
            stdin, stdout, stderr = ssh_exec.execute(self.create_command(options))
            out = stdout.read()
            err = stderr.read()
            if err:
                return {"results": err}
            return {"results": out}

    def create_command(self, options):
        bcmd = 'module load lxbatch/tzero && condor_q -nobatch | grep -v RELMON_ '
        for opt in options.split(','):
            bcmd += opt
        return bcmd


class GetLogFeed(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self, filename, lines=-1):
        """
        Gets a number of lines from given log.
        """
        name = os.path.join('logs', os.path.basename(filename))
        return self.read_logs(name, lines)

    def read_logs(self, name, nlines):
        if not os.path.isfile(name):
            return {'results': 'Error: File "%s" does not exist' % (name)}

        if nlines > 0:
            command = 'tail -n%d %s' % (nlines, name)
        else:
            command = 'cat %s' % (name)

        read_process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        data = read_process.communicate()[0]
        return {"results": data}


class GetRevision(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        """
        returns the current tag of the software running
        """
        import subprocess
        output = subprocess.Popen(["git", "describe", "--tags", "--abbrev=0"], stdout=subprocess.PIPE)
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

    access_limit = access_rights.user

    def __init__(self):
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

    access_limit = access_rights.administrator

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        from tools.locker import locker, semaphore_events
        pretty_r_locks = {}
        for key, lock in locker.lock_dictionary.iteritems():
            pretty_r_locks[key] = '%s %s' % (key, str(lock))

        pretty_locks = {}
        for key, lock in locker.thread_lock_dictionary.iteritems():
            pretty_locks[key] = '%s %s' % (key, str(lock))

        return {"r_locks": pretty_r_locks,
                "locks (thread)": pretty_locks,
                "semaphores": semaphore_events.count_dictionary}

class GetQueueInfo(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        self.before_request()
        self.count_call()

    def get(self):
        from tools.handlers import submit_pool
        data = {"submission_len": submit_pool.get_queue_length()}
        return data
