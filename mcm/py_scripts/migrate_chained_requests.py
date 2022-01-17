import logging
import json
import hashlib
from copy import deepcopy
from tools.config_manager import Config
from couchdb_layer.mcm_database import database as Database


Config.load('../config.cfg', 'development')
database = Database('chained_requests')
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
for chained_requests in database.bulk_yield(1000):
    if not chained_requests:
        break

    total += len(chained_requests)
    logger.info('Fetched %s (%s) chained requests (%s -> %s)',
                len(chained_requests),
                total,
                chained_requests[0]['_id'],
                chained_requests[-1]['_id'])
    
    to_save = []
    for chained_request in chained_requests:
        initial_hash = item_hash(chained_request)
        chained_request.pop('analysis_id', None)
        chained_request.pop('chain_type', None)

        if 'action_parameters' in chained_request:
            chained_request['enabled'] = chained_request['action_parameters']['flag']
            chained_request['threshold'] = chained_request['action_parameters']['threshold']
            chained_request.pop('action_parameters', None)

        last_hash = item_hash(chained_request)
        if last_hash != initial_hash:
            to_save.append(chained_request)

    if to_save:
        logger.info('Saving %s chained requests', len(to_save))
        saved = database.bulk_save(to_save)
        logger.info('Saved %s items', len([r for r in saved if r]))
    else:
        logger.info('Nothing to save!')
