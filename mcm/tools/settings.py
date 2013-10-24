from couchdb_layer.mcm_database import database
from tools.locker import locker

class settings:
    cache=dict()
    def __init__(self):
        self.__db = database('settings')
    
    def get(self, label):
        with locker.lock(label):
            if not label in self.cache:
                setting = self.__db.get(label)
                self.cache[label] = setting
            return self.cache[label]
            
    def get_value(self, label ):
        return self.get(label)['value']

    def get_notes(self, label ):
        return self.get(label)['notes']

    def set(self, label, setting):
        with locker.lock(label):
            result = self.__db.update(setting)
            if result:
                self.cache[label] = setting
            return result

