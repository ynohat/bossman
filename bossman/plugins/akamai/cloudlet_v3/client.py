from datetime import datetime
import dateutil.parser
from typing import List
from cattr import Converter

from bossman.logging import get_class_logger
from bossman.plugins.akamai.lib.edgegrid import Session
from .data import *
from .error import *

class CloudletAPIV3Client:
  def __init__(self, edgerc, section, switch_key=None, **kwargs):
    self.logger = get_class_logger(self)
    self.session = Session(edgerc, section, switch_key=switch_key, **kwargs)
    self.converter = Converter()
    self.converter.register_structure_hook(datetime, lambda d, t: dateutil.parser.isoparse(d))

  def get_policy_by_name(self, name):
    self.logger.debug("get_policy_by_name name={name}".format(name=name))
    id = None
    policies = self.get_policies()
    for policy in policies:
      if policy.name == name:
        return policy
    raise PolicyNameNotFound(name)

  def get_policies(self) -> List[SharedPolicy]:
    self.logger.debug("get_policies")
    response = self.session.get("/cloudlets/v3/policies")
    if response.status_code != 200:
      raise CloudletAPIV3Error(response.json())
    # import json
    # print(json.dumps(response.json(), indent=2))
    response = self.converter.structure(response.json(), GetPoliciesResponse)
    return response.content

  def get_policy_version(self, policyId: int, policyVersion: int) -> SharedPolicyVersion:
    self.logger.debug("get_policy_version policyId={policyId}, policyVersion={policyVersion}".format(policyId=policyId, policyVersion=policyVersion))
    response = self.session.get("/cloudlets/v3/policies/{policyId}/versions/{policyVersion}".format(policyId=policyId, policyVersion=policyVersion))
    if response.status_code != 200:
      raise CloudletAPIV3Error(response.json())
    return self.converter.structure(response.json(), SharedPolicyVersion)

  def get_latest_policy_version(self, policyId: int) -> Optional[SharedPolicyVersion]:
    self.logger.debug("get_policy_version policyId={policyId}".format(policyId=policyId))
    response = self.session.get("/cloudlets/v3/policies/{policyId}/versions".format(policyId=policyId), params=dict(size=10))
    if response.status_code != 200:
      raise CloudletAPIV3Error(response.json())
    policy_versions = self.converter.structure(response.json(), GetPolicyVersionsResponse)
    if len(policy_versions.content):
      return policy_versions.content[0]
    return None

  def get_latest_policy_versions(self, policyId: int, count: int) -> List[SharedPolicyVersion]:
    self.logger.debug("get_latest_policy_versions policyId={policyId}, count={count}".format(policyId=policyId, count=count))
    response = self.session.get("/cloudlets/v3/policies/{policyId}/versions".format(policyId=policyId), params=dict(size=count))
    if response.status_code != 200:
      raise CloudletAPIV3Error(response.json())
    policy_versions = self.converter.structure(response.json(), GetPolicyVersionsResponse)
    return policy_versions.content

  def create_policy(self, policyName: str, description: str, cloudletType: SharedPolicyCloudletType, groupId: int) -> SharedPolicy:
    self.logger.debug("create_policy policyName={policyName}".format(policyName=policyName))
    response = self.session.post("/cloudlets/v3/policies", json=dict(
      name=policyName,
      cloudletType=cloudletType.value,
      groupId=groupId,
      description=description,
    ))
    if response.status_code != 201:
      raise CloudletAPIV3Error(response.json())
    return self.converter.structure(response.json(), SharedPolicy)

  def update_policy(self, policyId: int, description: str, groupId: int) -> SharedPolicy:
    self.logger.debug("update_policy policyName={policyId}".format(policyId=policyId))
    response = self.session.put("/cloudlets/v3/policies/{policyId}".format(policyId=policyId), json=dict(
      groupId=groupId,
      description=description,
    ))
    if response.status_code != 202:
      raise CloudletAPIV3Error(response.json())
    return self.converter.structure(response.json(), SharedPolicy)

  def create_policy_version(self, policyId: int, description: str, matchRules: List[dict]) -> SharedPolicyVersion:
    self.logger.debug("create_policy_version policyId={policyId}".format(policyId=policyId))
    response = self.session.post("/cloudlets/v3/policies/{policyId}/versions".format(policyId=policyId), json=dict(
      description=description,
      matchRules=matchRules,
    ))
    if response.status_code != 201:
      raise CloudletAPIV3Error(response.json())
    return self.converter.structure(response.json(), SharedPolicyVersion)

  def activate_policy_version(self, policyId: int, policyVersion: int, network: Network) -> SharedPolicyActivation:
    self.logger.debug("activate_policy_version policyId={policyId}, policyVersion={policyVersion}".format(policyId=policyId, policyVersion=policyVersion))
    response = self.session.post("/cloudlets/v3/policies/{policyId}/activations".format(policyId=policyId), json=dict(
      network=network.value,
      operation=SharedPolicyActivationOperation.ACTIVATION.value,
      policyVersion=policyVersion,
    ))
    if response.status_code != 202:
      result = response.json().get('errors')[0]
      raise CloudletAPIV3Error(result.get('detail'))
    return self.converter.structure(response.json(), SharedPolicyActivation)

  def get_policy_version_activation_status(self, activation: SharedPolicyActivation) -> SharedPolicyActivation:
    self.logger.debug("get_policy_version_activation_status policyId={policyId}, activationId={activationId}".format(policyId=activation.policyId, activationId=activation.id))
    response = self.session.get("/cloudlets/v3/policies/{policyId}/activations/{activationId}".format(policyId=activation.policyId, activationId=activation.id))
    if response.status_code != 200:
      raise CloudletAPIV3Error(response.json())
    return self.converter.structure(response.json(), SharedPolicyActivation)
