"""
Module that contains Settings class
"""
from cachelib import SimpleCache
from couchdb_layer.mcm_database import database as Database
from tools.locker import locker


def Settings():
    """
    Settings class provices a convenient way of managing setting objects in the
    database
    Fetched values are cached for an hour
    """
    __cache = SimpleCache(default_timeout=3600) # Cache timeout 1h
    __database = Database('settings')

    @classmethod
    def get_setting(cls, key):
        """
        Get a setting object from cache or database
        """
        if cls.__cache.has(key):
            return cls.__cache.get(key)

        setting = cls.__database.get(key)
        cls.__cache.set(key, setting)
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
            setting = cls.__database.get(key)
            if not setting:
                setting = {'_id': key}

            setting['value'] = value
            if notes is not None:
                setting['notes'] = notes

            if cls.__database.save(setting):
                cls.__cache.set(key, value)
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
        cls.__cache.clear()
