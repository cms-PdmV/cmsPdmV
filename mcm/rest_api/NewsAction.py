import json
import time
import cherrypy

from couchdb_layer.prep_database import database
from RestAPIMethod import RESTResourceIndex

# generates the next valid prepid 
class GetAllNews(RESTResourceIndex):
    def __init__(self):
        self.db = database('news')

    def get_all_news(self):
        #return self.db.get_all()
        return self.db.queries(['announced=="true"'])

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
    def __init__(self):
        self.db = database('news')#

    def get_single_new(self, doc_id):
        if not self.db.document_exists(doc_id):
            return dumps({"results": {}})
        mcm_new = self.db.get(prepid=doc_id)
        return json.dumps({"results":mcm_new})

    def GET(self, *args):
        """
        Get single new by _id of DB
        """
        if not args:
            self.logger.error('No arguments were given')
            return json.dumps({"results":{}})
        return self.get_single_new(args[0])

class CreateNews(RESTResourceIndex):
    def __init__(self):
        self.db = database('news')#
        self.New = None
        self.access_limit = 3

    def create_new(self, data):
        try:
            self.New = json.loads(data)
        except Exception as ex:
            return json.dumps({"results":False})
        
        self.New['author'] = cherrypy.request.headers['ADFS-LOGIN']
        #localtime = time.localtime(time.time())
        #datetime = ''
        #for i in range(5):
        #    datetime += str(localtime[i]).zfill(2)+'-'
        #datetime = datetime.rstrip('-')
        #datetime = '-'.join( map ('%02d'%localtime[0:5]))
        datetime = time.strftime('%Y-%m-%d-%H-%M')
        self.New['date'] = datetime
        self.New['announced'] = False
        self.db.save(self.New)
        return json.dumps({"results":True})

    def PUT(self):
        """
        Create a new in news DB
        """
        return self.create_new(cherrypy.request.body.read().strip())

class UpdateNew(RESTResourceIndex):
    def __init__(self):
        self.db = database('news')#
        self.access_limit = 3

    def update_new(self, data):
        try:
          news_data = json.loads(data)
        except Exception as ex:
            return json.dumps({"results":False, 'message': str(ex)})
        if not self.db.document_exists(news_data['_id']):
            return json.dumps({"results":False, 'message' : 'new %s does not exist in News DB'%( data['_id']) })
       # self.db.update(dnews_ata)
        #mcm_new = self.db.get(prepid=doc_id)
        return json.dumps({"results":self.db.update(news_data)})

    def PUT(self):
        """
        Update existing new in news DB
        """
        return self.update_new(cherrypy.request.body.read().strip())
