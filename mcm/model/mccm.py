import datetime
from model.user import Role, User
from tools.exceptions import BadAttributeException

from tools.settings import Settings
from model.model_base import ModelBase
from couchdb_layer.mcm_database import Database
from tools.utils import expand_range


class MccM(ModelBase):

    _ModelBase__schema = {
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
    database_name = 'mccms'

    def validate(self):
        repetitions = int(self.get('repetitions'))
        if repetitions > 10:
            raise BadAttributeException(f'Too many repetitions: {repetitions}')

        self.get_request_list()
        return super().validate()

    def get_editing_info(self):
        info = super().get_editing_info()
        status = self.get('status')
        if status != 'new':
            return info

        user = User()
        user_role = user.get_role()
        is_admin = user_role >= Role.ADMINISTRATOR
        is_prod_expert = user_role >= Role.PRODUCTION_EXPERT
        is_prod_manager = user_role >= Role.PRODUCTION_MANAGER
        is_gen_convener = user_role >= Role.GENERATOR_CONVENER
        is_mc_contact = user_role >= Role.MC_CONTACT
        is_user = user_role >= Role.USER
        # Some are always editable
        info['block'] = is_mc_contact
        info['chains'] = is_mc_contact
        info['requests'] = is_mc_contact
        info['repetitions'] = is_mc_contact
        info['tags'] = is_mc_contact

        return info

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

    @staticmethod
    def get_mccm_by_generated_chain(chain_id):
        mccms_db = Database('mccms')
        result = mccms_db.search({'generated_chains': chain_id})
        if result and result[0]:
            return MccM(result[0])

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
        for entry in request_list:
            if isinstance(entry, list) and len(entry) == 2:
                requests.extend(expand_range(entry[0], entry[1]))
            elif isinstance(entry, str):
                requests.append(entry)
            else:
                raise BadAttributeException(f'Unrecognized prepid {entry} of type {type(entry)}')

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