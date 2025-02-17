import os
import sys
import tempfile
import time
from pathlib import Path
from random import shuffle

# Make sure the McM package is installed:
# https://github.com/cms-PdmV/mcm_scripts?tab=readme-ov-file#build-package
from rest import McM

sys.path.append(os.path.abspath(os.path.pardir))
from couchdb_layer.mcm_database import database

from inspect_all import do_with_timeout

# McM client
cookie_file = Path(tempfile.TemporaryDirectory().name) / Path("cookie.txt")
mcm = McM(dev=False, debug=False, cookie=cookie_file)

def inspect_chained_request(prepid):
    results = mcm.session.get(url=mcm.server + f"restapi/chained_requests/inspect/{prepid}")
    print("Inspect chained request HTTP request code: ", results.status_code)
    return results.text


def get_all_chained_campaigns():
    chained_campaigns_db = database('chained_campaigns')
    all_chained_campaigns_result = do_with_timeout(chained_campaigns_db.get_all, timeout=300)
    if all_chained_campaigns_result:
        prepids_list = [x['_id'] for x in all_chained_campaigns_result]
    else:
        prepids_list = []

    shuffle(prepids_list)
    return prepids_list


def multiple_inspect():
    chained_campaign_prepids = get_all_chained_campaigns()
    chained_requests_db = database('chained_requests')
    print(('Chained campaigns inspect begin. Number of chained campaigns to be inspected: %s' % (len(chained_campaign_prepids))))
    for chained_campaign_index, chained_campaign_prepid in enumerate(chained_campaign_prepids):
        try:
            print(('Current chained campaign: %s (%s/%s)' % (chained_campaign_prepid, chained_campaign_index + 1, len(chained_campaign_prepids))))
            chained_requests_db.clear_cache()
            page = 0
            chained_requests = [{}]
            query = {'member_of_campaign': chained_campaign_prepid,
                     'last_status': 'done',
                     'status': 'processing'}

            while chained_requests:
                print(('Chained campaign %s page %s' % (chained_campaign_prepid, page)))
                chained_requests = do_with_timeout(chained_requests_db.search, query, page=page, timeout=120)
                if not chained_requests:
                    break

                page += 1
                chained_requests = [x for x in chained_requests if x.get('action_parameters', {}).get('flag', False)]
                print(('Inspecting chained requests of %s page %s number of requests %s' % (chained_campaign_prepid, page, len(chained_requests))))
                for chained_request_dict in chained_requests:
                    print(('Inspecting %s. %s. Step %s' % (chained_request_dict['prepid'],
                                                          '->'.join(chained_request_dict['chain']),
                                                          chained_request_dict['step'])))
                    try:
                        result = do_with_timeout(inspect_chained_request, chained_request_dict['prepid'], timeout=120)
                        time.sleep(0.01)
                    except Exception as e:
                        print(('Exception while inspecting chained request %s' % (chained_request_dict['prepid'])))
                        print(e)

        except Exception as e:
            print(('Exception while inspecting %s' % (chained_campaign_prepid)))
            print(e)

if __name__ == '__main__':
    multiple_inspect()
