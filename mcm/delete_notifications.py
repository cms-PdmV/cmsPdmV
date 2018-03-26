from datetime import datetime, timedelta
from couchdb_layer.mcm_database import database

if __name__ == "__main__":
    notifications_db = database('notifications')
    query = notifications_db.construct_lucene_query({'_id': '*'})
    page = 0
    today = datetime.now()
    one_month_ago = (today.replace(day=1) - timedelta(days=1)).replace(day=today.day)
    old_notifications_ids = []
    results = [{}]
    while len(results) > 0:
        results = notifications_db.full_text_search("search", query, page=page, limit=100)
        print('Page %d' % (page))
        for result in results:
            if result['_id'].startswith('_') or result['_id'] == 'notification_stats':
                continue

            if 'created_at' not in result:
                print('%s does not have created_at attribute!' % (result['_id']))
                continue

            created_at = datetime.strptime(result['created_at'], "%Y-%m-%d %H:%M:%S")
            if created_at < one_month_ago:
                old_notifications_ids.append(result['_id'])

        page += 1

    deleted_notifications = 0
    for notification_id in old_notifications_ids:
        if notifications_db.db.delete_doc(notification_id):
            print('Deleted %s' % (notification_id))
            deleted_notifications += 1
        else:
            print("Error while deleting notification %s" % notification_id)

    errors_deleting = len(old_notifications_ids) - deleted_notifications
    print("Deleted notifications: %d. Errors deleting: %d" % (deleted_notifications, errors_deleting))
