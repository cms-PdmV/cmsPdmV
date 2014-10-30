from tools.cmsweb_interface import cmsweb_interface
from tools.locator import locator

class reqmgr_interface:
    def __init__( self, proxy):
        self.cmsweb = cmsweb_interface( proxy )
        self.base_url = locator().cmsweburl()+'reqmgr/'

    def inject(self, request_dict ):
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Accept": "text/plain"}
        
        answer = self.cmsweb.generic_call(self.base_url+'create/makeSchema', header = headers, data = request_dict, load=False)
        if answer:
            ## yuks yuks and yuks : c.f wmcontrol
            workflow = answer.split("'")[1].split('/')[-1]
            return [workflow]
        else:
            print "Failed to inject the request dictionnary"
            return []

    def change_status( self, workflow, to_status):
        params = {"requestName": workflow,
                  "status": to_status
                  }
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Accept": "text/plain"}
        answer = self.cmsweb.generic_call(self.base_url+'reqMgr/request', header = headers, data = params, load=False)
        if answer:
            return True
        else:
            print "Failed to change the status to", to_status
            return False

    def assignmentapproved( self, workflow):
        return self.change_status( workflow, "assignment-approved")

    def change_priority( self, workflow , new_priority):
        params = {workflow + ":status": "",  
                  workflow+":priority": new_priority}
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Accept": "text/plain"}

        answer = self.cmsweb.generic_call(self.base_url+'view/doAdmin', header = headers, data = params, load=False)
        if answer:
            return True
        else:
            print "Failed to change priority"
            return False

