from json_layer.batch import Batch
from tools.locker import locker
from tools.settings import Settings


class BatchManager():

    logger = Batch.logger

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
