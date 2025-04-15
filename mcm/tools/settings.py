import sys
from couchdb_layer.mcm_database import database
from tools.locker import locker
from cachelib import SimpleCache

__cache = SimpleCache()
__db = database('settings')
# Cache timeout in seconds
CACHE_TIMEOUT = 30 * 60

def get(label):
    cached_value = __cache.get(label)
    if cached_value is not None:
        return cached_value

    with locker.lock(label):
        setting = __db.get(label)
        __cache.set(label, setting, timeout=CACHE_TIMEOUT)
        return setting

def get_value(label):
    return get(label)['value']

def get_notes(label):
    return get(label)['notes']

def add(label, setting):
    with locker.lock(label):
        result = __db.save(setting)
        if result:
            __cache.set(label, setting, timeout=CACHE_TIMEOUT)

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
            __cache.set(label, setting, timeout=CACHE_TIMEOUT)

        return result

def cache_size():
    return len(__cache._cache), sys.getsizeof(__cache._cache)

def clear_cache():
    size = cache_size()
    __cache.clear()
    return size

def get_htcondor_config_for_validation():
    """
    Get the HTCondor pool and the AccountingGroup
    for sending validation jobs.
    """
    # HTCondor pools - Get the complete list by running: `module avail`
    available_pools = ["lxbatch/share", "lxbatch/spool", "lxbatch/tzero"]
    htcondor_pool_config = {
        "Pool": "lxbatch/tzero", # By default, we submit to CMS CAF
        "AccountingGroup": "group_u_CMS.CAF.PHYS" # Using this AccountingGroup
    }

    try:
        htcondor_config_settings = dict(get_value("htcondor_config_settings"))
        requested_pool = str(htcondor_config_settings["Pool"])
        requested_accounting_group = str(htcondor_config_settings["AccountingGroup"])
        if requested_pool in available_pools:
            htcondor_pool_config["Pool"] = requested_pool
            htcondor_pool_config["AccountingGroup"] = requested_accounting_group

    except Exception:
        # The key does not exists in the database or it is malformed
        pass

    return htcondor_pool_config["Pool"], htcondor_pool_config["AccountingGroup"]
