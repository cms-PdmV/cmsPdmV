import json
import time
import cherrypy

from tools.user_management import user_pack, access_rights
from couchdb_layer.mcm_database import database
from RestAPIMethod import RESTResourceIndex
from tools.json import threaded_loads

class GetAllNews(RESTResourceIndex):

    def get_all_news(self):
        db = database('news')
        __query = db.construct_lucene_query({'announced' : 'true'})
        return db.full_text_search('search', __query, page=-1)

    def GET(self, *args):
        """
        Get all news for home page or only the /n last
        """
        all_news= self.get_all_news()
        all_news.sort( key=lambda n : n['date'], reverse=True)
        if len(args):
            n_last=int(args[0])
            all_news = all_news[:n_last]

        return json.dumps(all_news)

class GetSingleNew(RESTResourceIndex):

    def get_single_new(self, doc_id):
        db = database('news')
        if not db.document_exists(doc_id):
            return {"results": {}}
        mcm_new = db.get(prepid=doc_id)
        return {"results": mcm_new}

    def GET(self, *args):
        """
        Get single new by _id of DB
        """
        if not args:
            self.logger.error('No arguments were given')
            return json.dumps({"results":{}})
        return json.dumps(self.get_single_new(args[0]))

class CreateNews(RESTResourceIndex):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def create_new(self, data):
        db = database('news')
        try:
            new_news = threaded_loads(data)
        except Exception as ex:
            return {"results":False}
        user_p = user_pack()
        new_news['author'] = user_p.get_username()
        #localtime = time.localtime(time.time())
        #datetime = ''
        #for i in range(5):
        #    datetime += str(localtime[i]).zfill(2)+'-'
        #datetime = datetime.rstrip('-')
        #datetime = '-'.join( map ('%02d'%localtime[0:5]))
        datetime = time.strftime('%Y-%m-%d-%H-%M')
        new_news['date'] = datetime
        new_news['announced'] = False
        db.save(new_news)
        return {"results":True}

    def PUT(self):
        """
        Create a new in news DB
        """
        return json.dumps(self.create_new(cherrypy.request.body.read().strip()))

class UpdateNew(RESTResourceIndex):
    def __init__(self):
        self.access_limit = access_rights.production_manager

    def update_new(self, data):
        try:
            news_data = threaded_loads(data)
        except Exception as ex:
            return {"results": False, 'message': str(ex)}
        db = database('news')
        if not db.document_exists(news_data['_id']):
            return {"results": False, 'message': 'new %s does not exist in News DB' % data['_id']}
       # self.db.update(dnews_ata)
        #mcm_new = self.db.get(prepid=doc_id)
        return {"results": db.update(news_data)}

    def PUT(self):
        """
        Update existing new in news DB
        """
        return json.dumps(self.update_new(cherrypy.request.body.read().strip()))
