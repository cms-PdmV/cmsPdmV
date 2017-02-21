import cherrypy
import time

from json import dumps

from rest_api.RestAPIMethod import RESTResource
from couchdb_layer.mcm_database import database
from json_layer.mccm import mccm
from json_layer.user import user
from tools.locker import locker
from tools.locator import locator
from tools.communicator import communicator
from tools.settings import settings
from tools.user_management import access_rights
from tools.json import threaded_loads

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
        except Exception as ex:
            self.logger.error('Failed to update an mccm from API. Reason: %s' % (str(ex)))
            return dumps({'results': False, 'message': 'Failed to update an mccm from API. Reason: %s' % (
                    str(ex))})

    def update(self, body):
        data = threaded_loads(body)
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
                        key, previous_version.get_attribute(key),
                        new_version.get_attribute(key), right))

                return {"results": False, 'message': 'Illegal change of parameter %s' % key}

        self.logger.info('Updating mccm %s...' % (new_version.get_attribute('prepid')))


        # update history
        new_version.update_history({'action': 'update'})
        return {"results": db.update(new_version.json())}



class CreateMccm(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.generator_contact
        sdb = database('settings')
        self.possible_pwgs = sdb.get("pwg")["value"]

    def PUT(self):
        """
        Create the mccm with the provided json content
        """
        try:
            mccm_d = mccm(threaded_loads(cherrypy.request.body.read().strip()))
        except Exception as e:
            self.logger.error(mccm_d.json())
            self.logger.error("Something went wrong with loading the mccm data:\n {0}".format(
                    e))

            return dumps({"results": False,
                    "message": "Something went wrong with loading the mccm data:\n {0}".format(
                            e)})

        if not mccm_d.get_attribute('prepid'):
            self.logger.error('Non-existent prepid')
            return dumps({"results": False, "message": "The mccm ticket has no id!"})

        if mccm_d.get_attribute("pwg") not in self.possible_pwgs:
            self.logger.error('Trying to create Mccm with non-existant PWG: %s' % (
                    mccm_d.get_attribute("pwg")))

            return dumps({"results": False,
                    "message": "The mccm ticket has non-existant PWG!"})

        db = database('mccms')
        # need to complete the prepid
        if mccm_d.get_attribute('prepid') == mccm_d.get_attribute('pwg'):
            mccm_d.set_attribute('prepid', self.fill_id(mccm_d.get_attribute('pwg'), db))
        elif db.document_exists(mccm_d.get_attribute('prepid')):
            return dumps({"results": False,
                    "message": "Mccm document {0} already exists".format(
                            mccm_d.get_attribute('prepid'))})

        mccm_d.set_attribute('_id', mccm_d.get_attribute('prepid'))
        mccm_d.set_attribute('meeting', mccm.get_meeting_date().strftime("%Y-%m-%d"))
        mccm_d.update_history({'action': 'created'})
        self.logger.info('Saving mccm {0}'.format(mccm_d.get_attribute('prepid')))

        return dumps({"results": db.save(mccm_d.json()),
                "prepid": mccm_d.get_attribute('prepid')})


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

class CancelMccm(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.generator_contact

    def GET(self,  *args):
        """
        Cancel the MccM ticket provided in argument. Does not delete it but put the status as cancelled.
        """
        if not args:
            return dumps({"results": False, "message": "No id given to cancel."})

        db = database('mccms')
        udb = database('users')

        mcm_mccm = mccm(db.get(args[0]))
        curr_user = user(udb.get(mcm_mccm.current_user))

        self.logger.info("Canceling an mccm: %s" % (args[0]))

        if mcm_mccm.get_attribute('status') == 'done':
            self.logger.info("You cannot cancel 'done' mccm ticket")
            return dumps({"results": False, "message": "Cannot cancel done tickets"})

        if not mcm_mccm.get_attribute("pwg") in curr_user.get_pwgs():
            self.logger.info("User's PWGs: %s doesnt include ticket's PWG: %s" % (
                    curr_user.get_pwgs(), mcm_mccm.get_attribute("pwg")))

            return dumps({"results": False, "message": "You cannot cancel ticket with different PWG than yours"})

        mcm_mccm.set_attribute('status','cancelled')
        mcm_mccm.update_history({'action': 'cancelled'})
        saved = db.update(mcm_mccm.json())
        if saved:
            return dumps({"results": True})
        else:
            return dumps({"results": False, "message": "Could not save the ticket to be cancelled."})

class DeleteMccm(RESTResource):

    def DELETE(self, *args):
        if not args:
            return dumps({"results": False, "message": "No id given to delete."})
        db = database('mccms')
        mcm_mccm = db.get( args[0] )
        if mcm_mccm['status'] == 'done':
            return dumps({"results": False, "message" : "Cannot delete a ticket that is done"})
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
        mid = args[0]
        reserve = False
        if len(args) > 1:
            reserve = (args[1]=='reserve')
            if len(args) > 2:
                reserve = args[2]

        lock = locker.lock(mid)
        if lock.acquire(blocking=False):
            try:
                res= self.generate(mid, reserve)
            finally:
                lock.release()
            return dumps(res)
        else:
            return dumps({"results" : False,
                    "message" : "%s is already being operated on" % mid})

    def generate(self, mid, reserve=False):
        mdb = database('mccms')
        rdb = database('requests')

        mcm_m = mccm(mdb.get(mid))

        if mcm_m.get_attribute('status')!='new':
            return {"prepid" : mid,
                    "results" : False,
                    "message" : "status is %s, expecting new" % (
                            mcm_m.get_attribute('status'))}

        if mcm_m.get_attribute('block') == 0:
            return {"prepid" : mid,
                    "results" : False,
                    "message" : "No block selected"}

        if len(mcm_m.get_attribute('chains')) == 0:
            return {"prepid" : mid,
                    "results" : False,
                    "message" : "No chains selected"}

        if len(mcm_m.get_attribute('requests')) == 0:
            return {"prepid" : mid,
                    "results" : False,
                    "message" : "No requests selected"}

        aids = []
        for r in mcm_m.get_attribute('requests'):
            if type(r) == list:
                if len(r) > 2:
                    return {"prepid" : mid,
                            "results" : False,
                            "message" : "range of id too large"}

                (pwg1, campaign1, serial1) = r[0].split('-')
                (pwg2, campaign2, serial2) = r[1].split('-')
                serial1 = int(serial1)
                serial2 = int(serial2)
                if pwg1 != pwg2 or campaign1 != campaign2:
                    return {"prepid" : mid,
                            "results" : False,
                            "message" : "inconsistent range of ids %s -> %s" % (r[0], r[1])}

                aids.extend(map(lambda s : "%s-%s-%05d" % (pwg1, campaign1, s),
                        range(serial1, serial2+1)))

            else:
                aids.append(r)

        if len(aids) != len(list(set(aids))):
            return {"prepid" : mid,
                    "results" : False,
                    "message" : "There are duplicate actions in the ticket"}

        ccdb = database('chained_campaigns')
        ccs = []
        for cc in mcm_m.get_attribute('chains'):
            if cc.startswith('chain'):
                __query = ccdb.construct_lucene_query({'prepid' : cc})
            else:
                __query = ccdb.construct_lucene_query({'alias' : cc})
            ccs.extend(ccdb.full_text_search('search', __query, page=-1))
        ## collect the name of the campaigns it can belong to
        ccs = list(set(map(lambda cc : cc['campaigns'][0][0], ccs)))
        if len(ccs)!=1:
            return {"prepid":mid,
                    "results" : False,
                    "message" : "inconsistent list of chains %s, leading to different root campaigns %s" % (mcm_m.get_attribute('chains'), ccs)}

        allowed_campaign = ccs[0]
        for aid in aids:
            mcm_r = rdb.get(aid)
            if mcm_r['member_of_campaign'] != allowed_campaign:
                return {"prepid" : mid,
                        "results" : False,
                        "message" : "A request (%s) is not from the allowed root campaign %s" % (aid, allowed_campaign)}

            if mcm_r['status'] == 'new' and mcm_r['approval'] == 'validation':
                return {"prepid" : mid,
                        "results" : False,
                        "message" : "A request (%s) is being validated." % (aid)}

            if mcm_r['flown_with']:
                return {"prepid" : mid,
                        "results" : False,
                        "message" : "A request (%s) is in the middle of a chain already." % (aid)}

        if not mcm_m.get_attribute('repetitions'):
            return {"prepid" : mid,
                    "results" : False,
                    "message" : "The number of repetitions (%s) is invalid" % (
                            mcm_m.get_attribute('repetitions'))}

        res = []
        for aid in aids:
            for times in range(mcm_m.get_attribute('repetitions')):
                for cc in mcm_m.get_attribute('chains'):
                    b = mcm_m.get_attribute('block')
                    s = None
                    t = None
                    special = mcm_m.get_attribute('special')
                    if mcm_m.get_attribute('staged') != 0:
                        s = mcm_m.get_attribute('staged')
                    if mcm_m.get_attribute('threshold') != 0:
                        t = mcm_m.get_attribute('threshold')

                    res.append(self.setter.set_action(aid,
                            cc, b, staged=s, threshold=t, reserve=reserve, special=special))

                    ##for now we put a small delay to not crash index with a lot of action
                    time.sleep(2)

        generated_chains = {}
        for el in res:
            if not el['results']:
                return {
                    "prepid" : mid,
                    "results" : False,
                    "message" : el['message'],
                    'chained_request_prepid': el['prepid']
                }        
            for chain, requests in el["generated_chains"].iteritems():
                generated_chains[chain] = requests
        self.logger.debug("just generated chains: %s" % (generated_chains))
        mcm_m.set_attribute("generated_chains", generated_chains)
        mcm_m.set_status()
        mdb.update(mcm_m.json())
        return {"prepid" : mid,
                "results" : True,
                "message" : res}

class MccMReminderGenContacts(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator
        self._cp_config = {'response.stream': True}

    def GET(self, *args):
        """
        Send a reminder to all generator contacts that have tickets with status equal to new
        """
        mccms_db = database('mccms')
        users_db = database('users')
        __query = mccms_db.construct_lucene_query({'status' : 'new'})
        mccms_tickets = mccms_db.full_text_search('search', __query, page=0, limit=1)
        non_gen_contact_authors = set()
        authors_tickets_dict = dict()
        for ticket in mccms_tickets:
            yield '\nProcessing ticket %s' % (ticket['prepid'])
            authors_history = set() #set to avoid the processing of one author more than one time 
            for author in ticket['history']:
                author_email = author['updater']['author_email']
                if author_email in authors_history:
                    continue
                if author_email in authors_tickets_dict:
                    author_tickets_dict[author_email].append(ticket['prepid'])
                elif author_email not in non_gen_contact_authors:
                    __role_query = users_db.construct_lucene_query({'email' : author_email})
                    result = users_db.full_text_search('search', __role_query, page=-1, include_fields='role')
                    time.sleep(0.5) #we don't want to crash DB with a lot of single queries
                    if result and result[0]['role'] == 'generator_contact':
                        authors_tickets_dict[author_email] = [ticket['prepid']]
                    else:
                        non_gen_contact_authors.add(author_email)
                authors_history.add(author_email)
                yield '.'
        subject_part1 = 'Gentle reminder on %s '
        subject_part2 = ' to be operated by you'
        message_part1 = 'Dear GEN Contact, \nPlease find below the details of %s MccM '
        message_part2 = ' in status "new". Please present them in next MccM googledoc or cancel tickets if these are not needed anymore.\n\n'
        base_url = locator().baseurl()
        mail_communicator = communicator()
        for author_email, ticket_prepids in authors_tickets_dict.iteritems():
            num_tickets = len(ticket_prepids)
            full_message = (message_part1 % (num_tickets)) + ('ticket' if num_tickets == 1 else 'tickets') + message_part2
            for ticket_prepid in ticket_prepids:
                full_message += 'Ticket: %s \n' % (ticket_prepid)
                full_message += '%smccms?prepid=%s \n\n' % (base_url, ticket_prepid)
                yield '.'
            full_message += '\n'
            subject = (subject_part1 % (num_tickets)) + ('ticket' if num_tickets == 1 else 'tickets') + subject_part2
            mail_communicator.sendMail([author_email], subject, full_message)
            yield '\nEmail sent to %s\n' % (author_email)


class MccMReminderProdManagers(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.administrator

    def GET(self, *args):
        """
        Send a reminder to the production managers for existing opened mccm documents
        """
        mdb = database('mccms')
        udb = database('users')

        __query = mdb.construct_lucene_query({'status' : 'new'})
        mccms = mdb.full_text_search('search', __query, page=-1)

        block_threshold = 0
        if len(args):
            block_threshold = int(args[0])

        mccms = filter( lambda m : m['block'] <= block_threshold, mccms)
        mccms = sorted( mccms, key = lambda m : m['block'])
        if len(mccms)==0:
            return dumps({"results": True,"message": "nothing to remind of at level %s, %s"% (block_threshold, mccms)})

        l_type = locator()
        com = communicator()

        subject = 'Gentle reminder on %s tickets to be operated by you' % ( len( mccms)) 
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
        mdb = database('mccms')
        date = args[0]
        pwgs=None

        if len(args)>1:
            pwgs=args[1].split(',')

        to_be_shown= ['prepid','notes','deadline','requests','chains','repetitions']
        l_type=locator()

        __query = mdb.construct_lucene_query({'meeting' : date})
        mdocs = mdb.full_text_search('search', __query, page=-1)
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
