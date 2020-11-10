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

class PAPIProperty:
  def __init__(self, **kwargs):
    self.accountId = kwargs.get("accountId")
    self.contractId = kwargs.get("contractId")
    self.groupId = kwargs.get("groupId")
    self.propertyId = kwargs.get("propertyId")
    self.propertyName = kwargs.get("propertyName")
    self.latestVersion = kwargs.get("latestVersion")
    self.productionVersion = kwargs.get("productionVersion")
    self.stagingVersion = kwargs.get("stagingVersion")


class PAPIPropertyVersion:
  def __init__(self, **kwargs):
    self.accountId = kwargs.get("accountId")
    self.contractId = kwargs.get("contractId")
    self.groupId = kwargs.get("groupId")
    self.propertyId = kwargs.get("propertyId")
    self.propertyName = kwargs.get("propertyName")
    self.propertyVersion = kwargs.get("propertyVersion")
    self.etag = kwargs.get("etag")
    # When note is empty, it is not provided in the JSON payload
    # It is better for bossman to have a string always
    self.note = kwargs.get("note", "")
    self.productionStatus = kwargs.get("productionStatus")
    self.stagingStatus = kwargs.get("stagingStatus")

class PAPIPropertyVersionRuleTree:
  def __init__(self, **kwargs):
    self.accountId = kwargs.get("accountId")
    self.contractId = kwargs.get("contractId")
    self.groupId = kwargs.get("groupId")
    self.propertyId = kwargs.get("propertyId")
    self.propertyVersion = kwargs.get("propertyVersion")
    self.etag = kwargs.get("etag")
    self.rules = kwargs.get("rules")


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

  def get_property_id(self, propertyName):
    self.logger.debug("get_property_id propertyName={propertyName}".format(propertyName=propertyName))
    property_id = None
    response = self.session.post("/papi/v1/search/find-by-value", json={"propertyName": propertyName})
    versions = list(PAPIPropertyVersion(**item) for item in response.json().get("versions").get("items"))
    if len(versions) > 0:
      property_id = str(versions[0].propertyId)
    return property_id

  def get_property(self, propertyName) -> PAPIProperty:
    self.logger.debug("get_property propertyName={propertyName}".format(propertyName=propertyName))
    property_id = self.get_property_id(propertyName)
    if not property_id:
      return None
    response = self.session.get("/papi/v1/properties/{}".format(property_id))
    if response.status_code != 200:
      raise PAPIError(response.json())
    property_json = response.json().get("properties").get("items")[0]
    return PAPIProperty(**property_json)

  def get_latest_property_version(self, propertyId, network=None) -> PAPIPropertyVersion:
    self.logger.debug("get_latest_property_version propertyId={propertyId} network={network}".format(propertyId=propertyId, network=network))
    params = dict()
    if not network is None:
      params["activatedOn"] = network
    url = "/papi/v1/properties/{propertyId}/versions/latest".format(propertyId=propertyId)
    response = self.session.get(url, params=params)
    if response.status_code != 200:
      raise PAPIError(response.json())
    version_dict = response.json().get("versions").get("items")[0]
    return PAPIPropertyVersion(**version_dict)

  def get_property_version(self, propertyId, propertyVersion):
    self.logger.debug("get_property_version propertyId={propertyId} propertyVersion={propertyVersion}".format(propertyId=propertyId, propertyVersion=propertyVersion))
    url = "/papi/v1/properties/{propertyId}/versions/{propertyVersion}".format(propertyId=propertyId, propertyVersion=propertyVersion)
    response = self.session.get(url)
    version_dict = response.json().get("versions").get("items")[0]
    return PAPIPropertyVersion(**version_dict)

  def get_property_versions(self, propertyId, limit=500, offset=0):
    self.logger.debug("get_property_versions propertyId={propertyId} limit={limit} offset={offset}".format(propertyId=propertyId, limit=limit, offset=offset))
    params = dict(limit=str(limit), offset=str(offset))
    url = "/papi/v1/properties/{propertyId}/versions".format(propertyId=propertyId)
    response = self.session.get(url, params=params).json()
    meta_fields = dict((k, v) for (k, v) in response.items() if k in ("accountId", "contractId", "propertyId", "groupId", "propertyName"))
    versions = list({**meta_fields, **version} for version in response.get("versions").get("items"))
    return list(PAPIPropertyVersion(**version) for version in versions)

  def iter_property_versions(self, propertyId, predicate, pageSize=20):
    self.logger.debug("iter_property_versions propertyId={propertyId}".format(propertyId=propertyId))
    offset = 0
    while True:
      self.logger.debug("... iter_property_versions propertyId={propertyId} offset={offset}".format(propertyId=propertyId, offset=offset))
      versions = self.get_property_versions(propertyId, pageSize, offset)
      if len(versions) == 0:
        break
      for idx, version in enumerate(versions):
        if offset + idx > 10:
          return
        if predicate(version):
          yield version
      offset += pageSize
    return None

  def find_latest_property_version(self, propertyId, predicate, pageSize=500):
    self.logger.debug("find_latest_property_version propertyId={propertyId}".format(propertyId=propertyId))
    return next(self.iter_property_versions(propertyId, predicate, pageSize), None)

  def create_property(self, propertyName, productId, ruleFormat, contractId, groupId) -> str:
    self.logger.debug("create_property propertyName={propertyName} contractId={contractId} groupId={groupId}".format(propertyName=propertyName, contractId=contractId, groupId=groupId))
    url = "/papi/v1/properties"
    response = self.session.post(url, params=dict(contractId=contractId, groupId=groupId), json=dict(
      propertyName=propertyName,
      productId=productId,
      ruleFormat=ruleFormat,
      contractId=contractId,
      groupId=groupId,
    ))
    if response.status_code != 201:
      raise PAPIError(response.json())
    # Follow the Location header to the actual property
    response = self.session.get(response.headers["Location"])
    if response.status_code != 200:
      raise PAPIError(response.json())
    return response.json().get("properties").get("items")[0].get("propertyId")

  def create_property_version(self, propertyId, baseVersion, baseVersionEtag = None):
    self.logger.debug("create_property_version propertyId={propertyId} baseVersion={baseVersion}".format(propertyId=propertyId, baseVersion=baseVersion))
    data = dict(createFromVersion=baseVersion)
    if baseVersionEtag:
      data.update(createFromVersionEtag=baseVersionEtag)
    url = "/papi/v1/properties/{propertyId}/versions".format(propertyId=propertyId)
    response = self.session.post(url, json=data)
    link = response.json().get("versionLink")
    version = self.session.get(link).json().get("versions").get("items")[0]
    return PAPIPropertyVersion(**version)

  def update_property_rule_tree(self, propertyId, version, ruleTree):
    self.logger.debug("update_property_rule_tree propertyId={propertyId} version={version}".format(propertyId=propertyId, version=version))
    headers = {}
    if "ruleFormat" in ruleTree:
      headers["Content-Type"] = "application/vnd.akamai.papirules.{}+json".format(ruleTree.get("ruleFormat"))
    url = "/papi/v1/properties/{propertyId}/versions/{version}/rules".format(propertyId=propertyId, version=version)
    response = self.session.put(url, json=ruleTree, headers=headers)
    if response.status_code == 200:
      return PAPIPropertyVersionRuleTree(**response.json())
    raise PAPIError(response.json())

  def update_property_hostnames(self, propertyId, version, hostnames):
    self.logger.debug("update_property_hostnames propertyId={propertyId} version={version}".format(propertyId=propertyId, version=version))
    url = "/papi/v1/properties/{propertyId}/versions/{version}/hostnames".format(propertyId=propertyId, version=version)
    response = self.session.put(url, json=hostnames)
    if response.status_code == 200:
      return response.json()
    raise PAPIError(response.json())

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
    patience = 3 # number of points to print
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
        sys.stderr.write("\n")
        print(activation_statuses)
        return activation_statuses
      sys.stderr.write("\rpatience{}".format("." * patience))
      patience += 1
    return response.json()
