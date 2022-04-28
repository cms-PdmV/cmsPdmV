import datetime
from couchdb_layer.mcm_database import Database
from rest_api.api_base import RESTResource
from tools.locker import Locker
from tools.ssh_executor import SSHExecutor
from tools.config_manager import Config
from model.user import User, Role
from tools.settings import Settings
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

        with Locker.get_lock(key):
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
        return {"results": Locker.get_status()}


class GetQueueInfo(RESTResource):

    def get(self):
        from tools.handlers import submit_pool
        data = {"submission_len": submit_pool.get_queue_length()}
        return data


class CacheClear(RESTResource):

    def get(self):
        """
        Clear McM cache
        """
        Database.clear_cache()
        Settings.clear_cache()
        User.clear_cache()
        return {'results': True}
