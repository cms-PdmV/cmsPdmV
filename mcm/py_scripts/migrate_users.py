import logging
import json
import hashlib
from copy import deepcopy
from tools.config_manager import Config
from couchdb_layer.mcm_database import database as Database


Config.load('../config.cfg', 'development')
database = Database('users')
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
for users in database.bulk_yield(250):
    if not users:
        break

    total += len(users)
    logger.info('Fetched %s (%s) users (%s -> %s)',
                len(users),
                total,
                users[0]['_id'],
                users[-1]['_id'])

    to_save = []
    for user in users:
        initial_hash = item_hash(user)

        user.pop('seen_notifications', None)
        if user['role'] == 'generator_contact':
            user['role'] = 'mc_contact'

        last_hash = item_hash(user)
        if last_hash != initial_hash:
            to_save.append(user)

    if to_save:
        logger.info('Saving %s users', len(to_save))
        saved = database.bulk_save(to_save)
        logger.info('Saved %s items', len([r for r in saved if r]))
    else:
        logger.info('Nothing to save!')
