import logging
import json
import hashlib
from copy import deepcopy
from tools.config_manager import Config
from couchdb_layer.mcm_database import Database


Config.load('../config.cfg', 'development')
database = Database('flows')
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
for flows in database.bulk_yield(50):
    if not flows:
        break

    total += len(flows)
    logger.info('Fetched %s (%s) flows (%s -> %s)',
                len(flows),
                total,
                flows[0]['_id'],
                flows[-1]['_id'])

    to_save = []
    for flow in flows:
        initial_hash = item_hash(flow)
        parameters = flow.get('request_parameters', {})
        sequences = parameters.get('sequences', [])
        if isinstance(sequences, list) and parameters.get('sequences_name') is None:
            new_sequences = {}
            keys = set()
            for sequence in sequences:
                for key, value in sequence.items():
                    keys.add(key)
                    new_sequences.setdefault(key, []).append(value)

            if len(keys) > 1:
                raise Exception(flow['prepid'])

            if keys:
                flow['request_parameters']['sequences_name'] = list(keys)[0]
                flow['request_parameters']['sequences'] = new_sequences[list(keys)[0]]
            else:
                logger.warning('Removing sequences from %s', flow.get('_id'))
                flow['request_parameters'].pop('sequences', None)

        last_hash = item_hash(flow)
        if last_hash != initial_hash:
            to_save.append(flow)

    if to_save:
        logger.info('Saving %s flows', len(to_save))
        saved = database.bulk_save(to_save)
        logger.info('Saved %s items', len([r for r in saved if r]))
    else:
        logger.info('Nothing to save!')
