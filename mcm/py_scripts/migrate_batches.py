import logging
import json
import hashlib
from copy import deepcopy
from tools.config_manager import Config
from couchdb_layer.mcm_database import Database


Config.load('../config.cfg', 'development')
database = Database('batches')
logging.basicConfig(format='[%(asctime)s][%(levelname)s] %(message)s', level=logging.INFO)
logger = logging.getLogger()


def item_hash(item):
    item = deepcopy(item)
    item.pop('_id', None)
    item.pop('_rev', None)
    item.pop('prepid', None)
    item.pop('history', None)
    return hashlib.md5(json.dumps(item, sort_keys=True).encode('utf-8')).hexdigest()


total = 0
for batches in database.bulk_yield(250):
    if not batches:
        break

    total += len(batches)
    logger.info('Fetched %s (%s) batches (%s -> %s)',
                len(batches),
                total,
                batches[0]['_id'],
                batches[-1]['_id'])

    to_save = []
    for batch in batches:
        initial_hash = item_hash(batch)

        batch.pop('message_id', None)
        batch.pop('extension', None)
        batch.pop('version', None)
        batch.pop('process_string', None)

        requests = batch.get('requests', [])
        requests = [(r if isinstance(r, list) else [r['content']['pdmv_prep_id'], r['name']]) for r in requests]
        batch['requests'] = requests

        last_hash = item_hash(batch)
        if last_hash != initial_hash:
            to_save.append(batch)

    if to_save:
        logger.info('Saving %s batches', len(to_save))
        saved = database.bulk_save(to_save)
        logger.info('Saved %s items', len([r for r in saved if r]))
    else:
        logger.info('Nothing to save!')
