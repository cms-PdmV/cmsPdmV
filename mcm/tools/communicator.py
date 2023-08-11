import smtplib
import logging

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email.utils import make_msgid
from tools.locator import locator
import tools.settings as settings
from tools.locker import locker


class communicator:
    cache = {}
    logger = logging.getLogger("mcm_error")

    def __init__(self):
        self.from_opt = 'user'  # could be service at some point

    def flush(self, Nmin):
        res = []
        with locker.lock('accumulating_notifcations'):
            for key in self.cache.keys():
                (subject, sender, addressee) = key
                if self.cache[key]['N'] <= Nmin:
                    # flush only above a certain amount of messages
                    continue
                destination = addressee.split(COMMASPACE)
                text = self.cache[key]['Text']
                msg = MIMEMultipart()
                msg['From'] = sender
                msg['To'] = addressee
                msg['Cc'] = 'pdmvserv@cern.ch'
                msg['Date'] = formatdate(localtime=True)
                new_msg_ID = make_msgid()
                msg['Message-ID'] = new_msg_ID
                msg['Subject'] = subject
                # add a signature automatically
                text += '\n\n'
                text += 'McM Announcing service'
                # self.logger.info('Sending a message from cache \n%s'% (text))
                try:
                    msg.attach(MIMEText(text))
                    smtpObj = smtplib.SMTP()
                    smtpObj.connect()
                    smtpObj.sendmail(sender, destination, msg.as_string())
                    smtpObj.quit()
                    self.cache.pop(key)
                    res.append(subject)
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
        # it could happen that message are send after forking, threading and there's no current user anymore
        msg['From'] = sender if sender else 'PdmV Service Account <pdmvserv@cern.ch>'

        # add a mark on the subjcet automatically
        if locator().isDev():
            msg['Subject'] = '[McM-dev] ' + subject
            destination = ["pdmvserv@cern.ch"]  # if -dev send only to service account and sender
            if sender:
                destination.append(sender)
        else:
            msg['Subject'] = '[McM] ' + subject

        msg['To'] = COMMASPACE.join(destination)
        msg['Date'] = formatdate(localtime=True)
        destination.append('pdmvserv@cern.ch')
        msg['Cc'] = 'pdmvserv@cern.ch'
        new_msg_ID = make_msgid()
        msg['Message-ID'] = new_msg_ID

        if reply_msg_ID is not None:
            msg['In-Reply-To'] = reply_msg_ID
            msg['References'] = reply_msg_ID

        # accumulate messages prior to sending emails
        com__accumulate = settings.get_value('com_accumulate')
        force_com_accumulate = settings.get_value('force_com_accumulate')
        if force_com_accumulate or (accumulate and com__accumulate):
            with locker.lock('accumulating_notifcations'):
                # get a subject where the request name is taken out
                subject_type = " ".join(filter(lambda w: w.count('-') != 2, msg['Subject'].split()))
                addressees = msg['To']
                sendee = msg['From']
                key = (subject_type, sendee, addressees)
                if key in self.cache:
                    self.cache[key]['Text'] += '\n\n'
                    self.cache[key]['Text'] += text
                    self.cache[key]['N'] += 1
                else:
                    self.cache[key] = {'Text': text, 'N': 1}
                # self.logger.info('Got a message in cache %s'% (self.cache.keys()))
                return new_msg_ID


        # add a signature automatically
        text += '\n\n'
        text += 'McM Announcing service'

        try:
            msg.attach(MIMEText(text))
            smtpObj = smtplib.SMTP(host="cernmx.cern.ch", port=25)
            smtpObj.connect()
            communicator.logger.info('Sending %s to %s...' % (msg['Subject'], msg['To']))
            smtpObj.sendmail(sender, destination, msg.as_string())
            smtpObj.quit()
            return new_msg_ID
        except Exception as e:
            communicator.logger.error("Error: unable to send email %s", e)
