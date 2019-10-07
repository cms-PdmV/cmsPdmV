import sys
import os
sys.path.append(os.path.abspath(os.path.pardir))
from couchdb_layer.mcm_database import database
from json_layer.request import request
import time
import json


def get_all_campaigns():
    campaigns_db = database('campaigns')
    all_campaigns = campaigns_db.raw_query('prepid')
    prepids_list = [x['id'] for x in all_campaigns]
    return prepids_list


def multiple_inspect(campaign_prepids):
    request_statuses = ['submitted', 'approved']
    requests_db = database('requests')
    print('Campaigns inspect begin. Number of campaigns to be inspected: %s' % (len(campaign_prepids)))
    for campaign_index, campaign_prepid in enumerate(campaign_prepids):
        try:
            print('Current campaign: %s (%s/%s)' % (campaign_prepid, campaign_index + 1, len(campaign_prepids)))
            page = 0
            requests = [{}]
            query = requests_db.construct_lucene_complex_query([('member_of_campaign', {'value': [campaign_prepid]}),
                                                                ('status', {'value': request_statuses})])

            while len(requests) > 0:
                requests = requests_db.full_text_search('search', query, page=page)
                print('Inspecting requests of %s. Page: %s. Requests %s' % (campaign_prepid, page, len(requests)))
                for req_dict in requests:
                    print('Inspecting %s. %s-%s' % (req_dict['prepid'], req_dict['approval'], req_dict['status']))
                    req = request(req_dict)
                    req.current_user_level = 4

                    if req:
                        print(json.dumps(req.inspect(), indent=2))
                    else:
                        print('%s does not exist' % (req_dict['prepid']))

                    time.sleep(0.2)

                page += 1
                time.sleep(0.5)

            time.sleep(1)
        except Exception as e:
            print('Exception while inspecting campaign %s' % (campaign_prepid))
            print(e)


if __name__ == '__main__':
    multiple_inspect(get_all_campaigns())

