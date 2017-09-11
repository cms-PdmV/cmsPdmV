#!/usr/bin/env python

import cherrypy

from json import dumps

from RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from json_layer.notification import notification
from tools.user_management import user_pack, roles, access_rights
from tools.json import threaded_loads

class CheckNotifications(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self):
        """
        Check for new notifications
        """
        notifications_db = database('notifications')
        user_p = user_pack()
        username = user_p.get_username()
        role = self.authenticator.get_user_role(username, email=user_p.get_email())
        query = notifications_db.construct_lucene_query({
            'target_role' : role,
            'targets' : username,
        }, boolean_operator='OR')
        notifications = notifications_db.full_text_search('search', query, page=-1)
        users_db = database("users")
        seen_notifications = set(users_db.get(username)['seen_notifications'])
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

class FetchNotifications(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self, **kwargs):
        """
        Fetch notifications of a specific group
        """
        page = -1
        group = '*'
        if 'page' in kwargs:
            page = kwargs['page']
        if 'group' in kwargs:
            group = kwargs['group']
        user_p = user_pack()
        username = user_p.get_username()
        role = self.authenticator.get_user_role(username, email=user_p.get_email())
        notifications_db = database('notifications')
        query = notifications_db.construct_lucene_complex_query([
                ('target_role', {'value': role}),
                ('targets', {'value': username, 'join_operator': 'OR'}),
                ('group', {'value': group, 'join_operator': 'AND'})
        ])
        notifications = notifications_db.full_text_search('search', query, page=page, limit=10, sort="\_id")
        users_db = database("users")
        seen_notifications = set(users_db.get(username)['seen_notifications'])
        for notif in notifications:
            notif['seen'] = notif['_id'] in seen_notifications
        self.logger.info("Fetched notifications")
        return dumps({'notifications': notifications})

class SaveSeen(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def POST(self):
        """
        Save notification seen by the user
        """
        try:
             notification_id = threaded_loads(cherrypy.request.body.read().strip())['notification_id']
        except TypeError:
            return dumps({"results": False, "message": "Couldn't read body of request"})
        users_db = database('users')
        user_p = user_pack()
        username = user_p.get_username()
        user_json = users_db.get(username)
        user_json['seen_notifications'].append(notification_id)
        self.logger.info("Saved seen for notification %s" % notification_id)
        return dumps({"results": users_db.save(user_json)})

class FetchActionObjects(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self, **kwargs):
        """
        Get action objects from notification
        """
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
        mcm_notification = notification(notifications_db.get(notification_id))
        db = database(mcm_notification.get_attribute("object_type"))
        index = 0
        action_objects = mcm_notification.get_attribute("action_objects")
        action_objects_results = []
        while(index < len(action_objects) and len(action_objects_results) < limit):
            fetch = limit - len(action_objects_results)
            fetch = fetch if fetch < 20 else 20
            query = db.construct_lucene_query({'prepid': action_objects[index:fetch]}, boolean_operator="OR")
            action_objects_results += db.full_text_search('search', query, page=page, limit=limit)
            index += 20
        self.logger.info("Fetched action objects for notifications %s" % notification_id)
        return dumps(action_objects_results)
