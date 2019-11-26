import sys
import time
sys.path.append('/afs/cern.ch/cms/PPD/PdmV/tools/McM/')
from rest import McM

mcm = McM(dev=True, debug=True)

requests = mcm.get('requests', query='priority=110000&prepid=*MiniAOD*&status=submitted')

print('Found %s requests' % (len(requests)))

for request in requests:
    submission_date = None
    for history_entry in reversed(request['history']):
        if history_entry.get('action') == 'set status' and history_entry.get('step') == 'submitted':
            submission_date = history_entry['updater']['submission_date']

    if not submission_date:
        continue

    # Convert McM date to unix timestamp
    submission_date = int(time.mktime(time.strptime(submission_date, '%Y-%m-%d-%H-%M')))
    # 21 days
    three_weeks_ago = time.time() - 21 * 24 * 3600
    if submission_date < three_weeks_ago:
        prepid = request['prepid']
        priority = request['priority']
        priority += 1
        result = mcm._McM__post('restapi/requests/priority_change', [{'prepid': prepid, 'priority': priority}])
        print(result)
