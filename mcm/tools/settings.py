"""
Module that contains Settings class
"""
from cachelib import SimpleCache
from couchdb_layer.mcm_database import database as Database
from tools.locker import locker


class Settings():
    """
    Settings class provices a convenient way of managing setting objects in the
    database
    Fetched values are cached for an hour
    """
    cache = SimpleCache(default_timeout=3600) # Cache timeout 1h

    @classmethod
    def get_setting(cls, key):
        """
        Get a setting object from cache or database
        """
        if cls.cache.has(key):
            return cls.cache.get(key)

        setting = cls.get_database().get(key)
        cls.cache.set(key, setting)
        return setting

    @classmethod
    def get(cls, key):
        """
        Get just the setting value
        """
        return cls.get_setting(key)['value']

    @classmethod
    def set_setting(cls, key, value, notes=None):
        """
        Set setting value and notes and save to database
        If notes are None, they will not be updated
        """
        with locker.lock('settings-%s' % (key)):
            setting = cls.get_database().get(key)
            if not setting:
                setting = {'_id': key}

            setting['value'] = value
            if notes is not None:
                setting['notes'] = notes

            if cls.get_database().save(setting):
                cls.cache.set(key, value)
                return True

            return False

    @classmethod
    def set(cls, key, value):
        """
        Set a setting value
        """
        return cls.set_setting(key, value)

    @classmethod
    def clear_cache(cls):
        """
        Clear settings cache
        """
        cls.cache.clear()

    @classmethod
    def get_database(cls):
        """
        Return shared database instance
        """
        if not hasattr(cls, 'database'):
            cls.database = Database('settings')

        return cls.database
