#!/usr/bin/env python3
# coding: utf-8
import requests
from logging.handlers import SMTPHandler

class mimetypeSMTPHandler(SMTPHandler):
    def set_mimetype(self, mimetype):
        self.mimetype = mimetype

    def emit(self, record):
        """
        Emit a record.
        Format the record and send it to the specified addressees.
        """
        try:
            import smtplib
            from email.header import Header
            from email.utils import formatdate
            from email.mime.text import MIMEText

            port = self.mailport
            if not port:
                port = smtplib.SMTP_PORT

            try:
                minetype = self.mimetype
            except AttributeError:
                minetype = 'plain'

            smtp = smtplib.SMTP(self.mailhost, port, timeout=self.timeout)
            msg = self.format(record)
            msg = MIMEText(msg, minetype, 'utf-8')
            msg['From'] = self.fromaddr
            msg['To'] = ','.join(self.toaddrs)
            msg['Subject'] = Header(self.getSubject(record), 'utf-8')
            msg['Date'] = formatdate()
            if self.username:
                if self.secure is not None:
                    smtp.ehlo()
                    smtp.starttls(*self.secure)
                    smtp.ehlo()
                smtp.login(self.username, self.password)
            smtp.sendmail(self.fromaddr, self.toaddrs, msg.as_string())
            smtp.quit()
        except Exception:
            self.handleError(record)

class PushBear(object):
    API = 'https://pushbear.ftqq.com/sub'
    def __init__(self, sendkey, timeout=30):
        self.params = {
        'sendkey': sendkey,
        'text': '',
        'desp': '',
        }
        self.timeout = timeout

    def send(self, title, content=''):
        self.params['text'] = title
        self.params['desp'] = content
        return requests.get(self.API, params=self.params, timeout=self.timeout)

class SC(object):
    def __init__(self, sendkey, timeout=30):
        self.params = {
        'text': '',
        'desp': '',
        }
        self.timeout = timeout
        self.url = "https://sc.ftqq.com/{}.send".format(sendkey) 

    def send(self, title, content=''):
        self.params['text'] = title
        self.params['desp'] = content
        return requests.get(self.url, params=self.params, timeout=self.timeout)