from threading import Thread
import simplejson

def threaded_loads(json, loads=True):
    """
    Running json loads in another thread (blocking until it returns)
    so that cherrypy worker threads don't eat up all memory
    """

    class LoadingThread(Thread):
        """
        Threaded simplejson load.
        """

        def __init__(self, dat, loads):
            self.return_final = None
            self.dat = dat
            self.loads = loads
            Thread.__init__(self)

        def run(self):
            self.return_final = simplejson.loads(self.dat) if self.loads else simplejson.dumps(self.dat)

    th = LoadingThread(json, loads)
    th.start()
    th.join()
    return th.return_final