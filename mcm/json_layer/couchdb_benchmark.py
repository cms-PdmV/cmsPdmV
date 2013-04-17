#!/usr/bin/env python

import couchdb
import simplejson
import threading
import Queue
import time
import sys

####################################################################
# benchmark wrappers
def nc_benchmark(db_name='', json_filename=''): # non-concurrent
    results = {}
    print '##################### Non-Concurrent Tests #####################'
    print 'Loading data...', 
    sys.stdout.flush()
    lines = []
    try:
        f = open(json_filename,  'r')
        lines = f.readlines()
        f.close()
    except Exception as ex:
        print 'Error while opening ', json_filename,  '. Reason:', str(ex)
        return False
    print 'OK'
    
    print 'Objects detected: ',  len(lines)
    if len(lines) == 0:
        print 'Exiting...'
        return False
    print 'Running Tests...'
    
    # bulk insert
    print 'Testing bulk document insertion (', len(lines),'): ', 
    sys.stdout.flush()
    t = get_time()
    flag = bulk_insert(db_name,  lines)
    t = get_duration(t)
    print flag,  ',',  t,  'secs'
    results['bulk_insert'] = flag,  t
    
    # sequential delete
    print 'Testing sequential document deletion:', 
    sys.stdout.flush()
    t = get_time()
    flag = sequential_delete(db_name)
    t = get_duration(t)
    print flag,  ',',  t,  'secs'
    results['seq_delete'] = flag,  t
    
    # sequential insert
    print 'Testing sequential insert:', 
    sys.stdout.flush()
    t = get_time()
    flag = sequential_insert(db_name, lines)
    t = get_duration(t)
    print flag,  ',',  t,  'secs'
    results['seq_insert'] = flag,  t
    
    # sort all
    print 'Testing temporary view (Sorting everything by "prepid"): ', 
    sys.stdout.flush()
    t = get_time()
    flag = sort_all(db_name,  'prepid')
    print flag, ',', get_duration(t),  'secs'
    
    # seq edit all
    print 'Testing sequential edit of every document: ', 
    sys.stdout.flush()
    t = get_time()
    flag = sequential_edit_all(db_name)
    t = get_duration(t)
    print flag,  ',',  t,  'secs'
    results['seq_edit'] = flag,  t
    
    # bulk edit all
    print 'Testing bulk edit of every document: ', 
    sys.stdout.flush()
    t = get_time()
    flag = bulk_edit_all(db_name)
    t = get_duration(t)
    print flag,  ',',  t,  'secs'
    results['bulk_edit'] = flag,  t
    
    # map 
    print 'Testing search on a parameter: ', 
    sys.stdout.flush()
    t = get_time()
    flag = test_find_specific_document(db_name,  prepid='EXO_Summer12_00001')
    t = get_duration(t)
    print flag,  ',',  t,  'secs'

    # delete db
    print 'Deleting database:', 
    sys.stdout.flush()
    t = get_time()
    flag = delete_db(db_name)
    print flag,  ',',  get_duration(t),  'secs'
    
    print 
    print 'Average:'
    for key in results:
        if results[key][0]:
            res = float(results[key][1]) / len(lines)
            if res:
                inv_res = int(1 / res)
            else:
                res = -1
            print key,  ': ',  res,  'secs / document', '\t(',  inv_res, 'documents / sec)'
    
    return True

def c_benchmark(db_name='',  json_filename=''):
    results = {}
    thread_num = 10
    queue = Queue.Queue()
    print
    print '##################### Concurrent Tests #####################'
    print 'Loading data...', 
    sys.stdout.flush()
    lines = []
    try:
        f = open(json_filename,  'r')
        lines = f.readlines()
        f.close()
    except Exception as ex:
        print 'Error while opening ', json_filename,  '. Reason:', str(ex)
        return False
    print 'OK'
    
    print 'Objects detected: ',  len(lines)
    if len(lines) == 0:
        print 'Exiting...'
        return False
    print 'Running Tests...'
    for line in lines:
        queue.put(line)
    
    # concurrent seq insert
    print thread_num,  'threads per action'
    print 'Testing concurrent sequential insert:', 
    sys.stdout.flush()
    t = get_time()
    flag = test_concurrent_seq_insert(db_name,  queue,  thread_num)
    t = get_duration(t)
    print flag,  ',',  t,  'secs'
    results['concurrent_seq_insert'] = flag,  t
    
    # concurrent seq delete
    print 'Testing concurrent sequential delete: ', 
    sys.stdout.flush()
    t = get_time()
    flag = test_concurrent_seq_delete(db_name,  thread_num)
    t = get_duration(t)
    print flag,  ',',  t,  'secs'
    results['concurrent_seq_delete'] = flag,  t
    
    # concurrent bulk insert
    for line in lines:
        queue.put(line)
    print 'Testing concurrent bulk insert: ', 
    sys.stdout.flush()
    t = get_time()
    flag = test_concurrent_bulk_insert(db_name,  queue,  thread_num)
    t = get_duration(t)
    print flag,  ',',  t,  'secs'
    results['concurrent_bulk_insert'] = flag,  t
    
    # concurrent sequential edit
    print 'Testing concurrent sequential edit of all documents: ', 
    sys.stdout.flush()
    t = get_time()
    flag = test_concurrent_seq_edit(db_name, thread_num)
    t = get_duration(t)
    print flag,  ',',  t,  'secs'
    results['concurrent_seq_edit'] = flag,  t
    
    # concurrent bulk edit
    print 'Testing concurrent bulk edit of all documents: ', 
    sys.stdout.flush()
    t = get_time()
    flag = test_concurrent_bulk_edit(db_name,  thread_num)
    t = get_duration(t)
    print flag,  ',',  t,  'secs'
    results['concurrent_bulk_edit'] = flag,  t
    
    # find average
    print 
    print 'Average:'
    for key in results:
        if results[key][0]:
            res = float(results[key][1]) / len(lines)
            if res:
                inv_res = int(1 / res)
            else:
                res = -1
            print key,  ': ',  res,  'secs / document', '\t(',  inv_res, 'documents / sec)'
    
    return True

def collision_benchmark(db_name=''):
    print
    print '##################### Collision Test #####################'
    ob = find_specific_document(prepid='Summer12')
    cct1 = concurrency_collision_test(db_name,  ob)
    cct2 = concurrency_collision_test(db_name,  ob)
    cct3 = concurrency_collision_test(db_name,  ob)
    cct4 = concurrency_collision_test(db_name,  ob)
    cct1.start()
    cct2.start()
    cct3.start()
    cct4.start()
    cct1.join()
    cct2.join()
    cct3.join()
    cct4.join()
    
def usage_emulation_benchmark(db_name='',  json_filename=''):
    print
    print '##################### Emulating User Behaviour #####################'
    print 'Loading data...', 
    sys.stdout.flush()
    lines = []
    try:
        f = open(json_filename,  'r')
        lines = f.readlines()
        f.close()
    except Exception as ex:
        print 'Error while opening ', json_filename,  '. Reason:', str(ex)
        return False
    print 'OK'
    
    em1 = EmUsage(db_name,  lines)
    em2 = EmUsage(db_name,  lines)
    em3 = EmUsage(db_name,  lines)
    em4 = EmUsage(db_name,  lines)
    em5 = EmUsage(db_name,  lines)
    em6 = EmUsage(db_name,  lines)
    em7 = EmUsage(db_name,  lines)
    em8 = EmUsage(db_name,  lines)
    
    em1.start()
    em2.start()
    em3.start()
    em4.start()
    em5.start()
    em6.start()
    em7.start()
    em8.start()
    em1.join()
    em2.join()
    em3.join()
    em4.join()
    em5.join()
    em6.join()
    em7.join()
    em8.join()
    
####################################################################
# aux methods

def get_time():
    return time.time()

def get_duration(start_time):
    return repr(time.time()-start_time)

def database(db_name=''):
    if not db_name:
        db_name = 'test'
    
    couch = couchdb.Server() # assume http://localhost:5984
    db = None
    try:
        db = couch.create('test')
    except couchdb.http.PreconditionFailed as ex:
        #print 'WARNING: ', ex[0][1]
        db = couch['test']
    return db
    
def find_specific_document(db_name='',  prepid=''):
    if not prepid:
        return False
    db = database(db_name)
    if not db:
        return False
    mapfun = '''def fun(doc):
        if doc['prepid'] == '{0}':
            yield doc['prepid'], doc'''.format(prepid)
    view = db.query(mapfun)
    for row in view:
        if row['key']== prepid:
            return row['value']['_id']
    return False
    
####################################################################
# non-concurrent tests

def test_find_specific_document(db_name='',  prepid=''):
    if not prepid:
        return False
    db = database(db_name)
    if not db:
        return False
    mapfun = '''def fun(doc):
        if doc['prepid'] == '{0}':
            yield doc['prepid'], doc'''.format(prepid)
    view = db.query(mapfun)
    for row in view:
        if row['key']== prepid:
            return True
    return False

def delete_db(db_name=''):
    couch = couchdb.Server()
    del couch[db_name]
    return True
    
def bulk_insert(db_name='',  lines=[]):
    docs = []
    db = database(db_name)
    if not db:
        return False
    for line in lines:
        if len(line) > 1:
            ob = simplejson.loads(line)
            docs.append(ob)
    
    if db:
        db.update(docs)
        return True
    else:
        return False
    
def sequential_insert(db_name='',  lines=[]):
    db = database(db_name)
    if not db:
        return False
    for line in lines:
        if len(line) > 1:
            ob = simplejson.loads(line)
            db.save(ob)
    return True
    
def sequential_edit_all(db_name=''):
    if not db_name:
        db_name = 'test'
    
    db = database(db_name)
    if not db:
        return False
    for id in db:
        ob = db[id]
        ob['type']=0
        db[id]=ob
    return True

def bulk_edit_all(db_name=''):
    obs = []
    if not db_name:
        db_name = 'test'
    db = database(db_name)
    if not db:
        return False
    for id in db:
        ob = db[id]
        ob['type']=0
        obs.append(ob)
    db.update(obs)
    return True

def sequential_delete(db_name=''):
    if not db_name:
        db_name = 'test'
    db = database(db_name)
    if db:
        for key in db:
            del db[key]
        return True
    else:
        return False
    
def sort_all(db_name='',  key=''):
    db = database(db_name)
    if not key:
        key='priority'
    mapfun = '''def fun(doc):
        if doc['{0}']:
            yield doc['{0}'],1'''.format(key)
    if db:
        view = db.query(mapfun)
        if len(view) > 0:
            return True
    return False

####################################################################
# concurrent tests

#def concurrent_bulk_insert(db,  json_filename)
class concurrent_sequential_insert(threading.Thread):
    def __init__(self,  db_name='',  queue=None):
        if not db_name:
            db_name = 'test'
        if not queue:
            raise Exception
        self.queue = queue
        self.db = database(db_name)
        threading.Thread.__init__(self)
        
    def run(self):
        if not self.queue:
            return False
        if not self.db:
            return False
        while not self.queue.empty():
            line = self.queue.get()
            if len(line) > 1:
                ob = simplejson.loads(line)
                self.db.save(ob)
        return True
        
def test_concurrent_seq_insert(db_name='',  queue=None,  thread_num=1):
    threads = []
    for i in range(thread_num):
        csi = concurrent_sequential_insert('test',  queue)
        csi.start()
        threads.append(csi)
    for t in threads:
        t.join()
    return True
        
class concurrent_sequential_delete(threading.Thread):
    def __init__(self,  db_name=''):
        if not db_name:
            db_name = 'test'
        self.db = database(db_name)
        threading.Thread.__init__(self)
    
    def run(self):
        if not self.db:
            return False
        for key in self.db:
            try:
                self.db.delete(self.db[key])
            except:
                continue
        return True
        
def test_concurrent_seq_delete(db_name='',  thread_num=1):
    threads = []
    for i in range(thread_num):
        csd = concurrent_sequential_delete(db_name)
        csd.start()
        threads.append(csd)
    for t in threads:
        t.join()
    return True

class concurrent_sequential_edit_all(threading.Thread):
    def __init__(self,  db_name=''):
        if not db_name:
            db_name = 'test'
        self.db = database(db_name)
        threading.Thread.__init__(self)
        
    def run(self):
        if not self.db:
            return False
        for key in self.db:
            ob = self.db.get(key)
            ob['type'] = 0
            try:
                self.db[key]=ob
            except:
                continue
        return True
        
def test_concurrent_seq_edit(db_name='',  thread_num=1):
    threads = []
    for i in range(thread_num):
        csd = concurrent_sequential_edit_all(db_name)
        csd.start()
        threads.append(csd)
    for t in threads:
        t.join()
    return True
    
class concurrent_bulk_edit_all(threading.Thread):
    def __init__(self,  db_name=''):
        if not db_name:
            db_name = 'test'
        self.db = database(db_name)
        threading.Thread.__init__(self)
        
    def run(self):
        obs = []
        if not self.db:
            return False
        for key in self.db:
            ob = self.db.get(key)
            ob['type'] = 0
            obs.append(ob)
        try:
            self.db.update(obs)
        except:
            return False
        return True
    
def test_concurrent_bulk_edit(db_name='',  thread_num=1):
    threads = []
    for i in range(thread_num):
        csd = concurrent_bulk_edit_all(db_name)
        csd.start()
        threads.append(csd)
    for t in threads:
        t.join()
    return True

class concurrent_bulk_insert(threading.Thread):
    def __init__(self,  db_name='',  queue=None):
        if not db_name:
            db_name = 'test'
        if not queue:
            raise Exception
        self.queue = queue
        self.db = database(db_name)
        threading.Thread.__init__(self)
        
    def run(self):
        obs = []
        if not self.queue:
            return False
        if not self.db:
            return False
        while not self.queue.empty():
            line = self.queue.get()
            if len(line) > 1:
                ob = simplejson.loads(line)
                obs.append(ob)
        try:
            self.db.update(obs)
        except:
            return False
        return True
    
def test_concurrent_bulk_insert(db_name='',  queue=None,  thread_num=1):
    threads = []
    for i in range(thread_num):
        csd = concurrent_bulk_insert(db_name,  queue)
        csd.start()
        threads.append(csd)
    for t in threads:
        t.join()
    return True

class concurrency_collision_test(threading.Thread):
    def __init__(self,  db_name='',  idz=''):
        if not db_name:
            db_name='test'
        self.db = database(db_name)
        self.id = idz
        threading.Thread.__init__(self)
    
    def run(self):
        # prep collision test
        print self.getName,  'Starting...'
        if not self.id:
            return False
        if not self.db:
            return False
        
        # init collision test
        ob = self.db[self.id]
        if not ob:
            return False
            
        i = ob['type'] # type counter
        j = 0 # collision counter
        t = get_time()
        # begin
        while  True:
            # get global state
            ob = self.db[self.id]
            if not ob:
                return False
                
            # update 
            i +=1
            if i >= 2000:
                break
            
            # change it
            ob['type'] = i
            
            # try to make persistent
            try:
                self.db[self.id] = ob
            except Exception: # collision !
                j += 1
                i -= 1
            

        t = get_duration(t)
        print self.getName,'time:', t,'collisions:', j,  'updates:',  i
        
        ####################
        # revert to zero
#        ob = self.db[self.id]
#        if not ob:
#            return False
#        
#        # update 
#        i = ob['type']
#        
#        # change it
#        ob['type'] = 0
#        
#        # try to make persistent
#        try:
#            self.db[self.id] = ob
#        except Exception: # collision !
#            pass
        
        ####################
        
        return True
        
####################################################################
# emulate real usage
from request import request
from generator_parameters import generator_parameters
import os
import random
class EmUsage(threading.Thread):
    def __init__(self,  db_name='',  lines=[]):

        random.seed(os.urandom(100))
        self.db = database(db_name)
        self.prepids = []
        if self.db:
            self.db_name = db_name
        self.objects = []
        for i in range(20):
            self.objects.append(lines[random.randint(0, len(lines)-1)])
        for ob in self.objects:
            self.prepids.append(simplejson.loads(ob)['prepid'])
        threading.Thread.__init__(self)
    
    def get_request(self,  prepid=''):
        mapfun = '''def fun(doc):
            if doc['prepid'] == '{0}':
                yield doc['prepid'], doc'''.format(prepid)
        try:
            view = self.db.query(mapfun)
            t = get_time()
            for row in view:
                print get_duration()
                if prepid in row['key']:            
                    return row['value']
        except Exception as ex:
            return None
    
    def approve_request(self,  prepid=''):
        while True:
            ob = self.get_request(prepid)
            if not ob:
                return False
            rt = request('Nikolaos', request_json=ob)
            try:
                rt.approve('Nikolaos')
            except Exception as ex:
                pass
            try:
                self.db.update([rt.json()])
                return True
            except couchdb.ResourceConflict:
                print 'collision!',  self.getName()
                time.sleep(1)
                continue
                
    def add_new_gen_parameters(self,  prepid=''):
        while True:
            ob = self.get_request(prepid)
            if not ob:
                return False
            rt = request('Nikolaos', request_json=ob)
            try:
                rt.update_generator_parameters(generator_parameters('Nikolaos').build())
            except Exception as ex:
                pass
            try:
                self.db.update([rt.json()])
                return True
            except couchdb.ResourceConflict:
                print 'collision!',  self.getName()
                time.sleep(1)
                continue
                
    def do_smt(self):
        if not self.db:
            return False
        # insert
        if not bulk_insert(self.db_name,  self.objects):
            return False
        # approve
        #print self.prepids
        for prepid in self.prepids:
            self.approve_request(prepid)
            self.add_new_gen_parameters(prepid)
        
        return True
            
    def run(self):
        t = get_time()
        self.do_smt()
        t = get_duration(t)
        print self.getName(),  t,  get_time()
if __name__=='__main__':
    nc_benchmark('test',  '../../prepdb_json/campaigns')
    c_benchmark('test',  '../../prepdb_json/campaigns')
    collision_benchmark('test')
    delete_db('test')
    #usage_emulation_benchmark('test',  'prepdb_data/requests')
