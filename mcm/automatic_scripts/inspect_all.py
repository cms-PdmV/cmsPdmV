import sys
import os
import time
from random import shuffle
sys.path.append(os.path.abspath(os.path.pardir))
from couchdb_layer.mcm_database import Database


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


def inspect_campaign(campaign_prepid):
    return os.system('curl -k -L -s --cookie %s https://cms-pdmv.cern.ch/mcm/restapi/campaigns/inspect/%s' % (os.getenv('PROD_COOKIE'), campaign_prepid))


def get_all_campaigns():
    campaigns_db = database('campaigns')
    all_campaigns_result = do_with_timeout(campaigns_db.get_all, timeout=300)
    if all_campaigns_result:
        prepids_list = [x['_id'] for x in all_campaigns_result]
    else:
        prepids_list = []

    shuffle(prepids_list)
    return prepids_list


def multiple_inspect():
    campaign_prepids = get_all_campaigns()
    print('Campaigns inspect begin. Number of campaigns to be inspected: %s' % (len(campaign_prepids)))
    for campaign_index, campaign_prepid in enumerate(campaign_prepids):
        try:
            print('*** Current campaign: %s (%s/%s) ***' % (campaign_prepid, campaign_index + 1, len(campaign_prepids)))
            result = do_with_timeout(inspect_campaign, campaign_prepid, timeout=3600)
            print('*** Finished inspecting campaign %s, result %s ***' % (campaign_prepid, result))
            time.sleep(0.5)
        except Exception as e:
            print('Exception while inspecting campaign %s' % (campaign_prepid))
            print(e)


if __name__ == '__main__':
    multiple_inspect()
