#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#                   GNU GENERAL PUBLIC LICENSE
#                       Version 2, June 1991
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; see the file COPYING.  If not, write to
# the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# 
#
# version-0.0.1
#   depend 3rd lib: pycurl, BeautifulSoup4
#   offline files from github.com
#
import sys
import os
import re
import getopt
import glob
import time
import json
import pycurl

from io import BytesIO
from urllib.parse import urlparse
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from hashlib import sha1

#
# example:
#   https://github.com/Xilinx/linux-xlnx/tree/master/drivers/net/can
#
# convert web to raw:
#   https://github.com/Xilinx/linux-xlnx/blob/master/drivers/net/can/rx-offload.c
#   https://github.com/Xilinx/linux-xlnx/raw/master/drivers/net/can/rx-offload.c
#

def file_get_content(fn):
    f = open(fn, 'r', encoding='UTF-8')
    d = f.read()
    f.close()
    return d

def file_put_content(fn, d):
    f = open(fn, 'w', encoding='UTF-8')
    f.write(d)
    f.close()

def file_get_binary(fn):
    f = open(fn, 'rb')
    d = f.read()
    f.close()
    return d

def file_put_binary(fn, d):
    f = open(fn, 'wb')
    f.write(d)
    f.close()

def fetch_github_page(curl, url):
    key = sha1(url.encode('UTF-8')).hexdigest()
    fn = os.path.join('cache', key)
    if os.path.isfile(fn):
        return file_get_binary(fn)

    buf = BytesIO()
    curl.setopt(pycurl.WRITEFUNCTION, buf.write)
    curl.setopt(pycurl.URL, url)

    print('> URL:', url)
    curl.perform()
    if curl.getinfo(pycurl.HTTP_CODE) == 200:
        size = int(curl.getinfo(pycurl.SIZE_DOWNLOAD))
        kb = size//1024
        mb = kb//1024
        if mb > 0:
            size_str = '%.3f Mb' % (kb / 1024)
        elif kb > 0:
            size_str = '%.3f Kb' % (size / 1024)
        else:
            size_str = '%d bytes' % size

        page = buf.getvalue()
        file_put_binary(fn, page)
        buf.close()
    else:
        print('< HTTP %d' % curl.getinfo(pycurl.HTTP_CODE))
        page = None
        buf.close()

    return page

def parse_github_page(url, html):
    info = urlparse(url)

    soup = BeautifulSoup(html, 'lxml')

    res = soup.find('table', {'class':'files'})
    if res is None:
        print('Error: expect <table class="files", but found nothing')
        return None

    lst_cells = res.find_all('td', {'class':'icon'})
    if lst_cells is None:
        return None

    l = []
    for td in lst_cells:
        svg = td.find('svg')
        label = svg.get('aria-label')
        if label != 'directory' and label != 'file':
            continue

        content = td.parent.find('td', {'class':'content'})
        if content is None:
            continue
        a = content.find('a')
        if a is None:
            continue
        name = a.get('title')
        url  = a.get('href')

        if url.startswith('/'):
            url = '%s://%s%s' % (info.scheme, info.netloc, url)

        l.append((label, name, url))

    lst_directories = list(filter(lambda v:v[0] == 'directory', l))
    lst_files = list(filter(lambda v:v[0] == 'file', l))

    return (lst_directories, lst_files)


if __name__ == '__main__':
    opts, args = getopt.getopt(sys.argv[1:], 'o:')

    outdir = 'download'
    for k, v in opts:
        if k == '-o':
            outdir = v

    ########################################################
    if not os.path.isdir('cache'):
        os.mkdir('cache')

    if not os.path.isdir(outdir):
        os.mkdir(outdir)

    curl = pycurl.Curl()
    #curl.setopt(pycurl.VERBOSE, 1)
    curl.setopt(pycurl.SSL_VERIFYPEER, 0)   
    curl.setopt(pycurl.SSL_VERIFYHOST, 0)
    curl.setopt(pycurl.FOLLOWLOCATION, 1)

    ########################################################
    url = args[0]
    print('Info: analysis %s' % url)

    page = fetch_github_page(curl, url)
    if page is None:
        print('Can not fetch url', url)
        sys.exit(0)

    page = page.decode('UTF-8')
    res = parse_github_page(url, page)
    if res is None:
        print('Found nothing')
        sys.exit(0)

    lst_directories = []
    lst_files = []

    for label, name, url in res[0]:
        lst_directories.append(('.', name, url))

    for label, name, url in res[1]:
        lst_files.append(('.', name, url))

    while len(lst_directories) > 0:
        path, name, url = lst_directories.pop(0)
        page = fetch_github_page(curl, url)
        if page is None:
            continue

        page = page.decode('UTF-8')
        res = parse_github_page(url, page)
        if res is None:
            continue

        loc = os.path.join(path, name)

        for label, name, url in res[0]:
            lst_directories.append((loc, name, url))

        for label, name, url in res[1]:
            lst_files.append((loc, name, url))

    print('Info: found %d files' % len(lst_files))

    nr_bytes = 0
    for path, name, url in lst_files:
        if path.startswith('.\\'):
            path = path[2:]
        elif path.startswith('.'):
            path = path[1:]

        outpath = os.path.join(outdir, path)
        if path != '.' and not os.path.isdir(outpath):
            os.mkdir(outpath)

        #-----------------------------------------------
        info = urlparse(url)
        tokens = info.path.split('/')
        if tokens[3] == 'blob':
            tokens[3] = 'raw'
        path = '/'.join(tokens)
        rawurl = '%s://%s%s' % (info.scheme, info.netloc, path)

        page = fetch_github_page(curl, rawurl)
        nr_bytes = nr_bytes + len(page)

        #-----------------------------------------------
        fn = os.path.join(outpath, name)
        print('  write:', fn)
        file_put_binary(fn, page)

    if nr_bytes // (1024 * 1024) > 0:
        print('Info: wrote %.3f Mb' % (nr_bytes / (1024*1024)))
    elif nr_bytes // 1024 > 0:
        print('Info: wrote %.3f Kb' % (nr_bytes / 1024))
    else:
        print('Info: wrote %d bytes' % nr_bytes)

    print('Info: wrote "%s/files.json"' % outdir)
    file_put_content(os.path.join(outdir, 'files.json'), json.dumps(lst_files, indent=4))


