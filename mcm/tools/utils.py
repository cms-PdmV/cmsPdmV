"""
Common utils
"""
import json
import time
import xml.etree.ElementTree as XMLet
from locker import locker
from connection_wrapper import ConnectionWrapper


# Scram arch cache to save some requests to cmssdt.cern.ch
__scram_arch_cache = {}
__scram_arch_cache_timeout = 3600
__scram_arch_cache_update = 0


def clean_split(string, separator=',', maxsplit=-1):
    """
    Split a string by separator and collect only non-empty values
    """
    return [x.strip() for x in string.split(separator, maxsplit) if x.strip()]


def get_scram_arch(cmssw_release):
    """
    Get scram arch from
    https://cmssdt.cern.ch/SDT/cgi-bin/ReleasesXML?anytype=1
    Cache it global variable
    """
    if not cmssw_release:
        return None

    if __scram_arch_cache_update + __scram_arch_cache_timeout <= time.time():
        # Cache not timed out yet
        cached_value = __scram_arch_cache.get(cmssw_release)
        if cached_value:
            return cached_value

    with locker.lock('get-scram-arch'):
        # Maybe cache got updated while waiting for a lock
        cached_value = __scram_arch_cache.get(cmssw_release)
        if cached_value:
            return cached_value

        connection = ConnectionWrapper(host='https://cmssdt.cern.ch')
        response = connection.api('GET', '/SDT/cgi-bin/ReleasesXML?anytype=1')
        root = XMLet.fromstring(response)
        for architecture in root:
            if architecture.tag != 'architecture':
                # This should never happen as children should be <architecture>
                continue

            scram_arch = architecture.attrib.get('name')
            for release in architecture:
                __scram_arch_cache[release.attrib.get('label')] = scram_arch

        global __scram_arch_cache_update
        __scram_arch_cache_update = time.time()

    return __scram_arch_cache.get(cmssw_release)


def dbs_datasetlist(query):
    """
    Query DBS datasetlist endpoint with a query of list of datasets
    List of datasets do not support wildcards
    String query supports wildcards
    """
    if not query:
        return []

    dbs_conn = ConnectionWrapper(host='cmsweb-prod.cern.ch', port=8443)

    if isinstance(query, list):
        query = [ds[ds.index('/'):] for ds in query]
    else:
        query = query[query.index('/'):]

    dbs_response = dbs_conn.api('POST',
                                '/dbs/prod/global/DBSReader/datasetlist',
                                {'dataset': query,
                                 'detail': 1})
    dbs_response = json.loads(dbs_response.decode('utf-8'))
    if not dbs_response:
        return []

    return dbs_response
