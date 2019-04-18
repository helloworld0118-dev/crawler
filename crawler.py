# -*- coding: utf-8 -*-
"""
@author: 冰蓝
@site: http://lanbing510.info
"""

import re
import urllib2
import sqlite3
import random
import threading
import json
from multiprocessing import Pool
from bs4 import BeautifulSoup

import sys

reload(sys)
sys.setdefaultencoding("utf-8")


# 登录，不登录不能爬取三个月之内的数据
#import LianJiaLogIn

# Some User Agents
hds = [{'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6'}, \
       {
           'User-Agent': 'Mozilla/5.0 (Windows NT 6.2) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.12 Safari/535.11'}, \
       {'User-Agent': 'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Trident/6.0)'}, \
       {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:34.0) Gecko/20100101 Firefox/34.0'}, \
       {
           'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/44.0.2403.89 Chrome/44.0.2403.89 Safari/537.36'}, \
       {
           'User-Agent': 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50'}, \
       {
           'User-Agent': 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50'}, \
       {'User-Agent': 'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0'}, \
       {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.6; rv:2.0.1) Gecko/20100101 Firefox/4.0.1'}, \
       {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:2.0.1) Gecko/20100101 Firefox/4.0.1'}, \
       {
           'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_0) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11'}, \
       {'User-Agent': 'Opera/9.80 (Macintosh; Intel Mac OS X 10.6.8; U; en) Presto/2.8.131 Version/11.11'}, \
       {'User-Agent': 'Opera/9.80 (Windows NT 6.1; U; en) Presto/2.8.131 Version/11.11'}]

# 北京区域列表
regions = [u"changping",u"shunyi",u'yizhuangkaifaqu',u"daxing",u"chaoyang",u"fengtai",u"haidian"]
#regions = [u"shunyi"]

lock = threading.Lock()


class SQLiteWraper(object):
    """
    数据库的一个小封装，更好的处理多线程写入
    """

    def __init__(self, path, command='', *args, **kwargs):
        self.lock = threading.RLock()  # 锁
        self.path = path  # 数据库连接参数

        if command != '':
            conn = self.get_conn()
            cu = conn.cursor()
            cu.execute(command)

    def get_conn(self):
        conn = sqlite3.connect(self.path)  # ,check_same_thread=False)
        conn.text_factory = str
        return conn

    def conn_close(self, conn=None):
        conn.close()

    def conn_trans(func):
        def connection(self, *args, **kwargs):
            self.lock.acquire()
            conn = self.get_conn()
            kwargs['conn'] = conn
            rs = func(self, *args, **kwargs)
            self.conn_close(conn)
            self.lock.release()
            return rs

        return connection

    @conn_trans
    def execute(self, command, method_flag=0, conn=None):
        cu = conn.cursor()
        try:
            if not method_flag:
                cu.execute(command)
            else:
                cu.execute(command[0], command[1])
            conn.commit()
        except sqlite3.IntegrityError, e:
            # print e
            return -1
        except Exception, e:
            print e
            return -2
        return 0

    @conn_trans
    def fetchall(self, command="select name from xiaoqu", conn=None):
        cu = conn.cursor()
        lists = []
        try:
            cu.execute(command)
            lists = cu.fetchall()
        except Exception, e:
            print e
            pass
        return lists


def gen_xiaoqu_insert_command(info_dict):
    """
    生成小区数据库插入命令
    """
    info_list = [u'小区名称', u'大区域', u'小区域', u'小区户型', u'建造时间', u'参考价', u'在售',u'链接']
    t = []
    for il in info_list:
        if il in info_dict:
            t.append(info_dict[il])
        else:
            t.append('')
    t = tuple(t)
    command = (r"insert into xiaoqu values(?,?,?,?,?,?,?,?)", t)
    return command

def gen_selling_insert_command(info_dict):
    """
    生成在售记录数据库插入命令
    """
    info_list = [u'链接',u'大区域',u'小区域', u'小区名称', u'距离', u'户型',u'结构', u'建筑面积',u'套内面积', u'朝向', u'楼层', u'年代', u'产权年限', u'地铁', u'挂牌时间', u'交易权属', u'上次交易'
        , u'房屋用途', u'房屋年限', u'产权所属', u'抵押信息', u'房本备件', u'价格', u'单价', u'主标题', u'副标题']
    t = []
    for il in info_list:
        if il in info_dict:
            t.append(info_dict[il])
        else:
            t.append('')
    t = tuple(t)
    command = (r"insert into selling values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", t)
    return command

def gen_chengjiao_insert_command(info_dict):
    """
    生成成交记录数据库插入命令
    """
    info_list = [u'链接', u'小区名称', u'户型', u'面积', u'朝向', u'楼层', u'建造时间', u'签约时间', u'签约单价', u'签约总价', u'房产类型', u'学区', u'地铁']
    t = []
    for il in info_list:
        if il in info_dict:
            t.append(info_dict[il])
        else:
            t.append('')
    t = tuple(t)
    command = (r"insert into chengjiao values(?,?,?,?,?,?,?,?,?,?,?,?,?)", t)
    return command


def xiaoqu_spider(db_xq, url_page=u"http://bj.lianjia.com/xiaoqu/%E6%98%8C%E5%B9%B3/"):
    """
    爬取页面链接中的小区信息
    """
    try:
        req = urllib2.Request(url_page, headers=hds[random.randint(0, len(hds) - 1)])
        source_code = urllib2.urlopen(req, timeout=10).read()
        plain_text = unicode(source_code)  # ,errors='ignore')
        soup = BeautifulSoup(plain_text)
    except (urllib2.HTTPError, urllib2.URLError), e:
        exception_write('xiaoqu_spider', url_page)
        print e
        exit(-1)
    except Exception, e:
        exception_write('xiaoqu_spider', url_page)
        print e
        exit(-1)

    xiaoqu_list = soup.findAll('li', {'class': 'xiaoquListItem'})
    for xq in xiaoqu_list:

        info_dict = {}
        info_dict.update({u'小区名称': xq.find('div',{'class': 'title'}).text.strip()})
        info_dict.update({u'大区域': xq.find('a', {'class': 'district'}).text})
        info_dict.update({u'小区域': xq.find('a', {'class': 'bizcircle'}).text})
        content = xq.find('div', {'class': 'positionInfo'}).text
        temp_price = xq.find('div', {'class': 'totalPrice'}).text
        info_dict.update({u'参考价': temp_price.replace('元/m2','')})
        temp_sellcount= xq.find('a', {'class': 'totalSellCount'}).text
        sellcount = temp_sellcount.replace('套', '')

        # if sellcount==0 or sellcount=='0':
        #     continue

        info_dict.update({u'在售': sellcount})

        info_dict.update({u'链接': xq.find('a', {'class': 'totalSellCount'}).attrs['href']})
        info = content.split('/')
        if (len(info) == 3):
            info_dict.update({u'小区户型':info[1].strip()})
            info_dict.update({u'建造时间': info[2].strip()[:4]})
        else:
            i = 1
            temp = ""
            while i < len(info)-2:
                temp+=info[i]+"/"
                i+=1
            info_dict.update({u'小区户型':temp})

            info_dict.update({u'建造时间': info[len(info)-1].strip()[:4]})

        command = gen_xiaoqu_insert_command(info_dict)

        db_xq.execute(command, 1)


def do_xiaoqu_spider(db_xq, region=u""):
    """
    爬取大区域中的所有小区信息
    """
    url = u"http://bj.lianjia.com/xiaoqu/" + region + "/"
    try:
        req = urllib2.Request(url, headers=hds[random.randint(0, len(hds) - 1)])
        source_code = urllib2.urlopen(req, timeout=5).read()
        plain_text = unicode(source_code)  # ,errors='ignore')
        soup = BeautifulSoup(plain_text)
    except (urllib2.HTTPError, urllib2.URLError), e:
        exception_write('do_xiaoqu_spider', url)
        print e
        return
    except Exception, e:
        exception_write('do_xiaoqu_spider', url)
        print e
        return
    try:
        d = "d=" + soup.find('div', {'class': 'page-box house-lst-page-box'}).get('page-data')
    except Exception,e:
        print soup
    exec (d)
    total_pages = d['totalPage']

    threads = []
    #print region, total_pages

    for i in range(total_pages):
        url_page = u"http://bj.lianjia.com/xiaoqu/%s/pg%d/" % (region,i+1)
        t = threading.Thread(target=xiaoqu_spider, args=(db_xq, url_page))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print u"爬下了 %s 区全部的小区信息" % region

def selling_detail_spider(db_sl, url_page):
    try:
        req = urllib2.Request(url_page, headers=hds[random.randint(0, len(hds) - 1)])
        source_code = urllib2.urlopen(req, timeout=30).read()
        plain_text = unicode(source_code)  # ,errors='ignore')
        soup = BeautifulSoup(plain_text)
    except (urllib2.HTTPError, urllib2.URLError), e:
        print e
        exception_write('selling_detail_spider', url_page)
        return
    except Exception, e:
        print e
        exception_write('selling_detail_spider', url_page)
        return
    try:
        dict_info = {}
        dict_info.update({u'链接': url_page})
        title_main = soup.find('div',{'class':'sellDetailHeader'}).find('div', {'class': 'title'}).find('h1',{'class':'main'}).text
        title_sub = soup.find('div',{'class':'sellDetailHeader'}).find('div', {'class': 'title'}).find('div',{'class':'sub'}).text
        dict_info.update({u'主标题': title_main})
        dict_info.update({u'副标题': title_sub})
        price = soup.find('div', {'class', 'price'}).find('span', {'class': 'total'}).text
        unitPrice = soup.find('div', {'class', 'unitPrice'}).text.replace('元/平米', '')
        dict_info.update({u'价格': price})
        dict_info.update({u'单价': unitPrice})
        house_info = soup.find('div', {'class', 'houseInfo'}).find('div', {'class': 'area'}).find('div', {
            'class': 'subInfo'}).text.split('/')[0]
        p1 = r'[0-9]*'
        pattern1 = re.compile(p1)
        matcher1 = re.search(pattern1, house_info)
        years = matcher1.group(0)
        dict_info.update({u'年代': years})
        introContent = soup.find('div', {'class': 'introContent'}).find('div', {'class', 'content'})
        lis = introContent.find_all('li')
        for li in lis:
            spans = li.find_all('span')
            if spans[0].text == '房屋户型':
                dict_info.update({u'户型': li.text.strip().replace('房屋户型', '')})
            elif spans[0].text == '所在楼层':
                dict_info.update({u'楼层': li.text.strip().replace('所在楼层', '')})
            elif spans[0].text == '建筑面积':

                p1 = r'[0-9\.]*'
                pattern1 = re.compile(p1)
                matcher1 = re.search(pattern1, li.text.strip().replace('建筑面积', ''))
                ret = matcher1.group(0)
                if not ret:
                    ret = -1
                dict_info.update({u'建筑面积': ret})
            elif spans[0].text == '户型结构':
                dict_info.update({u'结构': li.text.strip().replace('户型结构', '')})
            elif spans[0].text == '套内面积':
                p1 = r'[0-9\.]*'
                pattern1 = re.compile(p1)
                matcher1 = re.search(pattern1, li.text.strip().replace('套内面积', ''))
                ret = matcher1.group(0)
                if not ret:
                    ret = -1
                dict_info.update({u'套内面积': ret})
            elif spans[0].text == '房屋朝向':
                dict_info.update({u'朝向': li.text.strip().replace('房屋朝向', '')})
            elif spans[0].text == '装修情况':
                dict_info.update({u'装修': li.text.strip().replace('装修情况', '')})
            elif spans[0].text == '配备电梯':
                dict_info.update({u'电梯': li.text.strip().replace('配备电梯', '')})
            elif spans[0].text == '产权年限':
                dict_info.update({u'产权年限': li.text.strip().replace('产权年限', '')})

        aroundInfo = soup.find('div', {'class': 'aroundInfo'})

        dict_info.update(
            {u'小区名称': aroundInfo.find('div', {'class': 'communityName'}).find('a', {'class': 'info'}).text})

        areaName = aroundInfo.find('div', {'class': 'areaName'}).find('span', {'class': 'info'}).text.split()
        if (len(areaName) ==1):
            dict_info.update({u'大区域': areaName[0]})
        elif(len(areaName)==3):
            dict_info.update({u'大区域': areaName[0]})
            dict_info.update({u'小区域': areaName[1]})
            dict_info.update({u'距离': areaName[2]})
        elif(len(areaName)==2):
            dict_info.update({u'大区域': areaName[0]})
            dict_info.update({u'小区域': areaName[0]})
            dict_info.update({u'距离': areaName[1]})

        transaction = soup.find('div', {'class', 'transaction'}).find('div', {'class', 'content'})
        lis = transaction.find_all('li')
        for li in lis:
            spans = li.find_all('span')
            if spans[0].text == '挂牌时间':
                dict_info.update({u'挂牌时间': spans[1].text.strip()})
            elif spans[0].text == '交易权属':
                dict_info.update({u'交易权属': spans[1].text.strip()})
            elif spans[0].text == '上次交易':
                dict_info.update({u'上次交易': spans[1].text.strip()})
            elif spans[0].text == '房屋用途':
                dict_info.update({u'房屋用途': spans[1].text.strip()})
            elif spans[0].text == '房屋年限':
                dict_info.update({u'房屋年限': spans[1].text.strip()})
            elif spans[0].text == '产权所属':
                dict_info.update({u'产权所属': spans[1].text.strip()})
            elif spans[0].text == '抵押信息':
                dict_info.update({u'抵押信息': spans[1].text.strip()})
            elif spans[0].text == '房本备件':
                dict_info.update({u'房本备件': spans[1].text.strip()})

        subway = soup.find('a', {'class', 'tag is_near_subway'}) or soup.find('a', {'class', 'is_near_subway'})
        if subway:
            dict_info.update({u'地铁': '近'})
        else:
            dict_info.update({u'地铁': '远'})
        #looked = soup.find('div', {'id': 'record'}).find('div', {'class': 'panel'}).find('div', {'class': 'count'}).text
        #dict_info.update({u'7日带看': looked}) 数据是异步的，获取不到

        command = gen_selling_insert_command(dict_info)
        db_sl.execute(command, 1)
    except Exception,e:
        print e
        exception_write('selling_detail_spider', url_page)

def selling_spider(db_sl, url_page):
    """
    爬取页面链接中的在售记录
    """
    try:
        req = urllib2.Request(url_page, headers=hds[random.randint(0, len(hds) - 1)])
        source_code = urllib2.urlopen(req, timeout=30).read()
        plain_text = unicode(source_code)  # ,errors='ignore')
        soup = BeautifulSoup(plain_text)
    except (urllib2.HTTPError, urllib2.URLError), e:
        print e
        exception_write('selling_spider', url_page)
        return
    except Exception, e:
        print e
        exception_write('selling_spider', url_page)
        return

    try:
        no_result = soup.find('div',{'class','m-noresult'})
        if no_result and '没有找到相关房源' in no_result.text:
            return
        lis = soup.find('ul', {'class': 'sellListContent'}).find_all('li', {'class', 'clear LOGCLICKDATA'})
        threads = []
        for li in lis:
            try:
                url = li.find('a', {'class', 'noresultRecommend img'})
            except:
                try:
                    url = li.find('a', {'class', 'noresultRecommend img LOGVIEWDATA LOGCLICKDATA'})
                except:
                    #exception_write('selling_spider', url_page)
                    continue
            if url:
                url = url.attrs['href']
                t = threading.Thread(target=selling_detail_spider, args=(db_sl, url))
                threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    except Exception,e:
        exception_write('selling_spider', url_page)

def chengjiao_spider(db_cj, url_page):
    """
    爬取页面链接中的成交记录
    """
    try:
        req = urllib2.Request(url_page, headers=hds[random.randint(0, len(hds) - 1)])
        source_code = urllib2.urlopen(req, timeout=10).read()
        plain_text = unicode(source_code)  # ,errors='ignore')
        soup = BeautifulSoup(plain_text)
    except (urllib2.HTTPError, urllib2.URLError), e:
        print e
        exception_write('chengjiao_spider', url_page)
        return
    except Exception, e:
        print e
        exception_write('chengjiao_spider', url_page)
        return

    cj_list = soup.findAll('div', {'class': 'info-panel'})
    for cj in cj_list:
        info_dict = {}
        href = cj.find('a')
        if not href:
            continue
        info_dict.update({u'链接': href.attrs['href']})
        content = cj.find('h2').text.split()
        if content:
            info_dict.update({u'小区名称': content[0]})
            info_dict.update({u'户型': content[1]})
            info_dict.update({u'面积': content[2]})
        content = unicode(cj.find('div', {'class': 'con'}).renderContents().strip())
        content = content.split('/')
        if content:
            info_dict.update({u'朝向': content[0].strip()})
            info_dict.update({u'楼层': content[1].strip()})
            if len(content) >= 3:
                content[2] = content[2].strip();
                info_dict.update({u'建造时间': content[2][:4]})
        content = cj.findAll('div', {'class': 'div-cun'})
        if content:
            info_dict.update({u'签约时间': content[0].text})
            info_dict.update({u'签约单价': content[1].text})
            info_dict.update({u'签约总价': content[2].text})
        content = cj.find('div', {'class': 'introduce'}).text.strip().split()
        if content:
            for c in content:
                if c.find(u'满') != -1:
                    info_dict.update({u'房产类型': c})
                elif c.find(u'学') != -1:
                    info_dict.update({u'学区': c})
                elif c.find(u'距') != -1:
                    info_dict.update({u'地铁': c})

        command = gen_chengjiao_insert_command(info_dict)
        db_cj.execute(command, 1)


def xiaoqu_selling_spider(db_sl,url):
    """
    爬取小区在售
    """
    try:
        req = urllib2.Request(url, headers=hds[random.randint(0, len(hds) - 1)])
        source_code = urllib2.urlopen(req, timeout=30).read()
        plain_text = unicode(source_code)  # ,errors='ignore')
        soup = BeautifulSoup(plain_text)
    except (urllib2.HTTPError, urllib2.URLError), e:
        print e
        exception_write('xiaoqu_selling_spider', url)
        return
    except Exception, e:
        print e
        exception_write('xiaoqu_selling_spider', url)
        return


    #lis = soup.find_all('li', {'class': 'clear LOGCLICKDATA'})
    content = soup.find('div', {'class': 'page-box house-lst-page-box'})
    total_pages = 0
    if content:
        d = "d=" + content.get('page-data')
        exec (d)
        total_pages = d['totalPage']

    threads = []
    temp_url =  url.split('/')
    xq_url = temp_url[len(temp_url)-2]
    for i in range(total_pages):
        url_page = u"http://bj.lianjia.com/ershoufang/pg%d%s/" % (i + 1, xq_url)
        t = threading.Thread(target=selling_spider, args=(db_sl, url_page))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # pool = Pool(processes=8)
    # for i in range(total_pages):
    #     url_page = u"http://bj.lianjia.com/ershoufang/pg%d%s/" % (i + 1, xq_url)
    #     pool.apply_async(selling_spider, (db_sl, url_page,))
    #
    # pool.close()
    # pool.join()


def xiaoqu_chengjiao_spider(db_cj, xq_name=u""):
    """
    爬取小区成交记录
    """
    url = u"http://bj.lianjia.com/chengjiao/" + xq_name + "/"
    try:
        req = urllib2.Request(url, headers=hds[random.randint(0, len(hds) - 1)])
        source_code = urllib2.urlopen(req, timeout=10).read()
        plain_text = unicode(source_code)  # ,errors='ignore')
        soup = BeautifulSoup(plain_text)
    except (urllib2.HTTPError, urllib2.URLError), e:
        print e
        exception_write('xiaoqu_chengjiao_spider', xq_name)
        return
    except Exception, e:
        print e
        exception_write('xiaoqu_chengjiao_spider', xq_name)
        return
    content = soup.find('div', {'class': 'page-box house-lst-page-box'})
    total_pages = 0
    if content:
        d = "d=" + content.get('page-data')
        exec (d)
        total_pages = d['totalPage']

    threads = []
    for i in range(total_pages):
        url_page = u"http://bj.lianjia.com/chengjiao/pg%drs%s/" % (i + 1, urllib2.quote(xq_name))
        t = threading.Thread(target=chengjiao_spider, args=(db_cj, url_page))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def do_xiaoqu_chengjiao_spider(db_xq, db_cj):
    """
    批量爬取小区成交记录
    """
    count = 0
    xq_list = db_xq.fetchall()
    for xq in xq_list:
        xiaoqu_chengjiao_spider(db_cj, xq[0])
        count += 1
        print 'have spidered %d xiaoqu' % count
    print 'done'


def do_xiaoqu_sell_spider(db_xq, db_sl):
    """
    批量爬取小区在售记录
    """
    count = 0
    xq_list = db_xq.fetchall('select sellCount,url from xiaoqu')
    for xq in xq_list:
        if xq[0]==0:
            continue
        xiaoqu_selling_spider(db_sl, xq[1])
        count += 1
        print 'have spidered xiaoqu %d selling' % count
    print 'done'


def exception_write(fun_name, url):
    """
    写入异常信息到日志
    """
    lock.acquire()
    f = open('log.txt', 'a')
    line = "%s %s\n" % (fun_name, url)
    f.write(line)
    f.close()
    lock.release()


def exception_read():
    """
    从日志中读取异常信息
    """
    lock.acquire()
    f = open('log.txt', 'r')
    lines = f.readlines()
    f.close()
    f = open('log.txt', 'w')
    f.truncate()
    f.close()
    lock.release()
    return lines
    #return None


def exception_spider(db_xq,db_cj,db_sl):
    """
    重新爬取爬取异常的链接
    """
    count = 0
    excep_list = exception_read()
    while excep_list:
        all_size = len(excep_list)
        for excep in excep_list:
            try:
                excep = excep.strip()
                if excep == "":
                    continue
                excep_name, url = excep.split(" ", 1)
                if excep_name == "chengjiao_spider":
                    chengjiao_spider(db_xq, url)
                    count += 1
                elif excep_name == "xiaoqu_spider":
                    xiaoqu_spider(db_xq, url)
                    count += 1
                elif excep_name == "do_xiaoqu_spider":
                    do_xiaoqu_spider(db_xq, url)
                    count += 1
                elif excep_name == "xiaoqu_chengjiao_spider":
                    xiaoqu_chengjiao_spider(db_cj, url)
                    count += 1
                elif excep_name == "xiaoqu_selling_spider":
                    xiaoqu_selling_spider(db_sl, url)
                    count += 1
                elif excep_name == "selling_spider":
                    selling_spider(db_sl, url)
                    count += 1
                elif excep_name == "selling_detail_spider":
                    selling_detail_spider(db_sl, url)
                    count += 1
                else:
                    print "wrong format"
                print "have spidered %d exception url all %d" % (count, all_size)
            except Exception,e:
                print e
                exception_write(excep)
        excep_list = exception_read()
        count = 0
    print 'all done ^_^'


if __name__ == "__main__":
    command = "create table if not exists xiaoqu (name TEXT primary key UNIQUE, regionb TEXT, regions TEXT, style TEXT, year TEXT,price TEXT,sellCount TEXT,url TEXT)"
    db_xq = SQLiteWraper('lianjia-xq.db', command)

    command = "create table if not exists chengjiao (href TEXT primary key UNIQUE, name TEXT, style TEXT, area TEXT, orientation TEXT, floor TEXT, year TEXT, sign_time TEXT, unit_price TEXT, total_price TEXT,fangchan_class TEXT, school TEXT, subway TEXT)"
    db_cj = SQLiteWraper('lianjia-cj.db', command)

    command = "create table if not exists selling (href TEXT primary key UNIQUE, regionb TEXT,regions TEXT, name TEXT,distance TEXT, style TEXT,structure TEXT, area REAL, innerArea REAL, orientation TEXT, floor TEXT, year INTEGER,house_type TEXT, subway TEXT, sign_time TEXT, jiaoyi_qushu TEXT,last_sell_date TEXT, fangwu_yongtu TEXT, fangwu_nianxian TEXT, fengchan TEXT, diya TEXT, fengben TEXT, price REAL, unit_price REAL, title_main TEXT, title_sub TEXT)"
    db_sl = SQLiteWraper('lianjia-sl.db', command)

    # 爬下所有的小区信息
    for region in regions:
        do_xiaoqu_spider(db_xq, region)

    # 重新爬取爬取异常的链接,把小区抓取全了，再查询小区的成交或在售才不会有漏
    exception_spider(db_xq, db_cj, db_sl)

    # 爬下所有小区里的成交信息
    #do_xiaoqu_chengjiao_spider(db_xq, db_cj)

    do_xiaoqu_sell_spider(db_xq, db_sl)
    # 重新爬取爬取异常的链接
    exception_spider(db_xq,db_cj,db_sl)

