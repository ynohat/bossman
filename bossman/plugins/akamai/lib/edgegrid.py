import random
import sys, os
import time
import requests
from requests.adapters import HTTPAdapter, RetryError
from urllib3.util.retry import Retry, MaxRetryError
from akamai.edgegrid import EdgeGridAuth, EdgeRc
from configparser import NoSectionError, NoOptionError
from bossman import logging, USER_AGENT
from bossman.logging import logger
from bossman.errors import BossmanError

py3 = sys.version_info[0] >= 3
if py3:
  from configparser import ConfigParser
  from urllib import parse
else:
  import ConfigParser
  # pylint: disable=import-error
  import urlparse as parse

class EdgegridError(BossmanError):
  pass

adapter = HTTPAdapter(
  pool_connections=1,
  pool_maxsize=10,
)

class Session(logging.RequestsLoggingSession):
  def __init__(self, edgerc, section, switch_key=None, **kwargs):
    try:
      super(Session, self).__init__(**kwargs)
      self.edgerc = EdgeRc(edgerc)
      self.section = section
      self.switch_key = None
      if self.edgerc.has_option(section, "account_key"):
        self.switch_key = self.edgerc.get(section, "account_key")
      if switch_key != None:
        self.switch_key = switch_key
      self.auth = EdgeGridAuth(
        client_token=self.edgerc.get(section, "client_token"),
        client_secret=self.edgerc.get(section, "client_secret"),
        access_token=self.edgerc.get(section, "access_token"),
      )
      self.mount("https://", adapter)
      self.mount("http://", adapter)
    except NoSectionError as e:
      raise EdgegridError(e.message)
    except NoOptionError as e:
      raise EdgegridError(e.message)

  def is_retryable(self, method: str, response: requests.Response):
    if not method in ("HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"):
      return False
    if 'application/problem+json' in response.headers.get('Content-Type', ''):
      if response.status_code == 400:
        problem_details = response.json()
        return problem_details.get('detail') == 'Invalid timestamp'
    return response.status_code in (429, 500, 502, 503, 504)

  def request(self, method, url, params=None, headers=None, **kwargs):
    if self.switch_key:
      params = params if params else {}
      params.update(accountSwitchKey=self.switch_key)

    headers = headers if headers else {}
    headers['user-agent'] = USER_AGENT

    baseUrl = "https://{host}".format(host=self.edgerc.get(self.section, "host"))
    url = parse.urljoin(baseUrl, url)
    # We cannot use the standard urllib3 retry mechansim because it simply retries the requests as-is,
    # with the same authorization headers. With edgegrid the auth headers may be invalid before we have
    # finished retrying, yielding "Invalid Timestamp" 400 errors.
    # https://github.com/psf/requests/issues/5975
    tries, max_tries, wait = 1, 5, 1
    while tries <= max_tries:
      response = super(Session, self).request(method, url, params=params, headers=headers, **kwargs)
      if not response.ok:
        if self.is_retryable(method, response):
          time.sleep(wait)
          wait = wait * 2 ** tries + random.uniform(0, 1)
        elif int(response.status_code) // 100 == 4:
          # input errors should be handled by the caller
          return response
        else:
          raise EdgegridError(response.json())
      else:
        return response
    raise EdgegridError('max retries exceeded')
