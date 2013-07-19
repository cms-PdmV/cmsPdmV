import json

from couchdb_layer.prep_database import database
from RestAPIMethod import RESTResourceIndex

# generates the next valid prepid 
class GetAllNews(RESTResourceIndex):
    def __init__(self):
        self.db = database('news')

    def get_all_news(self):
        return self.db.get_all()

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
