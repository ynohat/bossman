import json
import time
import sys
from functools import lru_cache
from bossman.plugins.akamai.lib.edgegrid import Session
from bossman.logging import get_class_logger
from bossman.cache import cache
from bossman.errors import BossmanError

_cache = cache.key(__name__)

class HAPIError(BossmanError):
  pass
class HAPIValidationError(HAPIError):
  pass
class HAPIEdgeHostname(object):
  def __init__(self, chinaCdn, comments, dnsZone, edgeHostnameId, ipVersionBehavior, map, productId, recordName, securityType, serialNumber, ttl, useDefaultMap, useDefaultTtl):
    self.chinaCdn = chinaCdn
    self.comments = comments
    self.dnsZone = dnsZone
    self.edgeHostnameId = edgeHostnameId
    self.ipVersionBehavior = ipVersionBehavior
    self.map = map
    self.productId = productId
    self.recordName = recordName
    self.securityType = securityType
    self.serialNumber = serialNumber
    self.ttl = ttl
    self.useDefaultMap = useDefaultMap
    self.useDefaultTtl = useDefaultTtl

  def __str__(self):
    return self.__class__.__qualname__ + ': ' + ' '.join(f'{k}={json.dumps(v)}' for k,v in self.__dict__.items())

class HAPIClient:
  def __init__(self, edgerc, section, switch_key=None, **kwargs):
    self.logger = get_class_logger(self)
    self.session = Session(edgerc, section, switch_key=switch_key, **kwargs)

  def get_edgehostnames(self, recordNameSubstring=None, dnsZone=None):
    self.logger.debug(f'get_edgehostnames recordNameSubstring={recordNameSubstring} dnsZone={dnsZone}')
    params = dict()
    if recordNameSubstring != None:
      params['recordNameSubstring'] = recordNameSubstring
    if dnsZone != None:
      params['dnsZone'] = dnsZone
    response = self.session.get("/hapi/v1/edge-hostnames", params=params)
    edgeHostnames = []
    if response.status_code == 200:
      edgeHostnames = list(HAPIEdgeHostname(**item) for item in response.json().get("edgeHostnames", []))
    return edgeHostnames

  def get_edgehostname_by_record_name_and_zone(self, recordName, dnsZone):
    self.logger.debug(f'get_edgehostname_by_record_name_and_zone recordName={recordName} dnsZone={dnsZone}')
    edgeHostnames = list(
      edgeHostname
      for edgeHostname
      in self.get_edgehostnames(recordNameSubstring=recordName, dnsZone=dnsZone)
      if edgeHostname.recordName == recordName
      and edgeHostname.dnsZone == dnsZone
    )
    return edgeHostnames[0] if len(edgeHostnames) > 0 else None

if __name__ == '__main__':
  hc = HAPIClient('/Users/ahogg/.edgerc', 'default', switch_key='B-C-1ED34DK%3A1-8BYUX')
  ehn = hc.get_edgehostname_by_record_name_and_zone('ahogg-shared-cert-a2s2', 'akamaized.net')
  print(ehn)