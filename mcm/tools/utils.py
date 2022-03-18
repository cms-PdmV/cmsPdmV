"""
Common utils
"""
import json
import time
import re
import os
import xml.etree.ElementTree as XMLet
from tools.locker import locker
from tools.connection_wrapper import ConnectionWrapper


# Scram arch cache to save some requests to cmssdt.cern.ch
__scram_arch_cache = {}
__scram_arch_cache_timeout = 3600
__scram_arch_cache_update = 0


def clean_split(string, separator=',', maxsplit=-1):
    """
    Split a string by separator and collect only non-empty values
    """
    return [x.strip() for x in string.split(separator, maxsplit) if x.strip()]


def cmssw_setup(cmssw_release, scram_arch=None):
    """
    Return code needed to set up CMSSW environment for given CMSSW release
    Basically, cmsrel and cmsenv commands
    If reuse is set to True, this will checkout CMSSW in parent directory
    If scram_arch is None, use default arch of CMSSW release
    Releases are put to <scram arch>/<release name> directory
    """
    if scram_arch is None:
        scram_arch = get_scram_arch(cmssw_release)

    if not scram_arch:
        raise Exception(f'Could not find SCRAM arch of {cmssw_release}')

    commands = [f'export SCRAM_ARCH={scram_arch}',
                'source /cvmfs/cms.cern.ch/cmsset_default.sh',
                'ORG_PWD=$(pwd)',
                f'mkdir -p {scram_arch}',
                f'cd {scram_arch}',
                f'if [ ! -r {cmssw_release}/src ] ; then scram p CMSSW {cmssw_release} ; fi',
                f'cd {cmssw_release}/src',
                'CMSSW_SRC=$(pwd)',
                'eval `scram runtime -sh`',
                'cd $ORG_PWD']

    return '\n'.join(commands)


def get_scram_arch(cmssw_release):
    """
    Get scram arch from
    https://cmssdt.cern.ch/SDT/cgi-bin/ReleasesXML?anytype=1
    Cache it global variable
    """
    if not cmssw_release:
        return None

    global __scram_arch_cache_update
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

    if isinstance(query, list):
        query = [ds[ds.index('/'):] for ds in query]
    else:
        query = query[query.index('/'):]

    with ConnectionWrapper('https://cmsweb-prod.cern.ch:8443') as dbs_conn:
        dbs_response = dbs_conn.api('POST',
                                    '/dbs/prod/global/DBSReader/datasetlist',
                                    {'dataset': query,
                                     'detail': 1,
                                     'dataset_access_type': '*'},
                                    headers={'Content-type': 'application/json'})

    dbs_response = json.loads(dbs_response.decode('utf-8'))
    if not dbs_response:
        return []

    return dbs_response


def expand_range(start, end):
    """
    Expand a given range to all ids
    E.g. start=AAA-00001 and end=AAA-00005 would return all the ids between
    00001 and 00005 -> AAA-00001, AAA-00002, AAA-00003, AAA-00004, AAA-00005
    """
    start = start.split('-')
    end = end.split('-')
    range_start = int(start[-1])
    range_end = int(end[-1])
    numbers = range(range_start, range_end + 1)
    start = '-'.join(start[:-1])
    end = '-'.join(end[:-1])
    if start != end:
        raise Exception('Invalid range "%s-..." != "%s-..."' % (start, end))

    if range_start > range_end:
        raise Exception('Invalid range ...-%05d > ...-%05d' % (range_start, range_end))

    return ['%s-%05d' % (start, n) for n in numbers]


def make_regex_matcher(pattern):
    """
    Compile a regex pattern and return a function that performs fullmatch on
    given value
    """
    compiled_pattern = re.compile(pattern)
    def matcher_function(self, value):
        """
        Return whether given value fully matches the pattern
        """
        return compiled_pattern.fullmatch(value) is not None

    return matcher_function


def strip_doc(doc):
    """
    LStrip docstring according to number of spaces in the first line
    """
    if not doc:
        return '<undocumented>'

    lines = doc.split('\n')
    while lines and not lines[0].strip():
        lines = lines[1:]

    if not lines:
        return ''

    spaces = len(lines[0]) - len(lines[0].lstrip())
    return '\n'.join(l[spaces:] for l in lines)


def get_api_documentation(app, api_path):
    """
    Return a dictionary with endpoints and their information for given app
    Works with flask api resources
    """
    docs = {}
    cwd = os.getcwd()
    for endpoint, view in app.view_functions.items():
        view_class = dict(view.__dict__).get('view_class')
        if view_class is None:
            continue

        #pylint: disable=protected-access
        urls = sorted([r.rule for r in app.url_map._rules_by_endpoint[endpoint]])
        #pylint: enable=protected-access
        if api_path:
            urls = [u for u in urls if u.startswith((f'/restapi/{api_path}',
                                                     f'/restapi/public/{api_path}'))]

        if not urls:
            continue

        urls = [u.replace('<string:', '<') for u in urls]
        url = urls[0].replace('/restapi', '').replace('/public', '').lstrip('/')
        category = clean_split(url, '/')[0].upper().replace('_', ' ')
        if category not in docs:
            docs[category] = {}

        class_name = view_class.__name__
        class_doc = strip_doc(view_class.__doc__)
        docs[category][class_name] = {'doc': class_doc, 'urls': urls, 'methods': {}}

        for method_name in view_class.methods:
            method = view_class.__dict__.get(method_name.lower())
            method_doc = strip_doc(method.__doc__)
            method_dict = {'doc': method_doc}
            docs[category][class_name]['methods'][method_name] = method_dict
            if hasattr(method, '__role__'):
                method_dict['role'] = str(getattr(method, '__role__')).upper().replace('_', ' ')

            # Try to get the actual method to get file and line
            while hasattr(method, '__func__'):
                method = method.__func__

    return docs


def run_commands_in_singularity(commands, os_name, mount_eos, mount_home):
    bash = ['# Dump code to singularity-script.sh file that can be run in Singularity',
            'cat <<\'EndOfTestFile\' > singularity-script.sh',
            '#!/bin/bash',
            '']
    bash += commands
    bash += ['',
             '# End of singularity-script.sh file',
             'EndOfTestFile',
             '',
             '# Make file executable',
             'chmod +x singularity-script.sh',
             ''
             'export SINGULARITY_CACHEDIR="/tmp/$(whoami)/singularity"',
             '']

    singularity = 'singularity run -B /afs -B /cvmfs -B /etc/grid-security'
    if mount_eos:
        singularity += ' -B /eos'

    if mount_home:
        singularity += ' --home $PWD:$PWD'
    else:
        singularity += ' --no-home'

    singularity += ' '
    if os_name == 'SLCern6':
        singularity += '/cvmfs/unpacked.cern.ch/registry.hub.docker.com/cmssw/slc6:amd64'
    else:
        raise Exception(f'Unrecognized OS {os_name}')

    singularity += ' $(pwd)/singularity-script.sh'
    bash += [singularity,
             'rm -f singularity-script.sh']

    return bash


def sort_workflows_by_name(workflows, name_attr):
    """
    Sort workflows by their submission date
    """
    return sorted(workflows, key=lambda w: '_'.join(w[name_attr].split('_')[-3:]))


def get_workflows_from_stats_for_prepid(prepid):
    """
    Fetch workflows from Stats for given prepid
    """
    if not prepid:
        return []

    with ConnectionWrapper('http://vocms074.cern.ch:5984') as stats_conn:
        response = stats_conn.api(
            'GET',
            f'/requests/_design/_designDoc/_view/requestsPrepids?key="{prepid}"&include_docs=True',
            headers={'Content-Type': 'application/json'}
        )

    response = json.loads(response.decode('utf-8'))
    workflows = [x['doc'] for x in response['rows']]
    workflows = sort_workflows_by_name(workflows, 'RequestName')
    return workflows


def get_workflows_from_stats(workflow_names):
    """
    Fetch workflows from Stats with given names
    """
    workflow_names = [w.strip() for w in workflow_names if w.strip()]
    if not workflow_names:
        return []

    data = {'docs': [{'id': name} for name in workflow_names]}
    with ConnectionWrapper('http://vocms074.cern.ch:5984') as stats_conn:
        response = stats_conn.api('POST',
                                  '/requests/_bulk_get',
                                  data=data,
                                  headers={'Content-Type': 'application/json'})

    response = json.loads(response.decode('utf-8')).get('results', [])
    workflows = [r['docs'][-1]['ok'] for r in response if r.get('docs') if r['docs'][-1].get('ok')]
    workflows = sort_workflows_by_name(workflows, 'RequestName')
    return workflows
