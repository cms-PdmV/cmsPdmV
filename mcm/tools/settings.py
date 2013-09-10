from couchdb_layer.prep_database import database

class settings:
    def __init__(self):
        self.cache={}
        pass
    
    def get(self, label ):
        if not label in self.cache:
            sdb = database('settings')
            setting = sdb.get( label )
            self.cache['label'] = setting
        return self.cache['label']
            
    def get_value(self, label ):
        return self.get(label)['value']
    
