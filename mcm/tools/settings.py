from couchdb_layer.mcm_database import database
from tools.locker import locker

from werkzeug.contrib.cache import SimpleCache

# Cache timeout in seconds
__CACHE_TIMEOUT = 60 * 60

__cache = SimpleCache()
__db = database('settings')

def get(label):
    with locker.lock(label):
        cache_key = 'settings_' + label
        cached_value = __cache.get(cache_key)
        if cached_value != None:
            return cached_value
        setting = __db.get(label)
        __cache.set(cache_key, setting, timeout = __CACHE_TIMEOUT)
        return setting

def get_value(label):
    return get(label)['value']

def get_notes(label):
    return get(label)['notes']

def add(label, setting):
    with locker.lock(label):
        result = __db.save(setting)
        if result:
            cache_key = 'settings_' + label
            __cache.set(cache_key, setting, timeout = __CACHE_TIMEOUT)
        return result

def set_value(label, value):
    with locker.lock(label):
        setting = get(label)
        setting['value'] = value
        return set(label, setting)

def set(label, setting):
    with locker.lock(label):
        result = __db.update(setting)
        if result:
            # Maybe it's a better idea to cache the setting immediately instead
            # getting it from database?
            new_value = __db.get(label)
            cache_key = 'settings_' + label
            __cache.set(cache_key, new_value, timeout = __CACHE_TIMEOUT)
        return result
