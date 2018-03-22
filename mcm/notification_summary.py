import sys
import time
from couchdb_layer.mcm_database import database
from tools.user_management import roles


def update_group(stats_dict, user, group):
    if user not in stats_dict:
        stats_dict[user] = {}
    if group not in stats_dict[user]:
        stats_dict[user][group] = 1
    else:
        stats_dict[user][group] += 1


def update_stats(stats_dict, user, group, seen_by):
    update_group(stats_dict, user, group)
    if user not in seen_by:
        update_group(stats_dict, user, 'unseen')


def set_all_counter(stats_dict):
    for stats in stats_dict.itervalues():
        all_counter = 0
        for group, counter in stats.iteritems():
            if group != "unseen":
                all_counter += counter
        stats['All'] = all_counter


if __name__ == "__main__":
    notifications_db = database('notifications')
    users_db = database('users')
    stats_dict = {}
    roles_users = {}
    for role in roles:
        query = users_db.construct_lucene_query({'role': role})
        results = users_db.full_text_search("search", query, page=-1)
        roles_users[role] = map(lambda u: u['username'], results)
    query = notifications_db.construct_lucene_query({'_id': '*'})
    page = 0
    results = [{}]
    while len(results) > 0:
        results = notifications_db.full_text_search("search", query, page=page, limit=100)
        for result in results:
            if result['_id'].startswith('_') or result['_id'] == 'notification_stats':
                continue
            seen_by = set(result['seen_by'])
            for username in result['targets']:
                update_stats(stats_dict, username, result['group'], seen_by)
            if result['target_role'] != "" and result['target_role'] in roles_users:
                targets = set(result['targets'])
                for user in roles_users[result['target_role']]:
                    if user not in targets:
                        update_stats(stats_dict, user, result['group'], seen_by)
        page += 1
        print "Page: %s" % page
    tries = 0
    while tries < 3:
        stats_doc = notifications_db.get('notification_stats')
        set_all_counter(stats_dict)
        stats_doc['stats'] = stats_dict
        if notifications_db.save(stats_doc):
            print "Notification stats updated"
            sys.exit()
        print "Failed to save notification stats doc, try: %s" % tries
        tries += 1
        time.sleep(2)
    sys.exit(-1)
