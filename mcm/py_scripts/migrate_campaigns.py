import logging
import json
import hashlib
from copy import deepcopy
from tools.config_manager import Config
from couchdb_layer.mcm_database import database as Database


Config.load('../config.cfg', 'development')
database = Database('campaigns')
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
for campaigns in database.bulk_yield(50):
    if not campaigns:
        break

    total += len(campaigns)
    logger.info('Fetched %s (%s) campaigns (%s -> %s)',
                len(campaigns),
                total,
                campaigns[0]['_id'],
                campaigns[-1]['_id'])
    
    to_save = []
    for campaign in campaigns:
        initial_hash = item_hash(campaign)
        old_sequences = campaign.get('sequences')
        if isinstance(old_sequences, list):
            new_sequences = {}
            for sequence_batch in old_sequences:
                for sequence_name, sequence in sequence_batch.items():
                    new_sequences.setdefault(sequence_name, []).append(sequence)

            campaign['sequences'] = new_sequences

        no_output = campaign.get('no_output')
        if no_output is not None:
            keep_output = {}
            for sequence_name, sequences in campaign['sequences'].items():
                keep_output[sequence_name] = [False] * len(sequences)

                if keep_output[sequence_name]:
                    keep_output[sequence_name][-1] = not no_output

            campaign.pop('no_output', None)
            campaign['keep_output'] = keep_output

        last_hash = item_hash(campaign)
        if last_hash != initial_hash:
            to_save.append(campaign)

    if to_save:
        logger.info('Saving %s campaigns', len(to_save))
        saved = database.bulk_save(to_save)
        logger.info('Saved %s items', len([r for r in saved if r]))
    else:
        logger.info('Nothing to save!')
