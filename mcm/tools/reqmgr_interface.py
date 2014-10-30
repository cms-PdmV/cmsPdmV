from tools.cmsweb_interface import tools.cmsweb_interface
from tools.locator import locator

class reqmgr_interface:
    def __init__( self, proxy):
        self.cmsweb = cmsweb_interface( proxy )
        self.base_url = locator().cmsweburl()+'reqmgr/'

    def inject(self, request_dict ):
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Accept": "text/plain"}
        
        answer = self.cmsweb.generic_call(self.base_url+'create/makeSchema', headers = headers, data = request_dict)
        workflow = answer
        return [workflow]

    def change_status( self, workflow, to_status):
        params = {"requestName": workflow,
                  "status": to_status}
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Accept": "text/plain"}
        answer = self.cmsweb.generic_call(self.base_url+'reqMgr/request', headers = headers, data = params)
        return answer

    def assignmentapproved( self, workflow):
        return self.change_status( workflow, "assignment-approved")

    def change_priority( self, workflow , new_priority):
        params = {workflow + ":status": "",  + ":priority": str(new_priority)}
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Accept": "text/plain"}
        answer = self.cmsweb.generic_call(self.base_url+'view/doAdmin', headers = headers, data = params)
        return answer

if __name__ == "__main__":
    req = reqmgr_interface('/afs/cern.ch/user/v/vlimant/private/personal/voms_proxy.cert')
    answer = req.change_priority('pdmvserv_EXO-Fall13-00210_00110_v0_HSCP_customise_140829_001534_7599', 75000)
    print answer
