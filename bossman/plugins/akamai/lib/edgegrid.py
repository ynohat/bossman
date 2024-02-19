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

INVALID_TIMESTAMP_RETRIES, INVALID_TIMESTAMP_SLEEP = 2, 10

adapter = HTTPAdapter(
  pool_connections=1,
  pool_maxsize=10,
  max_retries=Retry(
    total=3,
    backoff_factor=5,
    status_forcelist=[429, 500, 502, 503, 504],
    method_whitelist=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"],
  ),
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

  def is_invalid_timestamp_error(self, response: requests.Response):
    if 'application/problem+json' in response.headers.get('Content-Type', ''):
      if response.status_code == 400:
        problem_details = response.json()
        return problem_details.get('detail') == 'Invalid timestamp'
    return False

  def request(self, method, url, params=None, headers=None, **kwargs):
    try:
      if self.switch_key:
        params = params if params else {}
        params.update(accountSwitchKey=self.switch_key)

      headers = headers if headers else {}
      headers['user-agent'] = USER_AGENT

      baseUrl = "https://{host}".format(host=self.edgerc.get(self.section, "host"))
      url = parse.urljoin(baseUrl, url)
      # This retry loop is in addition to the retry loop implemented using the urllib Retry
      # mechanism. As a consequence, if we get a combination of "normal", network-level or
      # semantic retryable errors and invalid timestamp errors, we might actually retry
      # more times than expected. The alternative is to write all the retry logic ourselves
      # which feels overkill.
      tries = INVALID_TIMESTAMP_RETRIES
      while True:
        tries -= 1
        response = super(Session, self).request(method, url, params=params, headers=headers, **kwargs)
        if response.status_code in (401, 403, *range(500, 600)):
          raise EdgegridError(response.json())
        elif self.is_invalid_timestamp_error(response):
          if tries > 0:
            time.sleep(INVALID_TIMESTAMP_SLEEP)
            continue
          raise EdgegridError(response.json())
        return response
    except RetryError as e:
      raise EdgegridError(str(e))
