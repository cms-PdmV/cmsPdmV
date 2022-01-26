from couchdb_layer.mcm_database import database as Database
from json_layer.json_base import json_base
from tools.connection_wrapper import ConnectionWrapper
from tools.config_manager import Config
from tools.locker import locker


class Batch(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'history': [],
        'notes': '',
        'requests': [],
        'status': '',
    }

    @classmethod
    def get_database(cls):
        """
        Return shared database instance
        """
        if not hasattr(cls, 'database'):
            cls.database = Database('batches')

        return cls.database

    def add_request(self, prepid, workflow):
        """
        Add request and workflow to the batch
        """
        requests = self.get_attribute('requests')
        requests.append([prepid, workflow])
        requests = sorted(requests)
        self.set_attribute('requests', requests)
        self.update_history('add request', prepid)

    def remove_request(self, prepid):
        """
        Remove all entries of given request from the batch
        """
        requests = self.get_attribute('requests')
        requests = [r for r in requests if r[0] != prepid]
        self.set_attribute('requests', requests)
        self.update_history('remove request', prepid)

    def announce(self):
        """
        Set all workflow in ReqMgr2 to assignment-approved
        """
        host = Config.get('reqmgr_host')
        cert = Config.get('grid_cert')
        key = Config.get('grid_key')
        prepid = self.get('prepid')
        campaign = prepid.split('-')[0]
        with locker.lock(f'batch-{campaign}'):
            if self.get('status') != 'new':
                raise Exception('Only new batches can be announced')

            requests = self.get('requests')
            self.logger.info('Announcing batch %s with %s workflows', prepid, len(requests))
            with ConnectionWrapper(host, cert_file=cert, key_file=key) as connection:
                for workflow, prepid in requests:
                    self.logger.info('Approving %s for %s', workflow, prepid)
                    if not self.approve_workflow(workflow, connection):
                        raise Exception('Could not approve %s' % (workflow))

            self.update_history('status', 'announced')
            self.set('status', 'announced')
            self.reload(save=True)

    def approve_workflow(self, workflow_name, connection):
        """
        Approve workflow in ReqMgr2
        """
        headers = {'Content-type': 'application/json',
                   'Accept': 'application/json'}
        try:
            # Try to approve workflow (move to assignment-approved)
            # If it does not succeed, ignore failure
            connection.api('PUT',
                           f'/reqmgr2/data/request/{workflow_name}',
                           {'RequestStatus': 'assignment-approved'},
                           headers)
        except Exception as ex:
            self.logger.error('Error approving %s: %s', workflow_name, str(ex))
            return False

        return True
