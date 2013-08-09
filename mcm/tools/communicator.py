import smtplib
import os
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from tools.locator import locator


class communicator:
    def __init__(self):
        self.from_opt = 'user' # could be service at some point

    def sendMail(self,
                 destination,
                 subject,
                 text,
                 sender=None):

        if isinstance(destination, list):
            print "Cannot send email. destination should be a list of strings"
            return

        msg = MIMEMultipart()
        #it could happen that message are send after forking, threading and there's no current user anymore
        msg['From'] = sender if sender else 'pdmvserv@cern.ch'
        msg['To'] = COMMASPACE.join(destination)
        msg['Date'] = formatdate(localtime=True)

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
        except Exception as e:
            print "Error: unable to send email", e.__class__


