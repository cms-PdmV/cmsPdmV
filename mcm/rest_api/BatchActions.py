#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from RestAPIMethod import RESTResource
from couchdb_layer.prep_database import database
from json_layer.batch import batch

"""
class SetStatus(RESTResource):
    def __init__(self):
        self.db = database('batches')
        self.access_limit = 
    def GET(self, *args):
        if not args:
            return dumps({"results":'Error: No arguments were given'})
        return self.multiple_status(args[0])

    def multiple_status(self, rid):
        if ',' in rid:
            rlist = rid.rsplit(',')
            res = []
            for r in rlist:
                 res.append(self.status(r))
            return dumps(res)
        else:
            return dumps(self.status(rid))

    def status(self, rid):
        if not self.db.document_exists(rid):
            return {"prepid": rid, "results":'Error: The given request id does not exist.'}

        req = batch(json_input=self.db.get(rid))

        try:
            req.set_status(step)
        except json_base.WrongStatusSequence as ex:
            return {"prepid":rid, "results":False, 'message' : str(ex)}
        except:
            return {"prepid":rid, "results":False, 'message' : 'Unknow error'}

        return {"prepid": rid, "results":self.db.update(req.json())}
"""

class GetBatch(RESTResource):
    def __init__(self):
        self.db_name = 'batches'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
        Retrieve the json content of given batch id
        """
        if not args:
            self.logger.error("No Arguments were given")
            return dumps({"results":'Error: No arguments were given'})
        return self.get_request(args[0])

    def get_request(self, data):
        return dumps({"results":self.db.get(prepid=data)})

class GetAllBatches(RESTResource):
    def __init__(self):
        self.db_name = 'batches'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
        Retrieve the json content of the batch db
        """
        return self.get_all()

    def get_all(self):
        return dumps({"results":self.db.get_all()})

class GetIndex(RESTResource):
    def __init__(self):
        self.db_name = 'batches'
        self.db = database(self.db_name)

    def GET(self, *args):
        """
        Redirect to the proper link to a given batch id
        """
        if not args:
            self.logger.error("No Arguments were given")
            return dumps({"results":'Error: No arguments were given'})
        id=args[0]
        if not self.db.document_exists(id):
            return dumps({"results":False, "message": "%s is not a valid batch name"%(id)})
        #yurks ?
        redirect="""\
<html>
<meta http-equiv="REFRESH" content="0; url=/mcm/batches?prepid=%s&page=0">
</html>
"""%(id)
        return redirect
    

class AnnounceBatch(RESTResource):
    def __init__(self):
        self.db_name = 'batches'
        self.db = database(self.db_name) 
        self.access_limit = 3

    def PUT(self):
        """
        Annouce a given batch id, with the provided notes in json content
        """
        return self.announce(loads(cherrypy.request.body.read().strip()))
    
    def announce(self, data):
        if not 'prepid' in data or not 'notes' in data:
            raise ValueError('no prepid nor notes in batch announcement api')
        bid=data['prepid']
        if not self.db.document_exists(bid):
            return dumps({"results":False, "message": "%s is not a valid batch name"%(bid)})
        
        b = batch(self.db.get(bid))
        r=b.announce(data['notes'])
        if r:
            return dumps({"results":self.db.save(b.json()) , "value" : r})
        else:
            return dumps({"results":False})
        
    

        

