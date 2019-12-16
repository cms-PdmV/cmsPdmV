import sys
import os
import json
import time
import types
sys.path.append(os.path.abspath(os.path.pardir))
from couchdb_layer.mcm_database import database
from json_layer.request import request
from tools.user_management import authenticator


def do_with_timeout(func, *args, **kwargs):
    """
    Run function func with given timeout in seconds
    Return None if timeout happens
    """
    import signal

    class TimeoutException(Exception):
        pass

    def handler(signum, frame):
        print('Timeout of %ss reached' % (timeout))
        raise TimeoutException()

    if args is None:
        args = []

    if kwargs is None:
        kwargs = {}

    timeout = kwargs.pop('timeout', 30)
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)
    try:
        print('Running %s with timeout %ss' % (func.__name__, timeout))
        result = func(*args, **kwargs)
    except TimeoutException:
        result = None
    finally:
        signal.alarm(0)

    return result


def get_all_campaigns():
    campaigns_db = database('campaigns')
    all_campaigns_result = do_with_timeout(campaigns_db.raw_query, 'prepid', timeout=300)
    if all_campaigns_result:
        prepids_list = [x['id'] for x in all_campaigns_result]
    else:
        prepids_list = []

    return prepids_list


def multiple_inspect(campaign_prepids):
    request_statuses = ['submitted', 'approved']
    requests_db = database('requests')
    print('Campaigns inspect begin. Number of campaigns to be inspected: %s' % (len(campaign_prepids)))
    for campaign_index, campaign_prepid in enumerate(campaign_prepids):
        try:
            print('Current campaign: %s (%s/%s)' % (campaign_prepid, campaign_index + 1, len(campaign_prepids)))
            requests_db.clear_cache()
            page = 0
            requests = [{}]
            query = requests_db.construct_lucene_complex_query([('member_of_campaign', {'value': [campaign_prepid]}),
                                                                ('status', {'value': request_statuses})])

            while len(requests) > 0:
                requests = do_with_timeout(requests_db.full_text_search, 'search', query, page=page, timeout=300)
                if not requests:
                    requests = []

                print('Inspecting requests of %s. Page: %s. Requests %s' % (campaign_prepid, page, len(requests)))
                for req_dict in requests:
                    print('Inspecting %s. %s-%s' % (req_dict['prepid'], req_dict['approval'], req_dict['status']))
                    req = request(req_dict)

                    if req:
                        print(json.dumps(do_with_timeout(req.inspect, timeout=300), indent=2))
                    else:
                        print('%s does not exist' % (req_dict['prepid']))

                    time.sleep(0.1)

                page += 1
                time.sleep(0.1)

            time.sleep(0.1)
        except Exception as e:
            print('Exception while inspecting campaign %s' % (campaign_prepid))
            print(e)


if __name__ == '__main__':
    def get_user_role(*args, **kwargs):
        return 'administrator'

    authenticator.get_user_role = types.MethodType(get_user_role, authenticator())
    multiple_inspect(get_all_campaigns())
