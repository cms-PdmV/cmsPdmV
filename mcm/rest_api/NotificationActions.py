#!/usr/bin/env python

import cherrypy

from json import dumps

from RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from json_layer.notification import notification
from tools.user_management import user_pack, roles, access_rights
from tools.json import threaded_loads

class NotificationRESTResource(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        user_p = user_pack()
        self.username = user_p.get_username()
        self.role = self.authenticator.get_user_role(self.username, email=user_p.get_email())

    def fetch_action_objects(self, action_objects, object_type, page, limit):
        db = database(object_type)
        index = page * limit
        action_objects_results = []
        while(index < len(action_objects) and len(action_objects_results) < limit):
            fetch = limit - len(action_objects_results)
            fetch = fetch if fetch < 20 else 20
            query = db.construct_lucene_query({'prepid': action_objects[index:fetch]}, boolean_operator="OR")
            action_objects_results += db.full_text_search('search', query)
            index += 20
        return action_objects_results

    def set_seen(self, notifications):
        users_db = database("users")
        user_json = users_db.get(self.username)
        seen_notifications = set(user_json['seen_notifications'] if 'seen_notifications' in user_json else [])
        for notif in notifications:
            notif['seen'] = notif['_id'] in seen_notifications


class CheckNotifications(NotificationRESTResource):
    def __init__(self):
        NotificationRESTResource.__init__(self)

    def GET(self):
        """
        Check for new notifications
        """
        CheckNotifications.__init__(self)
        notifications_db = database('notifications')
        query = notifications_db.construct_lucene_query({
            'target_role' : self.role,
            'targets' : self.username,
        }, boolean_operator='OR')
        notifications = notifications_db.full_text_search('search', query, page=-1)
        users_db = database("users")
        json_user = users_db.get(self.username)
        if 'seen_notifications' not in json_user:
            return dumps({'All': 0, 'unseen': 0})
        seen_notifications = set(json_user['seen_notifications'])
        frequency = {}
        unseen_counter = 0
        for notif in notifications:
            if notif['group'] in frequency:
                frequency[notif['group']] += 1
            else:
                frequency[notif['group']] = 1
            if notif['_id'] not in seen_notifications:
                unseen_counter += 1
        frequency['All'] = len(notifications)
        frequency['unseen'] = unseen_counter
        return dumps(frequency)

class FetchNotifications(NotificationRESTResource):
    def __init__(self):
        NotificationRESTResource.__init__(self)

    def GET(self, **kwargs):
        """
        Fetch notifications of a specific group
        """
        FetchNotifications.__init__(self)
        page = -1
        group = '*'
        if 'page' in kwargs:
            page = kwargs['page']
        if 'group' in kwargs:
            group = kwargs['group']
        notifications_db = database('notifications')
        query = notifications_db.construct_lucene_complex_query([
                ('target_role', {'value': self.role}),
                ('targets', {'value': self.username, 'join_operator': 'OR'}),
                ('group', {'value': group, 'join_operator': 'AND'})
        ])
        notifications = notifications_db.full_text_search('search', query, page=page, limit=10, sort="\_id")
        self.set_seen(notifications)
        self.logger.info("Fetched notifications")
        return dumps({'notifications': notifications})

class SaveSeen(NotificationRESTResource):
    def __init__(self):
        NotificationRESTResource.__init__(self)

    def POST(self):
        """
        Save notification seen by the user
        """
        SaveSeen.__init__(self)
        try:
             notification_id = threaded_loads(cherrypy.request.body.read().strip())['notification_id']
        except TypeError:
            return dumps({"results": False, "message": "Couldn't read body of request"})
        users_db = database('users')
        user_json = users_db.get(self.username)
        if 'seen_notifications' not in user_json:
            return dumps({"results": False, "message": "Seen notifications not in user document"})
        user_json['seen_notifications'].append(notification_id)
        self.logger.info("Saved seen for notification %s" % notification_id)
        return dumps({"results": users_db.save(user_json)})

class FetchGroupActionObjects(NotificationRESTResource):
    def __init__(self):
        NotificationRESTResource.__init__(self)

    def GET(self, **kwargs):
        """
        Get group action objects from notification
        """
        FetchGroupActionObjects.__init__(self)
        if 'group' not in kwargs:
            return dumps({})
        group = kwargs['group']
        page = 0
        limit = 20
        if 'page' in kwargs:
            page = int(kwargs['page'])
        if 'limit' in kwargs:
            limit = int(kwargs['limit'])
        notifications_db = database('notifications')
        query = notifications_db.construct_lucene_complex_query([
                ('target_role', {'value': self.role}),
                ('targets', {'value': self.username, 'join_operator': 'OR'}),
                ('group', {'value': group, 'join_operator': 'AND'})
        ])
        notifications = notifications_db.full_text_search('search', query)
        action_objects = []
        object_type = ''
        for notif in notifications:
            action_objects += notif['action_objects']
            if object_type == '' and notif['object_type'] != '':
                object_type = notif['object_type']
        if object_type == '' or len(action_objects) < 1:
            return dumps({})
        action_objects_results = self.fetch_action_objects(action_objects, object_type, page, limit)
        self.logger.info("Fetched group action objects for group %s" % group)
        return dumps(action_objects_results)

class SearchNotifications(NotificationRESTResource):
    def __init__(self):
        NotificationRESTResource.__init__(self)

    def GET(self, **kwargs):
        """
        Search text in title and message fields
        """
        SearchNotifications.__init__(self)
        if 'search' not in kwargs:
            return dumps({})
        search = '*' + kwargs['search'] + '*'
        page = 0
        limit = 10
        if 'page' in kwargs:
            page = int(kwargs['page'])
        if 'limit' in kwargs:
            limit = int(kwargs['limit'])
        notifications_db = database('notifications')
        query = notifications_db.construct_lucene_complex_query([
                ('target_role', {'value': self.role}),
                ('targets', {'value': self.username, 'join_operator': 'OR'}),
                ('action_objects', {'value': search, 'join_operator': 'AND', 'open_parenthesis': True}),
                ('title', {'value': search, 'join_operator': 'OR', 'close_parenthesis': True})
        ])
        notifications = notifications_db.full_text_search('search', query, page=page, limit=10, sort="\_id")
        self.set_seen(notifications)
        self.logger.info("Searched text %s in notifications" % search)
        return dumps(notifications)

class FetchActionObjects(NotificationRESTResource):
    def __init__(self):
        NotificationRESTResource.__init__(self)

    def GET(self, **kwargs):
        """
        Get action objects from notification
        """
        FetchActionObjects.__init__(self)
        if 'notification_id' not in kwargs:
            return dumps({})
        notification_id = kwargs['notification_id']
        page = 0
        limit = 20
        if 'page' in kwargs:
            page = int(kwargs['page'])
        if 'limit' in kwargs:
            limit = int(kwargs['limit'])
        notifications_db = database('notifications')
        mcm_notification = notifications_db.get(notification_id)
        action_objects_results = self.fetch_action_objects(mcm_notification["action_objects"], mcm_notification["object_type"], page, limit)
        self.logger.info("Fetched action objects for notification %s" % notification_id)
        return dumps(action_objects_results)
