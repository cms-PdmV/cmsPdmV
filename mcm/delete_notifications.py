import time
from datetime import datetime, timedelta
from couchdb_layer.mcm_database import database

if __name__ == "__main__":
    notifications_db = database('notifications')
    query = notifications_db.construct_lucene_query({'_id' : '*'})
    page = 0
    today = datetime.now()
    one_month_ago = (today.replace(day=1) - timedelta(days=1)).replace(day=today.day)
    results = []
    deleted_notifications = 0
    while len(results) >= 100 or page == 0:
        results = notifications_db.full_text_search("search", query, page=page, limit=100)
        for result in results:
            if result['_id'].startswith('_') or result['_id'] == 'notification_stats':
                continue
            if 'created_at' not in result:
                print "No creation date in %s" % result['_id']
            created_at = datetime.strptime(result['created_at'], "%Y-%m-%d %H:%M:%S")
            if created_at < one_month_ago:
                if notifications_db.db.delete_doc(result['_id']):
                    deleted_notifications += 1
                else:
                    print "Error while deleting notification %s" % result['_id']
        page += 1
    print "Deleted notifications: %s" % deleted_notifications