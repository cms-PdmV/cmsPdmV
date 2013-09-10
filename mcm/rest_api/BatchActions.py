#!/usr/bin/env python

import cherrypy
from json import loads,dumps
from RestAPIMethod import RESTResource
from couchdb_layer.prep_database import database
from json_layer.batch import batch
from tools.locker import semaphore_events
from tools.settings import settings

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
class SaveBatch(RESTResource):
    def __init__(self):
        self.bdb = database('batches')
        self.access_limit = 3

    def PUT(self):
        """
        Save the content of a batch given the json content
        """
        data = loads(cherrypy.request.body.read().strip())
      
        data.pop('_rev')

        mcm_b = batch( data )
        
        self.bdb.save( mcm_b.json() )


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

class BatchAnnouncer(RESTResource):
    def __init__(self):
        self.bdb = database('batches')
        self.access_limit = 3

    def announce_with_text(self, bid, message):
        if not semaphore_events.is_set(bid):
            return {"results": False, "message": "Batch {0} has on-going submissions.".format(bid) , "prepid" : bid}
        b = batch(self.bdb.get(bid))
        r = b.announce(message)
        if r:
            return {"results":self.bdb.update(b.json()) , "message" : r , "prepid" : bid}
        else:
            return {"results":False , "prepid" : bid}
        

class AnnounceBatch(BatchAnnouncer):
    def __init__(self):
        BatchAnnouncer.__init__(self)

    def PUT(self):
        """
        Annouce a given batch id, with the provided notes in json content
        """
        return self.announce(loads(cherrypy.request.body.read().strip()))
    
    def announce(self, data):
        if not 'prepid' in data or not 'notes' in data:
            raise ValueError('no prepid nor notes in batch announcement api')
        bid=data['prepid']
        if not self.bdb.document_exists(bid):
            return dumps({"results":False, "message": "%s is not a valid batch name"%(bid)})
        
        return dumps(self.announce_with_text(bid, data['notes'] ))

    
class InspectBatches(BatchAnnouncer):
    def __init__(self):
        BatchAnnouncer.__init__(self)

    def GET(self, *args):
        """
        Look for batches that are new and with 1 requests or /N and announce them, or /batchid or /batchid/N
        """
        self.N_to_go=1
        bid=None
        if len(args):
            if args[0].isdigit():
                self.N_to_go=int(args[0])
            else:
                bid = args[0]
            if len(args)==2:
                self.N_to_go=int(args[1])

        res=[]
        if settings().get_value('batch_announce'):
            new_batches = self.bdb.queries(['status==new'])
            for new_batch in new_batches:
                if bid and new_batch['prepid']!=bid:  continue
                if len(new_batch['requests'])>=self.N_to_go:
                    ## it is good to be announced !
                    res.append( self.announce_with_text( new_batch['_id'], 'Automatic announcement.') )
        else:
            self.logger.log('Not announcing any batch')
        
        if settings().get_value('batch_set_done'):
            ## check on on-going batches
            rdb = database('requests')
            announced_batches = self.bdb.queries(['status==announced'])
            for announced_batch in announced_batches:
                if bid and announced_batch['prepid']!=bid:  continue
                all_done=False
                for r in announced_batch['requests']:
                    wma_name = r['name']
                    rid = r['content']['pdmv_prep_id']
                    mcm_r = rdb.get( rid )
                    all_done = ( mcm_r['status'] == 'done' )
                    if not all_done:
                        ## no need to go further
                        break
                if all_done:
                    ## set the status and save
                    mcm_b = batch(announced_batch)
                    mcm_b.set_status()
                    self.bdb.update( mcm_b.json() )
                    res.append({"results": True, "prepid" : bid, "message" : "Set to done"})
                else:
                    res.append({"results": False, "prepid" : bid, "message" : "Not completed"})
        else:
            self.logger.log('Not setting any batch to done')

        #anyways return something
        return dumps(res)

