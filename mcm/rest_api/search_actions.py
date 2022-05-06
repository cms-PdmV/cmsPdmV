import flask
from rest_api.api_base import RESTResource

from couchdb_layer.mcm_database import Database
from tools.utils import clean_split, expand_range


class Search(RESTResource):
    """
    Super-generic search through database (uses __all__ attribute in __init__.py of json_layer package)
    """

    from model.batch import Batch
    from model.campaign import Campaign
    from model.flow import Flow
    from model.mccm import MccM
    from model.chained_campaign import ChainedCampaign
    from model.request import Request
    from model.chained_request import ChainedRequest
    from model.invalidation import Invalidation
    modules = {'batches': Batch,
               'campaigns': Campaign,
               'chained_campaigns': ChainedCampaign,
               'chained_requests': ChainedRequest,
               'flows': Flow,
               'invalidations': Invalidation,
               'mccms': MccM,
               'requests': Request,
               'settings': None,
               'users': None}
    casting = None

    @classmethod
    def prepare_casting(cls):
        cls.logger.info('Preparing attribute casting in search')
        cls.casting = {}
        for database_name, class_obj in cls.modules.items():
            if not class_obj:
                cls.casting[database_name] = {}
                continue

            schema = class_obj.schema()
            if not schema:
                cls.casting[database_name] = {}
                continue

            cls.casting[database_name] = {}
            for schema_key, schema_value in schema.items():
                schema_type = type(schema_value)
                if schema_type in [int, float]:
                    cls.casting[database_name][schema_key] = '%s<%s>' % (schema_key,
                                                                         schema_type.__name__)

    def __init__(self):
        if not self.casting:
            self.prepare_casting()

    def get(self):
        args = flask.request.args.to_dict()
        self.logger.debug('Search: %s', ','.join('%s=%s' % (k, v) for k, v in args.items()))
        db_name = args.pop('db_name', 'requests')
        page = int(args.pop('page', 0))
        limit = int(args.pop('limit', 20))
        include_fields = args.pop('include_fields', '')
        sort_on = args.pop('sort', None)
        sort_asc = args.pop('sort_asc', 'True').lower() != 'false'
        # Drop get_raw attribute
        args.pop('get_raw', None)
        # Drio alias attribute
        args.pop('alias', None)

        if db_name not in self.modules:
            return {'results': False, 'message': 'Invalid database name %s' % (db_name)}

        if page == -1 and not args and db_name == 'requests':
            return {"results": False, "message": "Why you stupid? Don't be stupid..."}

        database = Database(db_name)
        args = {k: clean_split(v) if k != 'range' else v for k, v in args.items()}
        # range - requests, chained_requests, tickets
        get_range  = args.pop('range', None)
        if get_range and db_name in ('requests', 'chained_requests', 'tickets'):
            # Get range of objects
            # Syntax: a,b;c,d;e;f
            args['prepid_'] = []
            for part in clean_split(get_range, ';'):
                if ',' in part:
                    parts = part.split(',')
                    args['prepid_'].extend(expand_range(parts[0], parts[-1]))
                else:
                    args['prepid_'].append(part)

        # from_ticket - chained_requests
        from_ticket = args.pop('from_ticket', None)
        if from_ticket and db_name in ('chained_requests',):
            # Get chained requests generated from the ticket
            mccm_db = Database('mccms')
            if len(from_ticket) == 1 and '*' not in from_ticket[0]:
                mccms = [mccm_db.get(from_ticket[0])]
            else:
                mccms = mccm_db.search({'prepid': from_ticket}, limit=None)

            args['prepid__'] = []
            for mccm in mccms:
                args['prepid__'].extend(mccm.get('generated_chains', []).keys())

        if not args and not sort_on:
            # If there are no args, use simpler fetch
            response = database.get_all(page, limit, with_total_rows=True)
        else:
            # Add types to arguments
            args = {self.casting[db_name].get(k, k): v for k, v in args.items()}
            if not args:
                args = {'_id': '*'}

            if sort_on:
                sort_on = self.casting[db_name].get(sort_on, f'{sort_on}<string>')

            # Construct the complex query
            response = database.search(args, page, limit, include_fields, True, sort_on, sort_asc)

        response['results'] = response.pop('rows', [])
        return response
