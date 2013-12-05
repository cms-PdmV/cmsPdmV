import smtplib
import os
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email.utils import make_msgid
from tools.locator import locator


class communicator:
    def __init__(self):
        self.from_opt = 'user' # could be service at some point

    def sendMail(self,
                 destination,
                 subject,
                 text,
                 sender=None,
                 reply_msg_ID=None):

        if not isinstance(destination, list):
            print "Cannot send email. destination should be a list of strings"
            return

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

        ## add a signature automatically
        text += '\n'
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


