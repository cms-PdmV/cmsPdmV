import smtplib
import os
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from tools.locator import locator

class communicator:
    def __init__(self):
        self.from_opt='user' # could be service at some point

    def sendMail(self,
                 destination,
                 subject,
                 text,
                 sender):

        if type(destination)!=list:
            print "Cannot send email. destination should be a list of strings"
            return
        

        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = COMMASPACE.join(destination)
        msg['Date'] = formatdate(localtime=True)
        if locator().isDev():
            msg['Subject'] ='[McM-dev] '+subject
        else:
            msg['Subject'] ='[McM] '+subject
        try:
            msg.attach(MIMEText(text))
            smtpObj = smtplib.SMTP()
            smtpObj.connect()
            smtpObj.sendmail(sender, destination, msg.as_string())
            smtpObj.quit()
        except Exception as e:
            print "Error: unable to send email", e.__class__


