import logging
import json
import hashlib
from copy import deepcopy
from tools.config_manager import Config
from couchdb_layer.mcm_database import Database


Config.load('../config.cfg', 'development')
database = Database('chained_campaigns')
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
for chained_campaigns in database.bulk_yield(50):
    if not chained_campaigns:
        break

    total += len(chained_campaigns)
    logger.info('Fetched %s (%s) chained campaigns (%s -> %s)',
                len(chained_campaigns),
                total,
                chained_campaigns[0]['_id'],
                chained_campaigns[-1]['_id'])

    to_save = []
    for chained_campaign in chained_campaigns:
        initial_hash = item_hash(chained_campaign)
        chained_campaign.pop('alias', None)
        chained_campaign.pop('valid', None)
        chained_campaign.pop('chain_type', None)
        if 'do_not_check_cmssw_versions' in chained_campaign:
            check = not chained_campaign.pop('do_not_check_cmssw_versions', False)
            chained_campaign['check_cmssw_version'] = check

        if 'action_parameters' in chained_campaign:
            chained_campaign['enabled'] = chained_campaign['action_parameters']['flag']
            chained_campaign['threshold'] = chained_campaign['action_parameters']['threshold']
            chained_campaign.pop('action_parameters', None)

        last_hash = item_hash(chained_campaign)
        if last_hash != initial_hash:
            to_save.append(chained_campaign)

    if to_save:
        logger.info('Saving %s chained campaigns', len(to_save))
        saved = database.bulk_save(to_save)
        logger.info('Saved %s items', len([r for r in saved if r]))
    else:
        logger.info('Nothing to save!')
