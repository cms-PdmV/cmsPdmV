import sys
import os
import time
import json
import httplib
from urllib2 import Request, urlopen
sys.path.append('/afs/cern.ch/cms/PPD/PdmV/tools/McM/')
from rest import McM


mcm = McM(dev=False, debug=False)

requests = mcm.get('requests', query='prepid=*MiniAOD*&status=submitted')

print('Found %s MiniAOD requests that are submitted' % (len(requests)))
requests = [r for r in requests if 'Dead' not in r.get('tags', [])]
print('Found %s MiniAOD requests that are submitted and not Dead' % (len(requests)))


def cmsweb_get(url):
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}
    cert = os.getenv('USERCRT')
    key = os.getenv('USERKEY')
    # print('Using certificate and key from %s' % cert)
    if cert is None:
        print('No user certificate found!')
        return {}

    conn = httplib.HTTPSConnection('cmsweb.cern.ch', cert_file=cert, key_file=key)
    conn.request("GET", url, headers=headers)
    response = conn.getresponse()
    status, data = response.status, response.read()
    conn.close()
    # print('HTTP status: %s' % (status))
    try:
        return json.loads(data)
    except:
        print('Error parsing JSON from:\n\n%s' % (data))
        return None


def make_simple_request(url):
    req = Request(url)
    try:
        return json.loads(urlopen(req).read().decode('utf-8'))
    except Exception as ex:
        print('Error while making a request to %s' % (url))
        print(ex)
        return None


for i, request in enumerate(requests):
    prepid = request['prepid']
    stats_url = 'http://vocms074:5984/requests/_design/_designDoc/_view/requests?key="%s"&limit=100&skip=0&include_docs=False' % (prepid)
    stats_workflows = make_simple_request(stats_url)
    stats_workflows = [x['value'] for x in stats_workflows.get('rows', [])]
    mcm_workflows = [x['name'] for x in request.get('reqmgr_name', [])]
    workflows = list(set(stats_workflows).union(set(mcm_workflows)))
    workflows = sorted(workflows, key=lambda x: ' '.join(x.split('_')[-3:]))
    # print('%s has %s workflows:\n    %s' % (prepid, len(workflows), ',\n    '.join(workflows)))
    if not workflows:
        print('%s has no workflows, skipping...' % (prepid))
        continue

    last_workflow = workflows[-1]
    reqmgr_workflow = cmsweb_get('/couchdb/reqmgr_workload_cache/%s' % (last_workflow))
    last_priority = reqmgr_workflow.get('PriorityTransition')[-1]
    priority = last_priority['Priority']
    priority_change_time = last_priority['UpdateTime']
    print('%s (%s/%s) has %s workflows' % (prepid, i + 1, len(requests), len(workflows)))
    print('Newest workflow: %s, priority %s' % (last_workflow, priority))
    if not priority or priority > 125000:
        print('Skipping, priority is %s' % (priority))
        continue

    now = time.time()
    # One week ago
    time_threshold = now - (7 * 24 * 3600)
    last_change_hours = int((now - priority_change_time) / 3600)
    if priority_change_time < time_threshold:
        # Priority increase by number of weeks
        priority += int(last_change_hours / 168)
        print('Change to %s, last update was %s hours ago' % (priority, last_change_hours))
        result = mcm._McM__post('restapi/requests/priority_change', [{'prepid': prepid, 'priority_raw': priority}])
        print(result)
    else:
        print('No need to change, last update was %s hours ago' % (last_change_hours))
