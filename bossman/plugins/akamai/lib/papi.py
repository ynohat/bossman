import json
import time
import sys
from functools import lru_cache
from bossman.plugins.akamai.lib.edgegrid import Session
from bossman.logging import get_class_logger
from bossman.cache import cache
from bossman.errors import BossmanError

_cache = cache.key(__name__)

class PAPIError(BossmanError):
  pass

class PAPIBulkActivation:
  def __init__(self):
    self.payload = dict(
      defaultActivationSettings=dict(
        acknowledgeAllWarnings=True,
        useFastFallback=False,
        fastPush=True,
        complianceRecord=dict(
          nonComplianceReason="NO_PRODUCTION_TRAFFIC",
        )
      ),
      activatePropertyVersions=[]
    )

  @property
  def length(self):
    return len(self.payload.get("activatePropertyVersions", []))

  def add(self, property_id, property_version, network, notifyEmails):
    self.payload.get("activatePropertyVersions").append(dict(
      propertyId=property_id,
      propertyVersion=property_version,
      network=network,
      notifyEmails=notifyEmails,
    ))

  def __str__(self):
    return json.dumps(self.payload)

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
      if len(versions) > 0:
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
    response = self.session.get(url, params=params).json()
    meta_fields = dict((k, v) for (k, v) in response.items() if isinstance(v, (str, int)))
    versions = list({**meta_fields, **version} for version in response.get("versions").get("items"))
    return versions

  def find_latest_property_version(self, propertyId, predicate, pageSize=100, maxOffset=20):
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

  @lru_cache(maxsize=1000) # don't fetch more than once per session, even if the rule format wasn't persistently cacheable
  def get_rule_format_schema(self, productId, ruleFormat):
    self.logger.debug("get_rule_format_schema productId={} version={}".format(productId, ruleFormat))
    cache = _cache.key("schema", "rule_format", productId, ruleFormat)
    schema = cache.get_json()
    if schema is None:
      url = "/papi/v1/schemas/products/{productId}/{ruleFormat}".format(productId=productId, ruleFormat=ruleFormat)
      response = self.session.get(url)
      schema = response.json()
      if ruleFormat != "latest":
        cache.update_json(schema)
    return schema

  def get_request_schema(self, request_filename):
    self.logger.debug("get_request_schema filename={request_filename}".format(request_filename=request_filename))
    cache = _cache.key("schema", "request", request_filename)
    schema = cache.get_json()
    if schema is None:
      url = "/papi/v1/schemas/request/{request_filename}".format(request_filename=request_filename)
      response = self.session.get(url)
      schema = response.json()
      cache.update_json(schema)
    return schema

  def bulk_activate(self, bulkActivation: PAPIBulkActivation):
    self.logger.debug("bulk_activate bulkActivation={}".format(bulkActivation))
    url = "/papi/v1/bulk/activations"
    response = self.session.post(url, json=bulkActivation.payload)
    if response.status_code != 202:
      raise PAPIError(response.text)
    response_json = response.json()
    bulkActivationUrl = response_json.get("bulkActivationLink")
    while True:
      time.sleep(2)
      status_response = self.session.get(bulkActivationUrl)
      status_response_json = status_response.json()
      if status_response_json.get("bulkActivationStatus") == "COMPLETE":
        activation_statuses = dict((apv.get("propertyName"), dict(
          activationStatus=apv.get("activationStatus"),
          taskStatus=apv.get("taskStatus"),
          propertyId=apv.get("propertyId"),
          propertyVersion=apv.get("propertyVersion"),
          network=apv.get("network"),
          fatalError=apv.get("fatalError", '{}')
        )) for apv in status_response_json.get("activatePropertyVersions"))
        return activation_statuses
      print("patience...\r", file=sys.stderr)
    return response.json()
