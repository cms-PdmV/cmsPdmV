"""
Module that contains email communicator class

"""
import logging
import random
import smtplib
import time
from email.message import Message
from email.utils import formatdate
from tools.config_manager import Config
from tools.locator import locator
from tools.locker import locker
from tools.utils import clean_split


class Communicator:
    cache = {}
    logger = logging.getLogger('mcm_error')
    greetings = ('Hi', 'Hello', 'Greetings', 'Hey')
    signatures = ('Sincerely', 'Regards', 'Best regards', 'Yours truly', 'Cheers', 'With love')

    def send_mail(self, recipients, subject, body, sender=None):
        """
        Send email to recipients with given subject and body
        Optionally change sender
        """
        if not isinstance(recipients, list):
            recipients = clean_split(recipients)

        # Make recipients
        service_email = Config.get('service_email')
        cc = [service_email]
        sender = sender if sender else service_email
        # Change subject and recipients based on environment
        if locator().isDev():
            subject = '[McM-DEV] ' + subject
            recipients = [service_email]
        else:
            subject = '[McM] ' + subject
            # Lowercase and remove pdmvserv account as it will go to CC
            recipients = [r.lower() for r in recipients if not r.startswith('pdmv')]
            # Sort and make recipients unique
            recipients = sorted(list(set(recipients)))

        if not recipients:
            self.logger.warning('Email %s has no recipients', subject)
            return

        # Make a message
        message = Message()
        message['Subject'] = subject
        message['From'] = sender
        message['To'] = ', '.join(recipients)
        message['Date'] = formatdate(localtime=True)
        message['Cc'] = ', '.join(cc)
        # Random greeting and signature
        greeting = random.choice(self.greetings)
        signature = random.choice(self.signatures)
        body = '%s,\n\n%s\n\n%s,\nMcM' % (greeting, body.strip(), signature)
        message.set_payload(body)
        # For a good measure, send only one email at a time
        with locker.lock('send_email'):
            # Send the message via our own SMTP server.
            smtp = smtplib.SMTP()
            smtp.connect()
            self.logger.debug('Sending...:\nSUBJECT: %s\nTO: %s\nFROM: %s\nCC: %s\n %s',
                            message['Subject'],
                            message['To'],
                            message['From'],
                            message['Cc'],
                            body)
            smtp.sendmail(sender, recipients + cc, message.as_string())
            smtp.quit()
            # Wait before sending next one
            time.sleep(1)
