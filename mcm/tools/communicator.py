import smtplib
import os
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email.utils import make_msgid
from tools.locator import locator
from tools.logger import logfactory
from collections import defaultdict
from tools.settings import settings
from tools.locker import locker
class communicator:
    cache = {}
    logger = logfactory 

    def __init__(self):
        self.from_opt = 'user' # could be service at some point

    def flush(self,Nmin):
        res=[]
        with locker.lock('accumulating_notifcations'):
            for key in self.cache.keys():
                (subject,addressee,sender)=key
                if self.cache[key]['N'] <= Nmin: 
                    ## flush only above a certain amount of messages
                    continue
                destination = addressee.split(COMMASPACE)
                text = self.cache[key]['Text']
                msg = MIMEMultipart()
                
                msg['From'] = sender
                msg['To'] = addressee
                msg['Date'] = formatdate(localtime=True)
                new_msg_ID = make_msgid()  
                msg['Message-ID'] = new_msg_ID 
                msg['Subject'] = subject
                
                ## add a signature automatically
                text += '\n\n'
                text += 'McM Announcing service'
                #self.logger.log('Sending a message from cache \n%s'% (text))
                try:
                    msg.attach(MIMEText(text))
                    smtpObj = smtplib.SMTP()
                    smtpObj.connect()
                    smtpObj.sendmail(sender, destination, msg.as_string())
                    smtpObj.quit()
                    self.cache.pop(key)
                    res.append( subject )
                except Exception as e:
                    print "Error: unable to send email", e.__class__
            return res

    def sendMail(self,
                 destination,
                 subject,
                 text,
                 sender=None,
                 reply_msg_ID=None,
                 accumulate=False):

        if not isinstance(destination, list):
            print "Cannot send email. destination should be a list of strings"
            return

        destination.sort()
        msg = MIMEMultipart()
        #it could happen that message are send after forking, threading and there's no current user anymore
        msg['From'] = sender if sender else 'pdmvserv@cern.ch'
        msg['To'] = COMMASPACE.join(destination)
        msg['Date'] = formatdate(localtime=True)
        new_msg_ID = make_msgid()
        msg['Message-ID'] = new_msg_ID
        
        if reply_msg_ID != None:
            msg['In-Reply-To'] = reply_msg_ID
            msg['References'] = reply_msg_ID

        ## add a mark on the subjcet automatically
        if locator().isDev():
            msg['Subject'] = '[McM-dev] ' + subject
        else:
            msg['Subject'] = '[McM] ' + subject

        ### accumulate messages prior to sending emails
        com__accumulate=settings().get_value('com_accumulate')
        if accumulate or com__accumulate:
            with locker.lock('accumulating_notifcations'):
                # get a subject where the request name is taken out
                subject_type=" ".join( filter(lambda w : w.count('-')!=2, msg['Subject'].split()) )
                addressees = msg['To']
                sendee = msg['From']
                key = (subject_type, sendee, addressees)
                if key in self.cache:
                    self.cache[key]['Text']+='\n'
                    self.cache[key]['Text']+=text
                    self.cache[key]['N']+=1
                else:
                    self.cache[key] = {'Text' : text, 'N':1}
                #self.logger.log('Got a message in cache %s'% (self.cache.keys()))
                return new_msg_ID


        ## add a signature automatically
        text += '\n\n'
        text += 'McM Announcing service'

        try:
            msg.attach(MIMEText(text))
            smtpObj = smtplib.SMTP()
            smtpObj.connect()
            smtpObj.sendmail(sender, destination, msg.as_string())
            smtpObj.quit()
            return new_msg_ID
        except Exception as e:
            print "Error: unable to send email", e.__class__


    
