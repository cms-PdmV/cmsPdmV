import datetime
from rest_api.RestAPIMethod import RESTResource
from json_layer.user import Role
from tools.locker import Locker
from tools.ssh_executor import SSHExecutor
from tools.config_manager import Config
from cachelib import SimpleCache


class GetValidationInfo(RESTResource):

    __cache = SimpleCache(default_timeout=120) # 2 minutes

    def get(self):
        """
        Get information about validation jobs in HTCondor
        Cache results for a few minutes as well as limit to only one executtion
        at a time
        """
        key = 'validation_info'
        cached = self.__cache.get(key)
        if cached:
            self.logger.debug('Found cached results for validation info')
            return {'results': cached}

        with Locker().lock(key):
            cached = self.__cache.get(key)
            if cached:
                self.logger.debug('Found cached results for validation info')
                return {'results': cached}

            host = 'lxplus'
            credentials = Config.get('ssh_auth')
            with SSHExecutor(host, credentials) as ssh:
                command = 'module load lxbatch/tzero && condor_q -nobatch -wide | grep -v RELMON'
                output, error, _ = ssh.execute_command(command)
                if error:
                    self.__cache.set(key, error)
                    return {'results': error}
                else:
                    self.__cache.set(key, output)
                    return {'results': output}


class GetStartTime(RESTResource):

    start_time = datetime.datetime.now().strftime('%c')
    def get(self):
        """
        Get the time at which the server was started.
        """
        return {'results': self.start_time}


class GetLocksInfo(RESTResource):

    @RESTResource.ensure_role(Role.ADMINISTRATOR)
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

    def get(self):
        from tools.handlers import submit_pool
        data = {"submission_len": submit_pool.get_queue_length()}
        return data
