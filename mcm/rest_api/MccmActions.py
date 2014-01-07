from rest_api.RestAPIMethod import RESTResource
from json import dumps, loads
from couchdb_layer.mcm_database import database
from json_layer.mccm import mccm
from tools.locker import locker
from tools.locator import locator
from tools.communicator import communicator
from tools.settings import settings
from tools.user_management import access_rights

import cherrypy


class GetMccm(RESTResource):

    def GET(self, *args):
        """
        Retreive the dictionnary for a given mccm
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": {}})
        return dumps(self.get_doc(args[0]))

    def get_doc(self, data):
        db = database('mccms')
        if not db.document_exists(data):
            return {"results": {}}
        mccm_doc = db.get(prepid=data)

        return {"results": mccm_doc}


class UpdateMccm(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.generator_contact

    def PUT(self):
        """
        Updating an existing mccm with an updated dictionary
        """
        try:
            return dumps(self.update(cherrypy.request.body.read().strip()))
        except:
            self.logger.error('Failed to update an mccm from API')
            return dumps({'results': False, 'message': 'Failed to update an mccm from API'})

    def update(self, body):
        data = loads(body)
        if '_rev' not in data:
            self.logger.error('Could not locate the CouchDB revision number in object: %s' % data)
            return {"results": False, 'message': 'could not locate revision number in the object'}
        db = database('mccms')
        if not db.document_exists(data['_id']):
            return {"results": False, 'message': 'mccm %s does not exist' % ( data['_id'])}
        else:
            if db.get(data['_id'])['_rev'] != data['_rev']:
                return {"results": False, 'message': 'revision clash'}

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
                return {"results": False, 'message': 'Illegal change of parameter %s' % key}

        self.logger.log('Updating mccm %s...' % (new_version.get_attribute('prepid')))


        # update history
        new_version.update_history({'action': 'update'})
        return {"results": db.update(new_version.json())}



class CreateMccm(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.generator_contact

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
        return dumps(self.get_editable(args[0]))

    def get_editable(self, prepid):
        db = database(self.db_name)
        mccm_d = mccm(db.get(prepid))
        editable = mccm_d.get_editable()
        return {"results": editable}


class GenerateChains(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.production_manager
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

        lock = locker.lock(mid)
        if lock.acquire(blocking=False):       
            res= self.generate(mid, reserve)
            lock.release()
            return dumps(res)
        else:
            return dumps({"results" : False, "message" : "%s is already being operated on"% mid} )

    def generate(self, mid, reserve=False):
        mdb = database('mccms')
        rdb = database('requests')

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
                if len(r) >2:
                    return {"prepid":mid,
                            "results" : False,
                            "message" : "range of id too large"}

                (pwg1, campaign1, serial1) = r[0].split('-')
                (pwg2, campaign2, serial2) = r[1].split('-')
                serial1=int(serial1)
                serial2=int(serial2)
                if pwg1!=pwg2 or campaign1!=campaign2:
                    return {"prepid":mid,
                            "results" : False,
                            "message" : "inconsistent range of ids %s -> %s" %(r[0],r[1])}
                
                aids.extend( map( lambda s : "%s-%s-%05d"%( pwg1, campaign1, s), range( serial1, serial2+1)))
            else:
                aids.append( r )

        res=[]
        for aid in aids:
            mcm_r = rdb.get(aid)
            if mcm_r['status']=='new' and mcm_r['approval']=='validation':
                return {"prepid":mid,
                        "results" : False, 
                        "message" : "A request (%s) is being validated" %( aid) }

            for times in range(mcm_m.get_attribute('repetitions')):
                for cc in mcm_m.get_attribute('chains'):
                    b=mcm_m.get_attribute('block')
                    s=None
                    t=None
                    if mcm_m.get_attribute('staged')!=0:
                        s= mcm_m.get_attribute('staged')
                    if mcm_m.get_attribute('threshold')!=0:
                        t=mcm_m.get_attribute('threshold')
                    
                    res.append( {"prepid":mid,"results" : True,"message": "%s x %s in %s block %s s %s t %s"%( times, aid, cc, b, s ,t )})
                    res.append(self.setter.set_action(aid, cc, b, staged=s, threshold=t, reserve=reserve))

        mcm_m.set_status()
        mdb.update( mcm_m.json())
        return {"prepid":mid,
                "results" : True,
                "message" : res}


class MccMReminder(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

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
    

class MccMDisplay(RESTResource):
    def __init__(self):
        pass

    def GET(self, *args):
        """
        Twiki display of mccm ticket for a given meeting date and /pwg optional
        """
        
        date = args[0]
        pwgs=None
        if len(args)>1:
            pwgs=args[1].split(',')

        mdb = database('mccms')

        to_be_shown= ['prepid','notes','deadline','requests','chains','repetitions']
        l_type=locator()        
        mdocs= mdb.queries(['meeting==%s'% date])
        if pwgs:
            text="---++ MccM Tickets for %s : %s \n"%( date, ', '.join(pwgs) )
            for pwg in pwgs:
                mdocs_pwg = filter ( lambda m : m['pwg']==pwg, mdocs)
                text+="---+++ Tickets for %s \n" %pwg
                text+="[[%smccms?meeting=%s&pwg=%s][link to McM]]\n"%( l_type.baseurl(), date, pwg)
                for t in mdocs_pwg:
                    text+="   * "
                    for item in to_be_shown:
                        if item in t:
                            text+="%s "% t[item]
                    text+='\n'
        else:
            text="---++ MccM Tickets for %s \n<br>"%( date )
            text+="[[%smccms?meeting=%s][link to McM]]\n"%( l_type.baseurl(), date )
            for t in mdocs:
                text+="   * "
                for item in to_be_shown:   
                    if item in t:
                        text+="%s "% t[item]       
                text+='\n'

        return text

        
        

