import json
from functools import lru_cache
from bossman.plugins.akamai.lib.edgegrid import Session
from bossman.logging import get_class_logger
from bossman.cache import cache

_cache = cache.key(__name__)

class PAPIClient:
  def __init__(self, edgerc, section, switch_key=None, **kwargs):
    self.logger = get_class_logger(self)
    self.session = Session(edgerc, section, switch_key=switch_key, **kwargs)

  @lru_cache(maxsize=1000)
  def find_by_property_name(self, propertyName):
    self.logger.debug("find_by_property_name propertyName={propertyName}".format(propertyName=propertyName))
    response = self.session.post("/papi/v1/search/find-by-value", json={"propertyName": propertyName})
    self.logger.debug("find_by_property_name response={response}".format(response=response.content))
    versions = response.json().get("versions").get("items")
    return versions

  def get_property_id(self, propertyName):
    self.logger.debug("get_property_id propertyName={propertyName}".format(propertyName=propertyName))
    cache = _cache.key("property_id", propertyName)
    property_id = cache.get_str()
    if property_id is None:
      versions = self.find_by_property_name(propertyName)
      if len(versions) == 1:
        property_id = str(versions[0].get("propertyId"))
        cache.update(property_id)
    return property_id

  def get_latest_property_version(self, propertyId, network=None):
    self.logger.debug("get_latest_property_version propertyId={propertyId} network={network}".format(propertyId=propertyId, network=network))
    params = dict()
    if not network is None:
      params["activatedOn"] = network
    url = "/papi/v1/properties/{propertyId}/versions/latest".format(propertyId=propertyId)
    response = self.session.get(url, params=params)
    return response.json().get("versions").get("items")[0]

  def get_property_versions(self, propertyId, limit=500, offset=0):
    self.logger.debug("get_property_versions propertyId={propertyId} limit={limit} offset={offset}".format(propertyId=propertyId, limit=limit, offset=offset))
    params = dict(limit=str(limit), offset=str(offset))
    url = "/papi/v1/properties/{propertyId}/versions".format(propertyId=propertyId)
    response = self.session.get(url, params=params)
    return response.json().get("versions").get("items")

  def find_latest_property_version(self, propertyId, predicate, pageSize=5, maxOffset=20):
    self.logger.debug("find_latest_property_version propertyId={propertyId}".format(propertyId=propertyId))
    offset = 0
    while offset < maxOffset:
      self.logger.debug("... find_latest_property_version propertyId={propertyId} offset={offset}".format(propertyId=propertyId, offset=offset))
      versions = self.get_property_versions(propertyId, pageSize, offset)
      if len(versions) == 0:
        break
      try:
        return next(version for version in versions if predicate(version))
      except StopIteration:
        offset += pageSize
        continue
    return None

  def create_property_version(self, propertyId, baseVersion, baseVersionEtag = None):
    self.logger.debug("create_property_version propertyId={propertyId} baseVersion={baseVersion}".format(propertyId=propertyId, baseVersion=baseVersion))
    data = dict(createFromVersion=baseVersion)
    if baseVersionEtag:
      data.update(createFromVersionEtag=baseVersionEtag)
    url = "/papi/v1/properties/{propertyId}/versions".format(propertyId=propertyId)
    response = self.session.post(url, json=data)
    link = response.json().get("versionLink")
    return self.session.get(link).json().get("versions").get("items")[0]

  def update_property_rule_tree(self, propertyId, version, ruleTree):
    self.logger.debug("update_property_rule_tree propertyId={propertyId} version={version}".format(propertyId=propertyId, version=version))
    headers = {}
    if "ruleFormat" in ruleTree:
      headers["Content-Type"] = "application/vnd.akamai.papirules.{}+json".format(ruleTree.get("ruleFormat"))
    url = "/papi/v1/properties/{propertyId}/versions/{version}/rules".format(propertyId=propertyId, version=version)
    response = self.session.put(url, json=ruleTree, headers=headers)
    return response.json()

  def update_property_hostnames(self, propertyId, version, hostnames):
    self.logger.debug("update_property_hostnames propertyId={propertyId} version={version}".format(propertyId=propertyId, version=version))
    url = "/papi/v1/properties/{propertyId}/versions/{version}/hostnames".format(propertyId=propertyId, version=version)
    response = self.session.put(url, json=hostnames)
    return response.json()
