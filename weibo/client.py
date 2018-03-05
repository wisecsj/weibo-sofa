# -*- coding: utf-8 -*-


""" 
@author: W@I@S@E 
@contact: wisecsj@gmail.com 
@site: https://wisecsj.github.io 
@file: client.py
@time: 2018/2/19 18:44 
"""
import random
import types
import urllib.parse
import json
import base64
import re
import binascii
import math
from io import BytesIO
import sys
import time
import codecs
import os
import pickle
import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import rsa
import requests
from PIL import Image
# from lxml import etree

from .log import logger

BASE_URL = 'https://login.sina.com.cn'
PRE_LOGIN_URL = BASE_URL + '/sso/prelogin.php?entry=weibo&callback=sinaSSOController.preloginCallBack&su={}&rsakt=mod&checkpin=1&client=ssologin.js(v1.4.19)'
LOGIN_URL = BASE_URL + '/sso/login.php?client=ssologin.js(v1.4.19)'


class CommentMixin:
    def update_headers(self):
        # set X-Requested-With and referer is essential
        self.headers['X-Requested-With'] = 'XMLHttpRequest'
        self.headers['Origin'] = 'https://weibo.com'
        self.headers['Accept-Language'] = 'zh-CN,zh;q=0.9'
        self.headers[
            'Referer'] = 'https://weibo.com/'
        self.headers['Accept-Encoding'] = 'gzip, deflate, br'

    def add_comment(self, mid, uid=None, content=None, cookies=None):
        self.update_headers()

        rnd = int(time.time() * 1e3)
        content = content or self.config['CONTENT']

        url = "https://weibo.com/aj/v6/comment/add?ajwvr=6&__rnd=%d" % rnd
        form = {
            'act': 'post',
            'mid': mid,
            'uid': uid or self.uid,
            'forward': 0,
            'isroot': 0,
            'content': content,
            'location': 'v6_content_home',
            'module': 'scommlist',
            'group_source': '',
            'pdetail': '',
            '_t': 0,
        }
        if cookies:
            r = self.ses.post(url, data=form, headers=self.headers, cookies=cookies)
        else:
            r = self.ses.post(url, data=form, headers=self.headers)

        # print(r.text)
        rlt = r.json()
        logger.critical("添加评论,code:{},msg:{},mid:{},content:{}".format(rlt['code'], rlt['msg'], mid, content))

    def del_comment(self, mid, uid, cid, cookies=None):
        self.update_headers()

        rnd = int(time.time() * 1e3)
        url = "https://weibo.com/aj/comment/del?ajwvr=6&__rnd=%d" % rnd

        form = {
            'act': 'delete',
            'mid': mid,
            'cid': cid,
            'uid': uid,
            'is_block': 0,
            'location': 'v6_content_home',
            'rid': cid,
            # owner id
            'oid': '5860185885',
            '_t': 0,
        }
        if cookies:
            r = self.ses.post(url, data=form, headers=self.headers, cookies=cookies)
        else:
            r = self.ses.post(url, data=form, headers=self.headers)
        print(r.text)
        r = r.json()
        if r['code'] != '100000':
            logger.exception('评论删除失败，%s' % r)
            return False
        else:
            return True


class Client(CommentMixin):
    def __init__(self, username, password, config_file):
        """

        :param name: application name
        :param username:  weibo username
        :param password:  weibo password
        """
        self.usr = username
        self.pwd = password
        self.root_path = os.path.dirname(sys.argv[0])
        # 是否为第一次执行check函数
        self.first_check = True
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.lock = threading.Lock()

        # config init
        self.config = {}
        self.load_config(config_file)
        self.record_path = os.path.join(self.root_path, self.config['RECORD_PATH'])

        self.ses = requests.session()

        # for Fiddler debug
        # remove when in production mode

        # self.ses.proxies = {
        #     'http': "http://127.0.0.1:8888",
        #     'https': "http://127.0.0.1:8888",
        # }
        # self.ses.verify = r'C:\Users\34398\Desktop\FiddlerRoot.pem'

        self.jsonData = {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'

        }
        self.uid = None  # user id (type: str)
        self._logged = None
        # record file last modification time
        try:
            self.mtime = os.path.getmtime(self.record_path)
        except:
            self.mtime = None
        self.u_config = {}  # user config acquired after logged on.e.g.,uid,location

        # pending message id
        self.pending_mid = []
        # keys are cookies,uid,self.uid_mid
        self.record = {}

        self._unpickle_record()

        self.cookies = self.record.get('cookies', None)
        self.uids = self.record.get('uids', None) or self.config['UID']
        # uid is the key,mid is the last mid
        self.uid_mid = copy.copy(self.record.get('uid_mid', {}))
        # 在初始化时执行登录操作（会先检查登录状态）
        self.login()

    def load_config(self, filename):
        filename = os.path.join(self.root_path, filename)
        d = types.ModuleType('config')
        d.__file__ = filename
        try:
            with open(filename, mode='rb') as config_file:
                exec(compile(config_file.read(), filename, 'exec'), d.__dict__)
        except IOError as e:
            logger.exception('配置加载出错')
            raise e
        for key in dir(d):
            if key.isupper():
                self.config[key] = getattr(d, key)
        logger.info('配置加载成功~')
        return True

    def _unpickle_record(self):
        if os.path.exists(self.record_path):
            with open(self.record_path, 'rb') as f:
                self.record = pickle.load(f)

    def pickle_record(self):
        with open(self.record_path, 'wb') as f:
            pickle.dump(self.record, f)

    @property
    def logged(self):
        self._logged = self.logon()
        return self._logged

    @property
    def modified(self):
        def modified(file_path):
            t = os.path.getmtime(file_path)
            if t > self.mtime:
                self.mtime = t
                return True
            else:
                return False

        # 文件不存在，不可能被修改过
        if self.mtime is None:
            return False
        else:
            return modified(self.record_path)

    def get_su(self):
        """
        get su based on self.usr
        :return: su para
        """
        t_usr = urllib.parse.quote(self.usr)

        t_usr = base64.b64encode(t_usr.encode('utf-8'))

        rv = t_usr.decode('utf-8')

        return rv

    def get_pre_data(self):
        """
        auquire json data from prelogin url
        """
        su = self.get_su()
        try:
            # encoding = utf-8
            r = self.ses.get(PRE_LOGIN_URL.format(su))
            text = r.text
        except Exception as e:
            logger.exception('获取Prelogin-Url响应出错')
            raise e

        data = re.search(r'\((.*?)\)', text).group(1)
        self.jsonData = json.loads(data)
        return self.jsonData

    def get_sp(self):
        """
        RSAKey.setPublic(me.rsaPubkey, "10001");
        password = RSAKey.encrypt([me.servertime, me.nonce].join("\t") + "\n" + password)
        :param data: get_pre_data rv
        :return:
        """
        data = self.jsonData

        servertime = str(data['servertime'])
        nonce = str(data['nonce'])
        pubkey = str(data['pubkey'])

        msg = "{}\t{}\n{}".format(servertime, nonce, self.pwd)
        pk = rsa.PublicKey(int(pubkey, 16), int('10001', 16))

        encrypt_msg = rsa.encrypt(msg.encode('utf-8'), pk)
        rv = binascii.b2a_hex(encrypt_msg).decode('utf-8')

        return rv

    def pin_code(self):
        """
        让用户根据图片输入验证码，并返回
        """
        # bulid pincodeUrl
        pincodeUrl = "https://login.sina.com.cn/cgi/pin.php"
        r = math.floor(random.random() * 1e8)
        s = '0'
        p = self.jsonData['pcid']
        pincodeUrl = pincodeUrl + "?r=" + str(r) + "&s=" + s + "&p=" + p
        # 在cmd中显示验证码图片
        r = self.ses.get(pincodeUrl)
        im = Image.open(BytesIO(r.content))
        im.show()
        # get pincode from user
        pincode = input('please input verify code:\n')
        return pincode

    def build_form_data(self, data=None):
        data = data or self.jsonData
        code = None
        pcid = self.jsonData['pcid']
        # print('jsonData',self.jsonData)
        if self.jsonData.get('showpin', 0) == 1:
            code = self.pin_code()
        try:
            form_data = {
                'door': code or '',
                'pcid': pcid,

                "entry": "weibo",
                "gateway": "1",
                "from": "",
                "savestate": "7",
                "qrcode_flag": False,
                "useticket": "1",
                "pagerefer": "",
                "vsnf": "1",
                "su": self.get_su(),
                "service": "miniblog",
                "servertime": data['servertime'],
                "nonce": data['nonce'],
                "pwencode": "rsa2",
                "rsakv": data['rsakv'],
                "sp": self.get_sp(),
                "sr": "1280*800",
                "encoding": "UTF-8",
                "prelt": "77",
                "url": "http://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack",
                "returntype": "META"
            }
        except Exception as e:
            logger.exception('构造登录表单数据时出错')
            raise e
        return form_data

    def do_login(self, form_data):
        r = self.ses.post(LOGIN_URL, data=form_data, headers=self.headers)
        # 需要显式指定编码方式
        r.encoding = 'gbk'
        r_text = r.text
        return r_text

    def handle_login_exc(self, r_text, form_data):
        def makenonce(digit=6):
            b = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            c = ''
            for _ in range(digit):
                # JS:     c += b.charAt(Math.ceil(Math.random() * 1e6) % b.length);
                i = math.ceil(random.random() * 1e6) % len(b)
                c += b[i]
            return c

        error = re.search(r'retcode=(\d+)&reason=(.*?)&#39', r_text)
        # step 3
        logger.debug('step 3 start')
        if error:
            # step 3.1
            logger.debug('step 3.1 start')
            code = error.group(1)
            r = error.group(2)
            r = urllib.parse.unquote(r, encoding='gbk')
            logger.info('retcode:%s   reason:%s' % (code, r))
            # print(code, r)

            if code in ('4049', '2070'):
                # 即使输入验证码正确，也需要再次输入一次
                json_data = self.get_pre_data()
                form_data = self.build_form_data(json_data)
                # print(json_data, form_data, sep='\n')
                r_text = self.do_login(form_data)
                time.sleep(1)
                # print(r_text)
                return self.handle_login_exc(r_text, form_data)
            # elif code == '2070':
            #     logger.info('验证码错误\n')
            #     code = self.pin_code()
            #     form_data['door'] = code
            #     form_data['nonce'] = makenonce()
            #     r_text = self.do_login(form_data)
            #     return self.handle_login_exc(r_text, form_data)
            else:
                logger.debug("r_text:%s" % r_text)
                logger.exception("登录异常：%s,%s" % (code, r))
                sys.exit(r)  # program exit

        else:
            return r_text

    def login(self):
        if self.logged:
            return
        elif self.cookies:
            # add to cookieJar
            self.ses.cookies = self.cookies
            if self.logged:
                self.get_user_config()
                logger.info('通过Cookies登录成功')

                return
            logger.info('通过Cookies登录失败')
            self.ses.cookies.clear_session_cookies()

        # step 0
        self.ses.get('https://weibo.com')
        # step 1
        logger.debug('step 1 start')
        json_data = self.get_pre_data()
        # form_data = self.build_form_data() also works well
        form_data = self.build_form_data(json_data)
        logger.debug('step 1 end')

        # step 2
        logger.debug('step 2 start')

        try:
            r_text = self.do_login(form_data)
            # print('-' * 20)
            # print(r.url, r.status_code, r.text, sep='\n')
            # print('-' * 20)
        except Exception as e:
            logger.exception('login.php 登录请求出错')
            raise e

        # step 3
        logger.debug('step 3 start')
        r_text = self.handle_login_exc(r_text, form_data)
        logger.debug('r_text:%s' % r_text)

        p = re.compile(r'location\.replace\((\'|\")(.*?)(\'|\")\)')

        # step 3.2
        logger.debug('step 3.2 start')

        url_1 = p.search(r_text).group(2)
        r1 = self.ses.get(url_1)
        r1.encoding = 'gbk'
        r1_text = r1.text

        logger.debug('step 3 end')

        # step 4
        logger.debug('step 4 start')
        url_2 = p.search(r1_text).group(2)
        # print('url_2: ', url_2)
        logger.debug('url_2%s' % url_2)

        r2 = self.ses.get(url_2)  # 302
        # 这里不需要手动设置编码，是因为此次请求微博返回
        # headers['Content-Type']设置了charset字段
        # 而之前的请求没有设置
        r2_text = r2.text
        logger.debug('step 4 end')

        # step 5
        p2 = re.compile(r'"userdomain":"(.*?)"')
        url_3 = p2.search(r2_text).group(1)

        # step 6
        url_final = 'https://weibo.com/' + url_3
        r3 = self.ses.get(url_final)
        text_final = r3.text

        if self.logged:
            logger.critical('登录成功')
            self.get_user_config()
            return 0
        else:
            logger.critical('登录失败')
            return -1

    def parse_page(self, text):
        """
        微博的数据不是直接通过HTML展示的，而是内嵌在JS中
        通过正则提取出来，供 func check 调用
        """
        pass

    def check(self):
        """
        依次检查uid最新微博的mid，以及是否需要更新self.uid_mid字典（生产者）
        """
        # 与微博网络连接的状态，防止被封出现414错误仍不停check
        status = False
        url = 'https://weibo.com/u/%s?is_all=1'
        # uids 为包含所有需要抢沙发的人的uid
        for uid in self.uids:
            r = self.ses.get(url % uid)
            if not r.ok:
                logger.exception("check执行返回状态码:{}".format(r.status_code))
                continue
            # 存在连接正常，设为True
            status = True
            text = r.text
            text = codecs.decode(text, 'unicode_escape')
            try:
                mids = []
                # 包括原创和转发的所有微博
                rlt = re.findall(r'tbinfo="ouid=%s(.*?)<div' % uid, text, re.S)
                # rlt = re.findall(r'<div\s*tbinfo="ouid=%s"(.*?)<div' % uid, text, re.S)
                for ele in rlt:
                    t = re.search(r'mid="(\d+)"', ele)
                    if t:
                        mids.append(t.group(1))
                # root = etree.HTML(r.text)
                # e = root.xpath("//div[@tbinfo='ouid=%s']/@mid" % uid)
                # print(e)
                # 最新发布的微博的mid
                last_mid = sorted(mids)[-1]
                if uid not in self.uid_mid:
                    self.uid_mid[uid] = last_mid
                    continue
                elif last_mid > self.uid_mid[uid]:
                    if not self.first_check:
                        self.uid_mid[uid] = last_mid
                        with self.lock:
                            self.pending_mid.append(last_mid)
                        self.executor.submit(self.consume, last_mid)
                    else:
                        self.uid_mid[uid] = last_mid
                time.sleep(random.choice(self.config['INTERVAL']) - 1)

            except Exception as e:
                logger.exception('对用户{uid}执行check时出错'.format(uid=uid))
                raise e
        if self.first_check:
            self.first_check = False
        if not status:
            # 所有请求返回状态码都大于等于400，退出程序
            logger.exception('对所有uid用户check失败，请检测是否被封')
            sys.exit()

    def consume(self, mid):
        try:
            self.add_comment(mid)
        except:
            logger.exception("对微博%s添加评论失败" % mid)
        finally:
            self.lock.acquire(blocking=True, timeout=3)
            self.pending_mid.remove(mid)
            self.lock.release()

    def run_once(self):
        # pickle stuff
        if self.modified:
            self._unpickle_record()
            self.uids = self.record['uids']

        self.check()
        logger.info('pending mid : %s' % repr(self.pending_mid))
        # if self.pending_mid:
        #     self.consume()

        new_record = {'cookies': self.ses.cookies, 'uids': self.uids, 'uid_mid': self.uid_mid}
        if new_record == self.record:
            logger.info('record not changed ...')
            time.sleep(random.choice(self.config['INTERVAL']))
        else:
            logger.info('record changed, pickling...')
            self.record = new_record
            self.pickle_record()
            self.mtime = os.path.getmtime(self.record_path)

    def run(self):
        while True:
            self.run_once()

    def get_user_config(self):
        r = self.ses.get("https://weibo.com/")
        text = r.text
        logger.debug('r_text_by_func_get_user_config:%s' % text)
        # user config required to get
        config = ['uid', 'location', 'nick', ]  # 'pid'
        pattern = r"\$CONFIG\['%s'\]='(.*?)'"

        try:
            for i in config:
                v = re.search(pattern % i, text).group(1)
                self.u_config[i] = v
        except Exception as e:
            logger.exception('登录后获取用户配置 {} 出错'.format(i.upper()))
            raise e

        self.uid = self.u_config['uid']

    def logon(self):
        """
        check if has logged on
        when logged on, request "https://weibo.com/"
        will redirect to "https://weibo.com/u/(uid)/home"
        """
        r = self.ses.get("https://weibo.com/")
        if re.search(r"u/(\d+)/home", r.url) \
                or re.search(r"weibo.com/(.*?)/home", r.url):
            return True
        else:
            return False
