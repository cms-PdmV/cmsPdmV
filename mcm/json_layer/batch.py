from couchdb_layer.mcm_database import database as Database
from json_layer.json_base import json_base
from tools.connection_wrapper import ConnectionWrapper
from tools.config_manager import Config
from tools.locker import locker
from tools.settings import Settings


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

    @classmethod
    def add_to_batch(cls, campaign, prepid, workflow):
        """
        Add request prepid and workflow to a batch
        If last batch is full, start a new one and add there
        Return batch that request was added to
        """
        batch_db = Batch.get_database()
        batch_threshold = Settings.get('max_in_batch')
        with locker.lock(f'batch-{campaign}'):
            # Get the newest batch, any status
            newest_batches = batch_db.search({'prepid': f'{campaign}-*'}, limit=1, sort_asc=False)
            # Get the batch
            batch = newest_batches[0] if newest_batches else None
            # Checks for the batch
            if not batch or batch['status'] != 'new' or len(batch['requests']) >= batch_threshold:
                batch = cls.new_batch(campaign)
                batch.update_history('create')
                cls.logger.info('Created new batch %s for %s', batch.get('prepid'), prepid)
            else:
                batch = Batch(batch)
                cls.logger.info('Using existing batch %s for %s', batch.get('prepid'), prepid)

            batch.add_request(prepid, workflow)
            batch.save()

        return batch

    @classmethod
    def new_batch(cls, campaign):
        """
        Create a new batch with a unique prepid and return it
        """
        batch_db = Batch.get_database()
        with locker.lock('batch-prepid-%s' % (campaign)):
            prepid = batch_db.get_next_prepid(campaign, [campaign])
            batch = Batch({'_id': prepid,
                           'prepid': prepid})
            batch.save()
            cls.logger.info('New batch created: %s ', prepid)

        return batch
