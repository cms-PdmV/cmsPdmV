import sys
import os
import json
import time
import types
import logging

sys.path.append(os.path.abspath(os.path.pardir))
from couchdb_layer.mcm_database import database
from json_layer.chained_request import chained_request
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
        logging.warning('Timeout of %ss reached' % (timeout))
        raise TimeoutException()

    if args is None:
        args = []

    if kwargs is None:
        kwargs = {}

    timeout = kwargs.pop('timeout', 30)
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)
    try:
        logging.info('Running %s with timeout %ss' % (func.__name__, timeout))
        result = func(*args, **kwargs)
    except TimeoutException:
        result = None
    finally:
        signal.alarm(0)

    return result


def get_all_chained_campaigns():
    chained_campaigns_db = database('chained_campaigns')
    all_chained_campaigns_result = do_with_timeout(chained_campaigns_db.query_view, 'prepid', timeout=300)
    if all_chained_campaigns_result:
        return [x['id'] for x in all_chained_campaigns_result]
    else:
        return []


def multiple_inspect(chained_campaign_prepids):
    chained_requests_db = database('chained_requests')
    logging.info('Chained campaigns inspect begin. Number of chained campaigns to be inspected: %s' % (len(chained_campaign_prepids)))
    for chained_campaign_index, chained_campaign_prepid in enumerate(chained_campaign_prepids):
        try:
            logging.info('Current chained campaign: %s (%s/%s)' % (chained_campaign_prepid, chained_campaign_index + 1, len(chained_campaign_prepids)))
            chained_requests_db.clear_cache()
            page = 0
            chained_requests = [{}]
            query = chained_requests_db.construct_lucene_complex_query([('member_of_campaign', {'value': [chained_campaign_prepid]}),
                                                                        ('last_status', {'value': 'done'}),
                                                                        ('status', {'value': 'processing'})])

            while len(chained_requests) > 0:
                logging.info('Page %s of %s' % (page, chained_campaign_prepid))
                chained_requests = do_with_timeout(chained_requests_db.full_text_search, 'search', query, page=page, timeout=300)
                if not chained_requests:
                    chained_requests = []
                    break

                chained_requests = [x for x in chained_requests if x.get('action_parameters', {}).get('flag', False)]
                logging.info('Inspecting chained requests of %s. Page: %s. Requests %s' % (chained_campaign_prepid, page, len(chained_requests)))
                for chained_request_dict in chained_requests:
                    logging.info('Inspecting %s. %s. Step %s' % (chained_request_dict['prepid'],
                                                                 '->'.join(chained_request_dict['chain']),
                                                                 chained_request_dict['step']))
                    time.sleep(0.01)
                    chained_req = chained_request(chained_request_dict)
                    if chained_req:
                        logging.info(json.dumps(do_with_timeout(chained_req.inspect, timeout=300), indent=2))
                    else:
                        logging.warning('%s does not exist' % (chained_request_dict['prepid']))

                    time.sleep(0.1)

                page += 1
                time.sleep(0.1)

            time.sleep(0.1)
        except Exception as e:
            logging.error('Exception while flowing chained campaign %s' % (chained_campaign_prepid))
            logging.error(e)


if __name__ == '__main__':
    def get_user_role(*args, **kwargs):
        return 'administrator'

    logging.basicConfig(format='[%(asctime)s][%(levelname)s] %(message)s', level=logging.INFO)
    authenticator.get_user_role = types.MethodType(get_user_role, authenticator())
    multiple_inspect(get_all_chained_campaigns())
