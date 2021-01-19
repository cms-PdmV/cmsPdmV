import sys
import json
import time
import os
from urllib2 import Request, urlopen
sys.path.append('/afs/cern.ch/cms/PPD/PdmV/tools/McM/')
from rest import McM


# McM instance
dev = False
dry_run = False
if dev:
    database_url = 'http://vocms0485:5984'
else:
    database_url = 'http://vocms0490:5984'

mcm = McM(dev=dev, cookie=os.getenv('DEV_COOKIE' if dev else 'PROD_COOKIE'))

# Current page of submitted requests
page = 0
# Page size
page_size = 500
submitted_requests = [{}]

# Dead requests
# Threshold in seconds for a request to be in one of the dead statuses
threshold_dead_seconds = 30 * 24 * 60 * 60  # 30 days
dead_statuses = set(['rejected', 'aborted', 'rejected-archived', 'aborted-archived'])

# Stuck in new requests
# Threshold in seconds for a request to be in new status
threshold_new_seconds = 5 * 24 * 60 * 60  # 5 days
new_statuses = set(['new'])

# Requests in normal-archived but not done
# Threshold in seconds for a request to be in archived status
threshold_archived_seconds = 14 * 24 * 60 * 60
archived_statuses = set(['normal-archived'])

# Requests stuck in their last status
# Threshold in seconds for a request to be in the last status
threshold_inactive_seconds = 365 * 24 * 60 * 60 # 365 days

# Threshold in seconds for ticket to be deleted
threshold_delete_tickets = 100 * 24 * 60 * 60
threshold_delete_tickets_notify = 95 * 24 * 60 * 60

# Counter for processed submitted requests
total_submitted = 0
# Lists for prepids of certain criteria
dead_prepids = []
status_new_prepids = []
assistance_manual_prepids = []


def make_simple_request(url):
    req = Request(url)
    try:
        return json.loads(urlopen(req).read().decode('utf-8'))
    except Exception as ex:
        print('Error while making a request to %s' % (url))
        print(ex)
        return None


def remove_tags(req, tags):
    existing_tags = list(req['tags'])
    new_tags = []
    for tag in existing_tags:
        if tag not in tags:
            new_tags.append(tag)

    req['tags'] = new_tags
    print('Request: %s' % (req['prepid']))
    print('  Set new tags: %s' % (req['tags']))


def add_note_and_tags(req, note=None, tags=None):
    if note:
        if req['notes']:
            req['notes'] = '%s\n\n%s' % (req['notes'], note)
        else:
            req['notes'] = note

    if tags:
        new_tags = list(req['tags'])
        for tag in tags:
            if tag not in new_tags:
                new_tags.append(tag)

        req['tags'] = list(set(new_tags))

    print('Request: %s' % (req['prepid']))
    if note:
        print('  Set new note: %s' % (req['notes']))

    if tags:
        print('  Set new tags: %s' % (req['tags']))


print('Threshold for dead status is %s seconds which is %.1f days. Dead statuses: %s' % (threshold_dead_seconds,
                                                                                         threshold_dead_seconds / 86400.0,
                                                                                         ', '.join(dead_statuses)))
print('Threshold for stuck in new status is %s seconds which is %.1f days. New statuses: %s' % (threshold_new_seconds,
                                                                                                threshold_new_seconds / 86400.0,
                                                                                                ', '.join(new_statuses)))
print('Threshold for archived status is %s seconds which is %.1f days. Archived statuses: %s' % (threshold_archived_seconds,
                                                                                                 threshold_archived_seconds / 86400.0,
                                                                                                 ', '.join(archived_statuses)))
print('Threshold for inactivity if %s seconds which is %.1f days' % (threshold_inactive_seconds, threshold_inactive_seconds / 86400.0))

print('Getting list of assistance-manual workflows from cms-unified')
assistance_manual_workflows = make_simple_request('http://cms-unified.web.cern.ch/cms-unified/public/statuses.json')
if not assistance_manual_workflows:
    print('Could not find any workflows in cms-unified')
    assistance_manual_workflows = []
else:
    assistance_manual_workflows = [prepid for prepid, value in assistance_manual_workflows.items() if 'assistance-manual' in value]

assistance_manual_workflows = set(assistance_manual_workflows)
print('Found %s workflows with assistance-manual status' % (len(assistance_manual_workflows)))

print('Starting to iterate through submitted requests...')
while len(submitted_requests) > 0:
    submitted_url = '%s/requests/_design/requests/_view/status?key="submitted"&limit=%s&skip=%s&include_docs=True' % (database_url, page_size, page_size * page)
    submitted_requests = [x['doc'] for x in make_simple_request(submitted_url).get('rows', [])]
    time.sleep(0.5)
    now = time.time()
    now_formatted = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))
    for request in submitted_requests:
        total_submitted += 1
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
        stats_last_workflow_url = 'http://vocms074:5984/requests/%s' % (last_workflow)
        stats_last_workflow = make_simple_request(stats_last_workflow_url)
        if not stats_last_workflow:
            print('Could not fetch %s workflow for %s' % (last_workflow, prepid))
            continue

        request_transitions = sorted(stats_last_workflow.get('RequestTransition', []), key=lambda x: x['UpdateTime'])
        if len(request_transitions) == 0:
            # workflow does not have request transitions
            print('%s (%s) does not have any transitions' % (last_workflow, prepid))
            continue

        last_transition = request_transitions[-1]
        last_transition_status = last_transition['Status']
        last_transition_time = last_transition['UpdateTime']
        last_transition_time_formatted = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_transition_time))
        last_transition_time_ago = now - last_transition_time

        # Check if request already has any of the tags
        requests_tags = request.get('tags', [])
        is_marked_dead = 'Dead' in requests_tags
        is_marked_status_new = 'StatusNew' in requests_tags
        is_marked_assistance_manual = 'StatusAssistance-Manual' in requests_tags

        if last_transition_status in dead_statuses and last_transition_time_ago > threshold_dead_seconds:
            # Last status is rejected or aborted and request has been in it for more than threshold_dead_seconds
            print('%s is Dead because last workflow %s is in dead status for more than %.1f days' % (prepid, last_workflow, threshold_dead_seconds / 86400.0))
            dead_prepids.append(prepid)
            if not is_marked_dead:
                note = 'Request %s is pronounced dead at %s as last status of %s is %s at %s. Request was rejected or aborted. Threshold is %s days.' % (
                    prepid,
                    now_formatted,
                    last_workflow,
                    last_transition_status,
                    last_transition_time_formatted,
                    int(threshold_dead_seconds / 86400.0))
                print(note)
                add_note_and_tags(request, note, ['Dead'])
                if not dry_run:
                    print('Saving %s: %s' % (prepid, mcm.update('requests', request)))

        elif last_transition_status in archived_statuses and last_transition_time_ago > threshold_archived_seconds:
            # Request has been archived for more than threshold_archived_seconds, most likely it was force completed
            print('%s is Dead because it is in archived status for more than %.1f days' % (prepid, threshold_archived_seconds / 86400.0))
            dead_prepids.append(prepid)
            if not is_marked_dead:
                note = 'Request %s is pronounced dead at %s as last status of %s is %s at %s. Request is archived. Threshold is %s days.' % (
                    prepid,
                    now_formatted,
                    last_workflow,
                    last_transition_status,
                    last_transition_time_formatted,
                    int(threshold_archived_seconds / 86400.0))
                print(note)
                add_note_and_tags(request, note, ['Dead'])  
                if not dry_run:
                    print('Saving %s: %s' % (prepid, mcm.update('requests', request)))

        elif last_transition_time_ago > threshold_inactive_seconds:
            # Workflow has been in last status for more than threshold_inactive_seconds
            print('%s is Dead because it is inactive for more than %.1f days' % (prepid, threshold_inactive_seconds / 86400.0))
            dead_prepids.append(prepid)
            if not is_marked_dead:
                note = 'Request %s is pronounced dead at %s as last status of %s is %s at %s. Request is inactive. Threshold is %s days.' % (
                    prepid,
                    now_formatted,
                    last_workflow,
                    last_transition_status,
                    last_transition_time_formatted,
                    int(threshold_inactive_seconds / 86400.0))
                print(note)
                add_note_and_tags(request, note, ['Dead'])
                if not dry_run:
                    print('Saving %s: %s' % (prepid, mcm.update('requests', request)))

        elif is_marked_dead:
            print('Removing Dead tag for %s as it became alive again' % (prepid))
            if not dry_run:
                remove_tags(request, ['Dead'])
                print('Saving %s: %s' % (prepid, mcm.update('requests', request)))

        if last_transition_status in new_statuses and last_transition_time_ago > threshold_new_seconds:
            # Request has been in new status for more than threshold_new_seconds
            print('%s is StatusNew has been in new status for more than %.1f days' % (prepid, threshold_new_seconds / 86400.0))
            status_new_prepids.append(prepid)
            if not is_marked_status_new:
                note = 'Request %s is pronounced stuck at %s as last status of %s is %s at %s. Request is still new. Threshold is %s days.' % (
                    prepid,
                    now_formatted,
                    last_workflow,
                    last_transition_status,
                    last_transition_time_formatted,
                    int(threshold_new_seconds / 86400.))
                print(note)
                add_note_and_tags(request, note, ['StatusNew'])
                if not dry_run:
                    print('Saving %s: %s' % (prepid, mcm.update('requests', request)))

        elif is_marked_status_new:
            print('Removing StatusNew tag for %s as it is no longer new. Current status %s' % (prepid, last_transition_status))
            if not dry_run:
                remove_tags(request, ['StatusNew'])
                if not dry_run:
                    print('Saving %s: %s' % (prepid, mcm.update('requests', request)))

        wfs_intersection_with_assistance_manual = set(workflows).intersection(assistance_manual_workflows)
        if len(wfs_intersection_with_assistance_manual) > 0:
            print('%s is StatusAssistance-Manual because workflow(s) %s are assistance-manual in cms-unified' % (prepid, ', '.join(wfs_intersection_with_assistance_manual)))
            assistance_manual_prepids.append(prepid)
            if not is_marked_assistance_manual:
                note = 'Request %s requires assistance because as of %s it was marked assistance-manual in cms-unified' % (
                    prepid,
                    now_formatted)
                print(note)
                add_note_and_tags(request, note, ['StatusAssistance-Manual'])
                if not dry_run:
                    print('Saving %s: %s' % (prepid, mcm.update('requests', request)))

        elif is_marked_assistance_manual:
            print('Removing StatusAssistance-Manual tag for %s as it is no longer in cms-unified.' % (prepid))
            if not dry_run:
                remove_tags(request, ['StatusAssistance-Manual'])
                if not dry_run:
                    print('Saving %s: %s' % (prepid, mcm.update('requests', request)))

    print('Total checked submitted: %s, dead: %s, status-new: %s, status-assistance-manual: %s, page: %s' % (
        total_submitted,
        len(dead_prepids),
        len(status_new_prepids),
        len(assistance_manual_prepids),
        page))

    page += 1

print('Finished tagging requests')
page = 0
dead_requests = [{}]
set_of_dead_prepids = set(dead_prepids)
for i in range(30):
    print('Sleeping before untagging Dead. %s' % (30 - i))
    time.sleep(1)

while len(dead_requests) > 0:
    print('Page %s of existing dead' % (page))
    dead_url = '%s/requests/_design/requests/_view/tags?key="Dead"&limit=%s&skip=%s&include_docs=True' % (database_url, page_size, page_size * page)
    dead_requests = [x['doc'] for x in make_simple_request(dead_url).get('rows', [])]
    print('Found %s requests in page %s' % (len(dead_requests), page))
    for request in dead_requests:
        prepid = request['prepid']
        print('Checking Dead for %s. It is %s %s' % (prepid, request.get('approval'), request.get('status')))
        if prepid not in set_of_dead_prepids:
            print('Removing Dead tag for %s' % (prepid))
            if not dry_run:
                remove_tags(request, ['Dead'])
                print('Saving %s: %s' % (prepid, mcm.update('requests', request)))

    page += 1

page = 0
status_new_requests = [{}]
set_of_status_new_prepids = set(status_new_prepids)
for i in range(30):
    print('Sleeping before untagging StatusNew. %s' % (30 - i))
    time.sleep(1)

while len(status_new_requests) > 0:
    print('Page %s of existing StatusNew' % (page))
    status_new_url = '%s/requests/_design/requests/_view/tags?key="StatusNew"&limit=%s&skip=%s&include_docs=True' % (database_url, page_size, page_size * page)
    status_new_requests = [x['doc'] for x in make_simple_request(status_new_url).get('rows', [])]
    print('Found %s requests in page %s' % (len(status_new_requests), page))
    for request in status_new_requests:
        prepid = request['prepid']
        print('Checking StatusNew for %s. It is %s %s' % (prepid, request.get('approval'), request.get('status')))
        if prepid not in set_of_status_new_prepids:
            print('Removing StatusNew tag for %s' % (prepid))
            if not dry_run:
                remove_tags(request, ['StatusNew'])
                print('Saving %s: %s' % (prepid, mcm.update('requests', request)))

    page += 1

page = 0
assistance_manual_requests = [{}]
set_of_assistance_manual_prepids = set(assistance_manual_prepids)
for i in range(30):
    print('Sleeping before untagging StatusAssistance-Manual. %s' % (30 - i))
    time.sleep(1)

while len(assistance_manual_requests) > 0:
    print('Page %s of existing StatusAssistance-Manual' % (page))
    assistance_manual_url = '%s/requests/_design/requests/_view/tags?key="StatusAssistance-Manual"&limit=%s&skip=%s&include_docs=True' % (database_url, page_size, page_size * page)
    assistance_manual_requests = [x['doc'] for x in make_simple_request(assistance_manual_url).get('rows', [])]
    print('Found %s requests in page %s' % (len(assistance_manual_requests), page))
    for request in assistance_manual_requests:
        prepid = request['prepid']
        print('Checking StatusAssistance-Manual for %s. It is %s %s' % (prepid, request.get('approval'), request.get('status')))
        if prepid not in set_of_assistance_manual_prepids:
            print('Removing StatusAssistance-Manual tag for %s' % (prepid))
            if not dry_run:
                remove_tags(request, ['StatusAssistance-Manual'])
                print('Saving %s: %s' % (prepid, mcm.update('requests', request)))

    page += 1

print('Deleting tickets')
tickets = mcm.get('mccms', query='status=new')
now = time.time()
for ticket in tickets:
    prepid = ticket.get('prepid')
    history = ticket.get('history', [])
    generated_chains = ticket.get('generated_chains', {})
    if generated_chains:
        continue

    if len(history) > 0:
        last_history_item = history[-1]
        ticket_timestamp = time.mktime(time.strptime(last_history_item['updater']['submission_date'], '%Y-%m-%d-%H-%M'))
        ticket_age = now - ticket_timestamp
        if (threshold_delete_tickets_notify - 4 * 60 * 60) <= ticket_age <= (threshold_delete_tickets_notify + 4 * 60 * 60):
            subject = 'MccM ticket %s will be deleted' % (prepid)
            message = 'MccM ticket %s will be deleted within next few days due to inactivity.' % (prepid)
            message += 'If you wish to keep this ticket, please act on it.'
            message += 'It has been inactive for %.2f days.' % (ticket_age / 86400)
            print(mcm._McM__put('restapi/mccms/notify', {'prepid': prepid, 'subject': subject, 'message': message}))
        elif now - ticket_timestamp > threshold_delete_tickets:
            print('%s: %s will be deleted' % (prepid, last_history_item['updater']['submission_date']))
            if not dry_run:
                subject = 'MccM ticket %s is deleted' % (prepid)
                message = 'MccM ticket %s is deleted due to inactivity.' % (prepid)
                message += 'It was inactive for %.2f days.' % (ticket_age / 86400)
                print(mcm._McM__put('restapi/mccms/notify', {'prepid': prepid, 'subject': subject, 'message': message}))
                time.sleep(3)
                print('Deleting %s: %s' % (prepid, mcm._McM__delete('restapi/mccms/delete/%s' % (prepid))))
