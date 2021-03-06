#!/usr/bin/env python3
# coding: utf-8
import re
import os
import json
import time
import requests
import argparse
import logging
from notify import mimetypeSMTPHandler, SC
from dic import YAMLdict 
from datetime import datetime, timedelta
from requests.exceptions import ReadTimeout, ConnectionError

Datefmt = "%Y-%m-%d %H:%M:%S"

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

CONFIG = YAMLdict(config_file)

if not os.path.isabs(CONFIG['logfile']):
    CONFIG['logfile'] = os.path.join(HERE, CONFIG['logfile'])

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
weixin = SC(CONFIG['ftqq']['SendKey'])

def datetime_from_to(**kwargs):
    date_to = datetime.now()
    date_from = date_to - timedelta(**kwargs)
    return date_from.strftime(Datefmt),  date_to.strftime(Datefmt)

def path(path):
    def decorate(func):
        def wrapper(self, *args, **kwargs):
            self.url = self.host+path
            return func(self, *args, **kwargs)
        return wrapper
    return decorate

class LoginFailError(Exception):
    pass

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
    host = CONFIG['site']['host']

    @path('/')
    def ping(self):
        return self.session.get(self.url)

    @path('/Default.aspx')
    def login(self, user, passwd):
        payload = {
            # "__EVENTTARGET": "",
            # "__EVENTARGUMENT": "",
            "__VIEWSTATE": "/wEPDwUKLTQxOTI5ODg5NWQYAQUeX19Db250cm9sc1JlcXVpcmVQb3N0QmFja0tleV9fFgMFDlNjcmlwdE1hbmFnZXIxBQhidG5Mb2dpbgUJYnRuQ2FuY2VsGqkA3CjmnLrHACl9kd9YZpKcjSI=",
            # "__VIEWSTATEGENERATOR": "CA0B0334",
            "__EVENTVALIDATION": "/wEWBgK3rLTDAwLB5eCpDQKl1bK4CQLKw6LdBQKC3IeGDAKQ9M/rBfddaPKySA+jkCmMpYQMOSF3L+uP",
            "txtUsername": user,
            "txtPass": passwd,
            "btnLogin.x": 0,
            "btnLogin.y": 0
        }
        r = self.session.post(self.url, data=payload, timeout=30)
        return r

    @path('/Pages/FailManage/FailInfoList.aspx')
    def failinfo(self, from_date, to_date, alarm_state=0):
        '''
        just get 未处理 fail info
        alarm_state:
            -1 全部
            0  未处理
            1  已处理
        '''
        dateFieldFrom, timeFieldFrom_Value = from_date.split(' ')
        dateFieldTo, timeFieldTo_Value = to_date.split(' ')
        # print(dateFieldFrom, timeFieldFrom_Value, dateFieldTo, timeFieldTo_Value)
        states = {
            -1: (-1,'全部',0),
            0: (0,'未处理',1),
            1: (1,'已处理',2),
        }
        AlarmState_Value, AlarmState, AlarmState_SelIndex = states[alarm_state]
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
            'combFAlarmState_Value': AlarmState_Value,
            'combFAlarmState': AlarmState,
            'combFAlarmState_SelIndex': AlarmState_SelIndex,
            'PagingToolBar1_ActivePage': 1,
            '__EVENTTARGET': 'ScriptManager1',
            '__EVENTARGUMENT': 'storeFailList|postback|refresh',
        }
        return self.session.post(self.url, headers=headers, data=payload, timeout=30)

    def get_failinfo_json(self, from_date, to_date, alarm_state=0):
        r = self.failinfo(from_date, to_date, alarm_state)
        # print(r.text)        
        if r.text == '{script:"window.location=\\"/Default.aspx\\";"}':
            raise LoginFailError
        prog = re.compile(r'data:(\[.+\])')
        result = prog.search(r.text)
        if result:
            # return list
            return json.loads(result.group(1))
        else:
            return None

def main():
    tank = Tank()
    tank.login(CONFIG['site']['username'],CONFIG['site']['password'])
    fd, td = datetime_from_to(**CONFIG['alarm']['timedelta'])
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
        
        # send to weixin
        # title = "有{}条报警信息".format(len(data))
        # markdown = md_template.format('\n'.join(mdtr))
        # weixin.send(title, markdown)
    # elif data = 
    else:
        logger.info('NO Alarm.')
        return 0

if __name__ == '__main__':
    n = 3
    for _ in range(n):
        try:  # run it and catch the error to log it
            main()
            if not CONFIG['alarm'].get('run') and CONFIG['alarm'].get('last_live'):
                # print(str(datetime.now())+'Tank ready to go')
                mail.info('系统已经开始运行。')
                weixin.send('系统已经开始运行。', str(datetime.now()))
            # run write last live time
            CONFIG['alarm']['run'] = 1
            CONFIG['alarm']['last_live'] = datetime.now().strftime(Datefmt)
            CONFIG.save()
            break
        except (LoginFailError, ReadTimeout, ConnectionError) as e:
            if _ < (n-1):
                logger.info('try %s' %(_+1))
                time.sleep(_*n+n)
                continue
            # int the last loop 
            CONFIG['alarm']['run'] = 0
            CONFIG.save()
            pass_time = datetime.now() - datetime.strptime(CONFIG['alarm'].get('last_live','1970-1-1 0:0:0'), Datefmt)
            if  pass_time < timedelta(**CONFIG['alarm']['buffer']):
                if isinstance(e, LoginFailError):
                    logger.error('! login error')
                if isinstance(e, (ReadTimeout, ConnectionError)):
                    logger.info('disconnect!')
                    mail.error('无法正常访问，请检查系统或者网络是否正常运行。')
                    weixin.send('无法正常访问，请检查系统或者网络是否正常运行。','{} pass.'.format(pass_time))
            else:  # do nothing and waiting for system to run
                logger.info('>_<')
        except Exception as e:  # only send to develop
            logger.exception(e, exc_info=True)
            break
