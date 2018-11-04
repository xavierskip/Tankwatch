#!/usr/bin/env python3
# coding: utf-8
import re
import os
import json
import logging
import requests
import argparse
from ruamel.yaml import YAML
from logging.handlers import SMTPHandler
from datetime import datetime, timedelta
from requests.exceptions import ReadTimeout, ConnectionError


parser = argparse.ArgumentParser()
parser.add_argument("--config", help="your config file")
args = parser.parse_args()
if args.config:
    config_file = args.config
else:
    config_file = 'config.yaml'

# use absolute path to run in corntab for easy
HERE = os.path.dirname(os.path.abspath(__file__))
if not os.path.isabs(config_file):
    config_file = os.path.join(HERE, config_file)

yaml=YAML(typ='safe')
with open(config_file) as f:
    CONFIG = yaml.load(f)

if not os.path.isabs(CONFIG['logfile']):
    CONFIG['logfile'] = os.path.join(HERE, CONFIG['logfile'])

def datetime_from_to(**kwargs):
    date_to = datetime.now()
    date_from = date_to - timedelta(**kwargs)
    fmt = "%Y-%m-%d %H:%M:%S"
    return date_from.strftime(fmt),  date_to.strftime(fmt)

def path(path):
    def decorate(func):
        def wrapper(self, *args, **kwargs):
            self.url = self.host+path
            return func(self, *args, **kwargs)
        return wrapper
    return decorate

class Crawl(object):
    """docstring for Crawl"""
    host = ""
    def __init__(self):
        self.url = self.host
        self.session = requests.Session()

    @path('/hello')
    def hello(self):
        print('crawling', self.url)

class Tank(Crawl):
    host = CONFIG['host']

    @path('/')
    def ping(self):
        return self.session.get(self.url)

    @path('/Default.aspx')
    def login(self, user, passwd):
        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": "/wEPDwUKLTQxOTI5ODg5NWQYAQUeX19Db250cm9sc1JlcXVpcmVQb3N0QmFja0tleV9fFgMFDlNjcmlwdE1hbmFnZXIxBQhidG5Mb2dpbgUJYnRuQ2FuY2VsXmUt6A99X2CtoixT/rQZhXiO+9U=",
            "__VIEWSTATEGENERATOR": "CA0B0334",
            "__EVENTVALIDATION": "/wEWBgK6yrf3CwLB5eCpDQKl1bK4CQLKw6LdBQKC3IeGDAKQ9M/rBYwJEawUQF3XZczcLewoomOjQ7Fx",
            "txtUsername": user,
            "txtPass": passwd,
            "btnLogin.x": 0,
            "btnLogin.y": 0
        }
        r = self.session.post(self.url, data=payload, timeout=30)
        return r

    @path('/Pages/FailManage/FailInfoList.aspx')
    def failinfo(self, from_date, to_date):
        dateFieldFrom, timeFieldFrom_Value = from_date.split(' ')
        dateFieldTo, timeFieldTo_Value = to_date.split(' ')
        # print(dateFieldFrom, timeFieldFrom_Value, dateFieldTo, timeFieldTo_Value)
        headers = {'X-Ext.Net': 'delta=true'}
        payload = {
            'submitDirectEventConfig': '{"config":{"extraParams":{"start":0,"limit":100}}}',
            'dateFieldFrom': dateFieldFrom,
            'timeFieldFrom_Value': timeFieldFrom_Value,
            'timeFieldFrom_SelIndex': 0,
            'dateFieldTo': dateFieldTo,
            'timeFieldTo_Value': timeFieldTo_Value,
            'timeFieldTo_SelIndex': -1,
            'combFaultType_Value': 0,
            'combFaultType': '全部',
            'combFaultType_SelIndex': 0,
            'combFAlarmState_Value': 0,
            'combFAlarmState': '未处理',
            'combFAlarmState_SelIndex': 1,
            'PagingToolBar1_ActivePage': 1,
            '__EVENTTARGET': 'ScriptManager1',
            '__EVENTARGUMENT': 'storeFailList|postback|refresh',
        }
        return self.session.post(self.url, headers=headers, data=payload, timeout=30)

    def get_failinfo_json(self, from_date, to_date):
        r = self.failinfo(from_date, to_date)
        # print(r.text)
        prog = re.compile('data:(\[.+\])')
        result = prog.search(r.text)
        if result:
            return json.loads(result.group(1))
        else:
            return None

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
        return requests.get(self.API, params=self.params, timeout=30)

def main():
    tank = Tank()
    tank.login(CONFIG['username'],CONFIG['password'])
    fd, td = datetime_from_to(**CONFIG['timedelta'])
    data = tank.get_failinfo_json(fd, td)
    if data:
        text = []
        tr = []
        mdtr = []
        text_template = '\t{time} {name} {fault} {alarm}({trange}) {temp}°C'
        tr_template = '<tr><td>{time}</td><td>{name}</td><td>{fault}</td><td>{alarm}({trange})</td><td>{temp}°C</td></tr>'
        mdtr_template = '|{time}|{name}|{fault}|{alarm}({trange})|{temp}°C|'
        md_template = '|报警时间|设备名称|报警类型|报警描述|温度|\n|-|-|-|-|-|\n{}'
        for item in data:
            # print(item)
            info = {
            'time': item['WarningDateTime'].replace('T' ,' '),
            'name': item['FDevName'],
            'fault': item['FFaultTypeName'],
            'alarm': item['FAlarmValue'],
            'temp': item['FTempValue1'],
            'trange': item['fanwei'],
            }
            text.append(text_template.format(**info))
            tr.append(tr_template.format(**info))
            mdtr.append(mdtr_template.format(**info))

        logger.info('\n'.join(text))
        mail.info('<table>{}<table>'.format(''.join(tr)))

        title = "有{}条报警信息".format(len(data))
        markdown = md_template.format('\n'.join(mdtr))
        weixin.send(title, markdown)
    else:
        logger.info('NO Alarm.')
        return 0

if __name__ == '__main__':
    # for logging
    fmt = logging.Formatter(
        fmt='%(asctime)s --\n%(message)s',
        datefmt='%Y/%m/%d %H:%M:%S',
        )
    logger = logging.getLogger('tankwatch')
    logger.setLevel('DEBUG')
    
    sh = logging.StreamHandler()
    sh.setLevel('DEBUG')
    sh.setFormatter(fmt)
    
    fh = logging.FileHandler(CONFIG['logfile'])
    fh.setLevel('INFO')
    fh.setFormatter(fmt)
    
    mh = mimetypeSMTPHandler(
        CONFIG['mail']['host'],
        CONFIG['mail']['account'],
        CONFIG['mail']['address'].split(',')[0],  # only send mail to developer
        '[ERROR]{}'.format(logger.name),
        credentials=(CONFIG['mail']['account'], CONFIG['mail']['passwd']),
        )
    mh.set_mimetype('html')
    mh.setLevel('ERROR')
    
    logger.addHandler(sh)
    logger.addHandler(fh)
    logger.addHandler(mh)  # send mail to develop when exception error raise

    mail = logging.getLogger('mail')
    mail.setLevel('INFO')

    smtp = mimetypeSMTPHandler(
        CONFIG['mail']['host'],
        CONFIG['mail']['account'],
        CONFIG['mail']['address'].split(','),
        CONFIG['mail']['subject'],
        credentials=(CONFIG['mail']['account'], CONFIG['mail']['passwd']),
        )
    smtp.set_mimetype('html')
        
    mail.addHandler(smtp)  # send mail with html table
    # weixin push notification with markdown content
    weixin = PushBear(CONFIG['SendKey'])
    # run it 
    try:
        main()
    except (ReadTimeout, ConnectionError) as e:
        mail.error('无法正常访问，请检查系统或者网络是否正常运行。')
        weixin.send('无法正常访问，请检查系统或者网络是否正常运行。')
    except Exception as e:  # only send to develop
        logger.exception(e, exc_info=True)