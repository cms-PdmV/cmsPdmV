import os
import tempfile
import time
from pathlib import Path

# Make sure the McM package is installed:
# https://github.com/cms-PdmV/mcm_scripts?tab=readme-ov-file#build-package
from rest import McM

stats_database_url = os.getenv("MCM_STATS2_DB_URL")
if not stats_database_url:
    raise RuntimeError("Set the Stats2 database URL via: $MCM_STATS2_DB_URL")

cookie_file = Path(tempfile.TemporaryDirectory().name) / Path("cookie.txt")
mcm = McM(dev=False, debug=False, cookie=cookie_file)

requests = mcm.get('requests', query='prepid=*MiniAOD*&status=submitted')

print(('Found %s MiniAOD requests that are submitted' % (len(requests))))
requests = [r for r in requests if 'Dead' not in r.get('tags', [])]
print(('Found %s MiniAOD requests that are submitted and not Dead' % (len(requests))))


def cmsweb_get(url):
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}
    cert = os.getenv('USERCRT')
    key = os.getenv('USERKEY')
    if cert is None:
        print('No user certificate found!')
        return {}

    full_url = "https://cmsweb.cern.ch" + url
    try:
        response = mcm.session.get(url=full_url, cert=(cert, key), headers=headers)
        return response.json()
    except Exception as ex:
        print('Error while making a request to %s' % (full_url))
        print(ex)
        return None

def make_simple_request(url):
    req = mcm.session.get(url=url)
    try:
        return req.json()
    except Exception as ex:
        print('Error while making a request to %s' % (url))
        print('Status code: %s' % (req.status_code))
        print('Output: %s' % (req.text))
        print(ex)
        return None


for i, request in enumerate(requests):
    prepid = request['prepid']
    stats_url = '%s/requests/_design/_designDoc/_view/requests?key="%s"&limit=100&skip=0&include_docs=False' % (stats_database_url, prepid)
    stats_workflows = make_simple_request(stats_url)
    stats_workflows = [x['value'] for x in stats_workflows.get('rows', [])]
    mcm_workflows = [x['name'] for x in request.get('reqmgr_name', [])]
    workflows = list(set(stats_workflows).union(set(mcm_workflows)))
    workflows = sorted(workflows, key=lambda x: ' '.join(x.split('_')[-3:]))
    # print('%s has %s workflows:\n    %s' % (prepid, len(workflows), ',\n    '.join(workflows)))
    if not workflows:
        print(('%s has no workflows, skipping...' % (prepid)))
        continue

    last_workflow = workflows[-1]
    reqmgr_workflow = cmsweb_get('/couchdb/reqmgr_workload_cache/%s' % (last_workflow))
    last_priority = reqmgr_workflow.get('PriorityTransition')[-1]
    priority = last_priority['Priority']
    priority_change_time = last_priority['UpdateTime']
    print(('%s (%s/%s) has %s workflows' % (prepid, i + 1, len(requests), len(workflows))))
    print(('Newest workflow: %s, priority %s' % (last_workflow, priority)))
    if not priority or priority > 125000:
        print(('Skipping, priority is %s' % (priority)))
        continue

    now = time.time()
    # One week ago
    time_threshold = now - (7 * 24 * 3600)
    last_change_hours = int((now - priority_change_time) / 3600)
    if priority_change_time < time_threshold:
        # Priority increase by number of weeks
        priority += int(last_change_hours / 168)
        print(('Change to %s, last update was %s hours ago' % (priority, last_change_hours)))
        result = mcm._post('restapi/requests/priority_change', [{'prepid': prepid, 'priority_raw': priority}])
        print(result)
    else:
        print(('No need to change, last update was %s hours ago' % (last_change_hours)))
