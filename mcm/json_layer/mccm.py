import datetime

from tools.settings import Settings
from json_base import json_base
from couchdb_layer.mcm_database import database as Database


class mccm(json_base):

    _json_base__schema = {
        '_id': '',
        'prepid': '',
        'block': 0,
        'threshold': 0.,
        'meeting': '',
        'history': [],
        'notes': '',
        'pwg': '',
        'requests': [],
        'chains': [],
        'tags': [],
        'repetitions': 1,
        'status': 'new',
        'generated_chains': {},
        'total_events': 0  # Sum of request events in ticket not considering repetitions nor chains
    }

    _json_base__status = ['new', 'done']

    def __init__(self, json_input=None):
        json_input = json_input if json_input else {}

        repetitions = int(json_input.get('repetitions', 1))
        if repetitions > 10:
            self.logger.error('Too many repetitions: %s', repetitions)
            raise Exception('Too many repetitions: %s' % (repetitions))

        self.update(json_input)
        self.validate()
        # Make sure this does not throw any errors
        self.get_request_list()

    @staticmethod
    def get_meeting_date():
        """
        Get next meeting date
        """
        today = datetime.date.today()
        meeting_day = Settings.get('mccm_meeting_day')
        weeks = 0 if meeting_day >= today.weekday() else 1
        today = today + datetime.timedelta(days=meeting_day - today.weekday(), weeks=weeks)
        return today

    def get_editable(self):
        editable = {}
        schema = self._json_base__schema
        if self.get_attribute('status') == 'new':
            not_editable = {"status", "prepid", "meeting", "pwg",
                            "approval", "message_id", "generated_chains"}
            for key in schema:
                editable[key] = bool(key not in not_editable)

        else:
            for key in schema:
                editable[key] = False

        return editable

    @staticmethod
    def get_mccm_by_generated_chain(chain_id):
        mccms_db = Database('mccms')
        result = mccms_db.search({'generated_chains': chain_id})
        if result and result[0]:
            return mccm(json_input=result[0])

        return None

    def update_mccm_generated_chains(self, chains_requests_dict):
        generated_chains = self.get_attribute('generated_chains')
        for chain, requests in chains_requests_dict.iteritems():
            generated_chains.setdefault(chain, []).extend(requests)

        mccms_db = Database('mccms')
        mccms_db.save(self.json())

    def get_request_list(self):
        """
        Convert list of prepids and ranges to list of prepids
        """
        request_list = self.get_attribute("requests")
        requests = []
        prepid = self.get_attribute('prepid')
        for entry in request_list:
            if isinstance(entry, list) and len(entry) == 2:
                start = entry[0].split('-')
                end = entry[1].split('-')
                range_start = int(start[-1])
                range_end = int(end[-1])
                numbers = range(range_start, range_end + 1)
                start = '-'.join(start[:-1])
                end = '-'.join(end[:-1])
                if start != end:
                    raise Exception('Invalid range "%s-..." != "%s-..." for %s' % (start,
                                                                                   end,
                                                                                   prepid))

                if range_start > range_end:
                    raise Exception('Invalid range ...-%05d > ...-%05d' % (range_start, range_end))

                requests.extend('%s-%05d' % (start, n) for n in numbers)
            elif isinstance(entry, (basestring, str)):
                requests.append(entry)

        return requests

    def get_duplicate_requests(self):
        """
        Return requests that appear more than once in the list
        """
        frequency = {}
        for request in self.get_request_list():
            frequency[request] = frequency.setdefault(request, 0) + 1

        return [k for k, v in frequency.items() if v > 1]

    def update_total_events(self):
        """
        Calculate total events of requests
        """
        requests_db = Database('requests')
        prepids = self.get_request_list()
        requests = requests_db.bulk_get(prepids)
        events = sum(max(0, r.get('total_events', 0)) for r in requests if r)
        self.set_attribute('total_events', events)

    def all_requests_approved(self):
        """
        Return whether all requests are approved
        """
        request_prepids = self.get_request_list()
        request_db = Database('requests')
        requests = request_db.bulk_get(request_prepids)
        allowed_approvals = {'approve', 'submit'}
        for request in requests:
            if not request or request.get('approval') not in allowed_approvals:
                return False

        return True

    def get_defined_but_not_approved_requests(self):
        """
        Check if all requests are defined or approved
        If they are, return which are not yet approved
        If there are requests that are not defined, return empty list
        """
        request_prepids = self.get_request_list()
        request_db = Database('requests')
        requests = request_db.bulk_get(request_prepids)
        defined = {'define', 'approve', 'submit'}
        if [r for r in requests if not r or r.get('approval') not in defined]:
            # There are requests that are not defined/approved/submitted
            return []

        approved = {'approve', 'submit'}
        return [r['prepid'] for r in requests if r.get('approval') not in approved]

    def get_not_defined(self):
        """
        Get list of not defined requests
        """
        request_prepids = self.get_request_list()
        request_db = Database('requests')
        requests = request_db.bulk_get(request_prepids)
        defined = {'define', 'approve', 'submit'}
        defined_prepids = [r['prepid'] for r in requests if r and r.get('approval') in defined]
        not_defined_prepids = sorted(list(set(request_prepids) - set(defined_prepids)))
        return not_defined_prepids
