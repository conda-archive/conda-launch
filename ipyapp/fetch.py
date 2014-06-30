__author__ = 'ijstokes'

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

import requests

from urlparse import urlparse

class NotAvailableError(Exception):
    " Indicates a URL resource could not be fetched "
    pass

def fetch_gist(gistid):
    " Fetch Github GIST to a file "
    fn = "%s.ipynb" % gistid
    url = "http://github.com/gist/%s" % gistid # TODO: not the correct URL
    try:
        r  = requests.get(url)
    except requests.ConnectionError:
        raise NotAvailableError('Cannot access URL %s' % url)
    with open(fn, 'w') as fh:
        fh.write(r.content)
    return fn

def fetch_url(url):
    " Fetch URL to implied file name "
    url_obj = urlparse(url)
    fn = url_obj.path.split('/')[-1]
    try:
        r  = requests.get(url)
    except requests.ConnectionError:
        raise NotAvailableError('Cannot access URL %s' % url)
    with open(fn, 'w') as fh:
        fh.write(r.content)
    return fn