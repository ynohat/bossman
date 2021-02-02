import sys, os
import requests
from akamai.edgegrid import EdgeGridAuth, EdgeRc
from configparser import NoSectionError, NoOptionError
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

class Session(requests.Session):
  def __init__(self, edgerc, section, switch_key=None, **kwargs):
    try:
      super(Session, self).__init__(**kwargs)
      self.edgerc = EdgeRc(edgerc)
      self.section = section
      self.switch_key = switch_key
      self.auth = EdgeGridAuth(
        client_token=self.edgerc.get(section, "client_token"),
        client_secret=self.edgerc.get(section, "client_secret"),
        access_token=self.edgerc.get(section, "access_token"),
      )
    except NoSectionError as e:
      raise EdgegridError(e.message)
    except NoOptionError as e:
      raise EdgegridError(e.message)

  def request(self, method, url, params=None, **kwargs):
    if self.switch_key:
      params = params if params else {}
      params.update(accountSwitchKey=self.switch_key)
    baseUrl = "https://{host}".format(host=self.edgerc.get(self.section, "host"))
    url = parse.urljoin(baseUrl, url)
    response = super(Session, self).request(method, url, params=params, **kwargs)
    if response.status_code in (401, 403, *range(500, 600)):
      raise EdgegridError(response.json())
    return response
