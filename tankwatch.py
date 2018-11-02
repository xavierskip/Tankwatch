#!/usr/bin/env python3
# coding: utf-8
import requests
import json
import re
import logging
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

yaml=YAML(typ='safe')
with open(config_file) as f:
    CONFIG = yaml.load(f)

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
        r = self.session.post(self.url, data=payload)
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
        return self.session.post(self.url, headers=headers, data=payload)

    def get_failinfo_json(self, from_date, to_date):
        r = self.failinfo(from_date, to_date)
        # print(r.text)
        prog = re.compile('data:(\[.+\])')
        result = prog.search(r.text)
        if result:
            return json.loads(result.group(1))
        else:
            return None

def main():
    tank = Tank()
    tank.login(CONFIG['username'],CONFIG['password'])
    fd, td = datetime_from_to(**CONFIG['timedelta'])
    data = tank.get_failinfo_json(fd, td)
    if data:
        messages = []
        for item in data:
            # print(item)
            time = item['WarningDateTime']
            name = item['FDevName']
            fault = item['FFaultTypeName']
            alarm = item['FAlarmValue']
            temp = item['FTempValue1']
            trange = item['fanwei']
            messages.append('{} {} {} {} {} {}'.format(
                time, fault, name, alarm, trange, temp))
        s = '\n'.join(messages)
        logger.info(s)
        mail.info(s)
    else:
        logger.info('NO Alarm.')
        return 0

if __name__ == '__main__':
    # for logging
    fmt = logging.Formatter(
        fmt='%(asctime)s --\n%(message)s',
        datefmt='%Y/%m/%d %H:%M:%S',
        )
    logger = logging.getLogger(__name__)
    logger.setLevel('DEBUG')
    sh = logging.StreamHandler()
    sh.setLevel('DEBUG')
    sh.setFormatter(fmt)
    fh = logging.FileHandler(CONFIG['logfile'])
    fh.setLevel('INFO')
    fh.setFormatter(fmt)
    mh = SMTPHandler(
        CONFIG['mail']['host'],
        CONFIG['mail']['account'],
        CONFIG['mail']['address'].split(',')[0],  # send mail to developer
        '[ERROR] TankWatch',
        credentials=(CONFIG['mail']['account'], CONFIG['mail']['passwd']),
        )
    mh.setLevel('ERROR')
    logger.addHandler(sh)
    logger.addHandler(fh)
    logger.addHandler(mh)

    mail = logging.getLogger('mail')
    mail.setLevel('INFO')
    smtp = SMTPHandler(
        CONFIG['mail']['host'],
        CONFIG['mail']['account'],
        CONFIG['mail']['address'].split(','),
        CONFIG['mail']['subject'],
        credentials=(CONFIG['mail']['account'], CONFIG['mail']['passwd']),
        )
    mail.addHandler(smtp)
    # run it 
    try:
        main()
    except (ReadTimeout, ConnectionError) as e:
        mail.error('无法正常访问，请检查系统或者网络是否正常运行。', exc_info=True)
    except Exception as e:
        logger.exception(e, exc_info=True)