#!/usr/bin/env python
from RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from tools.user_management import user_pack, access_rights, authenticator
from flask_restful import reqparse


class NotificationRESTResource(RESTResource):

    access_limit = access_rights.user

    def __init__(self):
        user_p = user_pack()
        self.username = user_p.get_username()
        self.role = authenticator.get_user_role(self.username, email=user_p.get_email())
        self.before_request()
        self.count_call()
        self.notifications_db = database('notifications')

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
        for notif in notifications:
            notif['seen'] = self.username in notif['seen_by']

    def substract_seens_in_stats(self, seens):
        if seens <= 0:
            return {"results": True}
        stats = self.notifications_db.get('notification_stats')
        stats['stats'][self.username]['unseen'] -= seens
        if not self.notifications_db.save(stats):
            message = "Failed to save notification stats"
            self.logger.error(message)
            return {"results": False, "message": message}
        return {"results": True}


class CheckNotifications(NotificationRESTResource):

    def __init__(self):
        NotificationRESTResource.__init__(self)

    def get(self):
        """
        Check for new notifications
        """
        CheckNotifications.__init__(self)
        stats = self.notifications_db.get('notification_stats')['stats']
        if self.username in stats:
            return stats[self.username]
        return {'All': 0, 'unseen': 0}


class FetchNotifications(NotificationRESTResource):

    def __init__(self):
        NotificationRESTResource.__init__(self)
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('page', type=int, default=0)
        self.parser.add_argument('group', type=str, default='*')

    def get(self):
        """
        Fetch notifications of a specific group
        """
        FetchNotifications.__init__(self)
        kwargs = self.parser.parse_args()
        query = self.notifications_db.construct_lucene_complex_query([
            ('target_role', {'value': self.role}),
            ('targets', {'value': self.username, 'join_operator': 'OR'}),
            ('group', {'value': kwargs['group'], 'join_operator': 'AND'})])
        notifications = self.notifications_db.full_text_search('search', query, page=kwargs['page'], limit=10, sort="\_id")
        self.set_seen(notifications)
        self.logger.info("Fetched notifications")
        return {'notifications': notifications}


class SaveSeen(NotificationRESTResource):

    def __init__(self):
        NotificationRESTResource.__init__(self)
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('notification_id', type=str, required=True)

    def post(self):
        """
        Save notification seen by the user
        """
        SaveSeen.__init__(self)
        kwargs = self.parser.parse_args()
        notif = self.notifications_db.get(kwargs['notification_id'])
        notif['seen_by'].append(self.username)
        if not self.notifications_db.save(notif):
            message = "Failed to save seen for notification: %s" % kwargs['notification_id']
            self.logger.error(message)
            return {"results": False, "message": message}
        return self.substract_seens_in_stats(1)


class FetchGroupActionObjects(NotificationRESTResource):

    def __init__(self):
        NotificationRESTResource.__init__(self)
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('group', type=str, required=True)
        self.parser.add_argument('page', type=int, default=0)
        self.parser.add_argument('limit', type=int, default=20)

    def get(self):
        """
        Get group action objects from notification
        """
        FetchGroupActionObjects.__init__(self)
        kwargs = self.parser.parse_args()
        query = self.notifications_db.construct_lucene_complex_query([
            ('target_role', {'value': self.role}),
            ('targets', {'value': self.username, 'join_operator': 'OR'}),
            ('group', {'value': kwargs['group'], 'join_operator': 'AND'})])
        notifications = self.notifications_db.full_text_search('search', query)
        action_objects = []
        object_type = ''
        for notif in notifications:
            action_objects += notif['action_objects']
            if object_type == '' and notif['object_type'] != '':
                object_type = notif['object_type']
        if object_type == '' or len(action_objects) < 1:
            return {}
        action_objects_results = self.fetch_action_objects(action_objects, object_type, kwargs['page'], kwargs['limit'])
        self.logger.info("Fetched group action objects for group %s" % kwargs['group'])
        return action_objects_results


class SearchNotifications(NotificationRESTResource):

    def __init__(self):
        NotificationRESTResource.__init__(self)
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('search', type=str, required=True)
        self.parser.add_argument('page', type=int, default=0)

    def get(self):
        """
        Search text in title and message fields
        """
        SearchNotifications.__init__(self)
        kwargs = self.parser.parse_args()
        search = '*' + kwargs['search'] + '*'
        query = self.notifications_db.construct_lucene_complex_query([
            ('target_role', {'value': self.role}),
            ('targets', {'value': self.username, 'join_operator': 'OR'}),
            ('action_objects', {'value': search, 'join_operator': 'AND', 'open_parenthesis': True}),
            ('title', {'value': search, 'join_operator': 'OR', 'close_parenthesis': True})])
        notifications = self.notifications_db.full_text_search('search', query, page=kwargs['page'], limit=10, sort="\_id")
        self.set_seen(notifications)
        self.logger.info("Searched text %s in notifications" % search)
        return notifications


class FetchActionObjects(NotificationRESTResource):

    def __init__(self):
        NotificationRESTResource.__init__(self)
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('notification_id', type=str, required=True)
        self.parser.add_argument('page', type=int, default=0)
        self.parser.add_argument('limit', type=int, default=20)

    def get(self):
        """
        Get action objects from notification
        """
        FetchActionObjects.__init__(self)
        kwargs = self.parser.parse_args()
        notification_id = kwargs['notification_id']
        mcm_notification = self.notifications_db.get(notification_id)
        action_objects_results = self.fetch_action_objects(mcm_notification["action_objects"], mcm_notification["object_type"], kwargs['page'], kwargs['limit'])
        self.logger.info("Fetched action objects for notification %s" % notification_id)
        return action_objects_results


class MarkAsSeen(NotificationRESTResource):

    def __init__(self):
        NotificationRESTResource.__init__(self)
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('group', type=str, required=True)

    def post(self):
        """
        Fetch notifications of a specific group
        """
        MarkAsSeen.__init__(self)
        kwargs = self.parser.parse_args()
        query = self.notifications_db.construct_lucene_complex_query([
            ('target_role', {'value': self.role}),
            ('targets', {'value': self.username, 'join_operator': 'OR'}),
            ('group', {'value': kwargs['group'], 'join_operator': 'AND'})])
        page = 0
        limit = 50
        set_seen_counter = 0
        while page == 0 or len(notifications) >= limit:
            notifications = self.notifications_db.full_text_search('search', query, page=page, limit=limit)
            for notif in notifications:
                seen_by = set(notif["seen_by"])
                if self.username in seen_by:
                    continue
                set_seen_counter += 1
                seen_by.add(self.username)
                notif["seen_by"] = list(seen_by)
                if not self.notifications_db.save(notif):
                    message = "Error saving seen for notification: %s" % notif["_id"]
                    self.logger.error(message)
                    self.substract_seens_in_stats(set_seen_counter)
                    return {'results': False, 'message': "Error saving seen for notification: %s" % notif["_id"]}
            page += 1
        return self.substract_seens_in_stats(set_seen_counter)
