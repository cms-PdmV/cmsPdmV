from rest_api.RestAPIMethod import RESTResource
from json import dumps, loads
from couchdb_layer.mcm_database import database
from json_layer.mccm import mccm
from tools.locker import locker
from tools.locator import locator
from tools.communicator import communicator
from tools.settings import settings

import cherrypy


class GetMccm(RESTResource):

    def GET(self, *args):
        """
        Retreive the dictionnary for a given mccm
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": {}})
        return self.get_doc(args[0])

    def get_doc(self, data):
        db = database('mccms')
        if not db.document_exists(data):
            return dumps({"results": {}})
        mccm_doc = db.get(prepid=data)

        return dumps({"results": mccm_doc})

class UpdateMccm(RESTResource):
    def __init__(self):
        self.access_limit = 1

    def PUT(self):
        """
        Updating an existing mccm with an updated dictionary
        """
        try:
            res = self.update(cherrypy.request.body.read().strip())
            return res
        except:
            self.logger.error('Failed to update an mccm from API')
            return dumps({'results': False, 'message': 'Failed to update an mccm from API'})

    def update(self, body):
        data = loads(body)
        if '_rev' not in data:
            self.logger.error('Could not locate the CouchDB revision number in object: %s' % data)
            return dumps({"results": False, 'message': 'could not locate revision number in the object'})
        db = database('mccms')
        if not db.document_exists(data['_id']):
            return dumps({"results": False, 'message': 'mccm %s does not exist' % ( data['_id'])})
        else:
            if db.get(data['_id'])['_rev'] != data['_rev']:
                return dumps({"results": False, 'message': 'revision clash'})

        new_version = mccm(json_input=data)

        if not new_version.get_attribute('prepid') and not new_version.get_attribute('_id'):
            self.logger.error('Prepid returned was None')
            raise ValueError('Prepid returned was None')

        ## operate a check on whether it can be changed
        previous_version = mccm(db.get(new_version.get_attribute('prepid')))
        editable = previous_version.get_editable()
        for (key, right) in editable.items():
            # does not need to inspect the ones that can be edited
            if right: continue
            if previous_version.get_attribute(key) != new_version.get_attribute(key):
                self.logger.error('Illegal change of parameter, %s: %s vs %s : %s' % (
                    key, previous_version.get_attribute(key), new_version.get_attribute(key), right))
                return dumps({"results": False, 'message': 'Illegal change of parameter %s' % key})

        self.logger.log('Updating mccm %s...' % (new_version.get_attribute('prepid')))


        # update history
        new_version.update_history({'action': 'update'})
        return dumps({"results": db.update(new_version.json())})



class CreateMccm(RESTResource):
    def __init__(self):
        self.access_limit = 1

    def PUT(self):
        """
        Create the mccm with the provided json content
        """
        try:
            mccm_d = mccm(loads(cherrypy.request.body.read().strip()))
        except Exception as e:
            self.logger.error(mccm_d.json())
            self.logger.error("Something went wrong with loading the mccm data:\n {0}".format(e))
            return dumps({"results": False, "message": "Something went wrong with loading the mccm data:\n {0}".format(e)})

        if not mccm_d.get_attribute('prepid'):
            self.logger.error('Non-existent prepid')
            return dumps({"results": False, "message": "The mccm ticket has no id!"})
        db = database('mccms')
        if mccm_d.get_attribute('prepid') == mccm_d.get_attribute('pwg'): # need to complete the pwg
            mccm_d.set_attribute('prepid', self.fill_id(mccm_d.get_attribute('pwg'), db))
        elif db.document_exists(mccm_d.get_attribute('prepid')):
            return dumps({"results": False, "message": "Mccm document {0} already exists".format(mccm_d.get_attribute('prepid'))})

        mccm_d.set_attribute('_id', mccm_d.get_attribute('prepid'))
        mccm_d.set_attribute('meeting', mccm.get_meeting_date().strftime("%Y-%m-%d"))
        mccm_d.update_history({'action': 'created'})
        self.logger.log('Saving mccm {0}'.format(mccm_d.get_attribute('prepid')))
        return dumps({"results": db.save(mccm_d.json()), "prepid": mccm_d.get_attribute('prepid')})


    def fill_id(self, pwg, db):
        mccm_id = pwg
        with locker.lock(mccm_id): # get date and number
            t = mccm.get_meeting_date()
            mccm_id += '-' + t.strftime("%Y%b%d") + '-' # date
            final_mccm_id = mccm_id + '00001'
            i = 2
            while db.document_exists(final_mccm_id):
                final_mccm_id = mccm_id + str(i).zfill(5)
                i += 1
            return final_mccm_id


class DeleteMccm(RESTResource):

    def DELETE(self, *args):
        if not args:
            return dumps({"results": False, "message": "No id given to delete."})
        db = database('mccms')
        return dumps({"results": db.delete(args[0])})


class GetEditableMccmFields(RESTResource):

    def __init__(self):
        self.db_name = 'mccms'

    def GET(self, *args):
        """
        Retrieve the fields that are currently editable for a given mccm
        """
        if not args:
            self.logger.error('Mccm/GetEditable: No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})
        return self.get_editable(args[0])

    def get_editable(self, prepid):
        db = database(self.db_name)
        mccm_d = mccm(db.get(prepid))
        editable = mccm_d.get_editable()
        return dumps({"results": editable})

class GenerateChains(RESTResource):
    def __init__(self):
        self.access_limit = 3
        from ActionsActions import SetAction
        self.setter = SetAction()
        

    def GET(self, *args):
        """
        Operate the chaining for a given MccM document id
        """
        if not args:
            return dumps({"results": 'Error: No arguments were given'})
        mid=args[0]
        reserve=False
        if len(args)>1:
            reserve= (args[1]=='reserve')

        return dumps(self.generate(mid, reserve))

    def generate(self, mid, reserve=False):
        mdb = database('mccms')
        mcm_m = mccm(mdb.get( mid ))

        if mcm_m.get_attribute('status')!='new':
            return {"prepid":mid,
                    "results" : False,
                    "message" : "status is %s, expecting new"%( mcm_m.get_attribute('status'))}
        if mcm_m.get_attribute('block')==0:
            return {"prepid":mid,
                    "results" : False, 
                    "message" : "No block selected"}
        if len(mcm_m.get_attribute('chains'))==0:
            return {"prepid":mid,
                    "results" : False, 
                    "message" : "No chains selected"}
        if len(mcm_m.get_attribute('requests'))==0:
            return {"prepid":mid,
                    "results" : False, 
                    "message" : "No requests selected"}
            
        aids = []
        for r in mcm_m.get_attribute('requests'):
            if type(r)==list:
                return {"prepid":mid,
                        "results" : False,
                        "message" : "range of id not supported yet"}
            else:
                aids.append( r )

        res=[]
        for aid in aids:
            for times in range(mcm_m.get_attribute('repetitions')):
                for cc in mcm_m.get_attribute('chains'):
                    res.append( {"prepid":mid,"results" : True,"message": "%s %s %s %s"%( times, aid, cc, mcm_m.get_attribute('block'))})
                    res.append(self.setter.set_action(aid, cc, mcm_m.get_attribute('block'), reserve=reserve))

        mcm_m.set_status()
        mdb.update( mcm_m.json())
        return {"prepid":mid,
                "results" : True,
                "message" : res}

class MccMReminder(RESTResource):
    def __init__(self):
        self.access_limit = 4

    def GET(self, *args):
        """
        Send a reminder to the production managers for existing opened mccm documents
        """
        mdb = database('mccms')
        mccms = mdb.queries(['status==new'])
        udb = database('users')
        
        block_threshold = 0
        if len(args):
            block_threshold = int(args[0])

        mccms = filter( lambda m : m['block'] <= block_threshold, mccms)
        mccms = sorted( mccms, key = lambda m : m['block'])
        if len(mccms)==0:
            return dumps({"results": True,"message": "nothing to remind of at level %s, %s"% (block_threshold, mccms)})

        l_type = locator()
        com = communicator()

        subject = 'Gentle reminder on tickets to be operated by you'
        message = '''\
Dear Production Managers,
 please find below the details of %s opened MccM tickets that need to be operated.

''' % (len(mccms))
        
        for mccm in mccms:
            message += 'Ticket : %s (block %s)\n'%( mccm['prepid'], mccm['block'] )
            message += ' %smccms?prepid=%s \n\n' % (l_type.baseurl(), mccm['prepid'])

        message += '\n'

        to_who = [settings().get_value('service_account')]
        to_who.extend( map( lambda u : u['email'], udb.query(query="role==production_manager", page_num=-1)))

        com.sendMail(to_who,
                     subject,
                     message)
        
        return dumps({"results" : True, "message" : map( lambda m : m['prepid'], mccms)})
    

