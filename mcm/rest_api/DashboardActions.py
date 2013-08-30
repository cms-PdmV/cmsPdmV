#!/usr/bin/env python

from RestAPIMethod import RESTResource
from tools.ssh_executor import ssh_executor
from json import dumps
import os


class GetBjobs(RESTResource):
    def __init__(self):
        self.authenticator.set_limit(0)

    def GET(self, *args):
        """
        Get bjobs information regarding the batch jobs
        """
        ssh_exec = ssh_executor()
        try:
            stdin, stdout, stderr = ssh_exec.execute(self.create_command(args))
            out = stdout.read()
            err = stderr.read()
            if err:
                if "No job found in job group" in err:  # so the shown string is consistent with production
                    return dumps({"results": 'No unfinished job found'})
                return dumps({"results": err})
            return dumps({"results": out})
        finally:
            ssh_exec.close_executor()

    def create_command(self, options):
        bcmd = 'bjobs'
        for opt in options:
            if '-g' in opt:
                bcmd += ' -g ' + '/' + '/'.join(opt.split()[1:])
            else:
                bcmd += opt
        return bcmd


class GetLogFeed(RESTResource):
    def __init__(self):
        self.authenticator.set_limit(0)

    def GET(self, *args):
        """
        Gets a number of lines from given log.
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})
        name = os.path.join('logs', args[0])
        nlines = -1
        if len(args) > 1:
            nlines = int(args[1])
        return self.read_logs(name, nlines)

    def read_logs(self, name, nlines):

        with open(name) as log_file:
            try:
                data = log_file.readlines()
            except IOError as ex:
                self.logger.error('Could not access logs: "{0}". Reason: {1}'.format(name, ex))
                return dumps({"results": "Error: Could not access logs."})

        if nlines > 0:
            data = data[-nlines:]
        return dumps({"results": ''.join(data)})


class GetLogs(RESTResource):
    def __init__(self):
        self.authenticator.set_limit(0)
        self.path = "logs"

    def GET(self, *args):
        """
        Gets a list of logs sorted by date.
        """

        files_dates = sorted([{"name": filename, "modified": os.path.getmtime(os.path.join(self.path, filename))}
                              for filename in os.listdir(self.path)
                              if os.path.isfile(os.path.join(self.path, filename))], key=lambda x: x["modified"],
                             reverse=True)

        return dumps({"results": files_dates})


