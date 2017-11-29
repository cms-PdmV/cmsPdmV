from copy import deepcopy
from datetime import datetime
from simplejson import dumps

from json_base import json_base
from couchdb_layer.mcm_database import database


class notification(json_base):
    # Groups
    BATCHES = 'Batches'
    CHAINED_REQUESTS = 'Chained_requests'
    REQUEST_APPROVALS = 'Request_approvals'
    # Requests in (all request status)
    REQUEST_OPERATIONS = 'Request_operations'
    REMINDERS = "Reminders"
    USERS = "Users"

    _json_base__schema = {
        '_id': '',
        'message': '',
        'title': '',
        'targets': [],
        'target_role': '',
        'action_objects': [],
        'object_type': '',
        'created_at': '',
        'group': ''
    }

    def __init__(self, title, message, targets, target_role='', action_objects=[], object_type='', group='', base_object=None):
        if base_object is not None:
            targets.extend(base_object.get_actors())
        targets = list(set(targets))
        json_input = deepcopy(notification._json_base__schema)
        json_input.pop('_id')
        json_input['message'] = message
        json_input['title'] = title
        json_input['targets'] = targets
        json_input['target_role'] = target_role
        json_input['action_objects'] = action_objects
        json_input['object_type'] = object_type
        json_input['group'] = group
        json_input['seen_by'] = []
        json_input['created_at'] = str(datetime.now()).split('.')[0]
        notification_db = database('notifications')
        if not notification_db.save(json_input):
            self.logger.error('Failed to save notification: \n' + dumps(json_input))