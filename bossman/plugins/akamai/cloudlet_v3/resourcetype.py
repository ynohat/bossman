from collections import defaultdict
import json
import random
import re
from os.path import expanduser
import time
from types import SimpleNamespace
from typing import List
from bossman.cache import cache
from bossman.errors import BossmanError, BossmanValidationError
from bossman.abc import ResourceTypeABC
from bossman.abc import ResourceABC
from bossman.abc import ResourceApplyResultABC
from bossman.config import ResourceTypeConfig
from bossman.plugins.akamai.cloudlet_v3 import CloudletAPIV3Client, CloudletAPIV3Error
from bossman.plugins.akamai.cloudlet_v3.data import Network, SharedPolicyActivationStatus, SharedPolicyAsCode, SharedPolicyVersion
from bossman.plugins.akamai.cloudlet_v3.error import PolicyNameNotFound, PolicyVersionValidationError
from bossman.plugins.akamai.cloudlet_v3.resource import SharedPolicyResource
from bossman.plugins.akamai.cloudlet_v3.schema import validate_policy_version
from bossman.plugins.akamai.cloudlet_v3.ui import SharedPolicyApplyResult, SharedPolicyStatus, SharedPolicyVersionStatus
from bossman.plugins.akamai.lib.edgegrid import EdgegridError
from bossman.plugins.akamai.utils import GenericVersionComments
from bossman.repo import Repo, Revision, RevisionDetails

RE_COMMIT = re.compile("^commit: ([a-z0-9]*)", re.MULTILINE)


class CloudletError(BossmanError):
  pass

class ResourceTypeOptions:
  def __init__(self, options):
    from os import environ
    self.env_prefix = options.get("env_prefix", "")
    self.edgerc = expanduser(environ.get("%sEDGERC" % self.env_prefix, options.get("edgerc", "~/.edgerc")))
    self.section = environ.get("%sEDGERC_SECTION" % self.env_prefix, options.get("section", "papi"))
    self.switch_key = environ.get("%sEDGERC_SWITCH_KEY" % self.env_prefix, options.get("switch_key", None))

class ResourceType(ResourceTypeABC):
  def __init__(self, repo: Repo, config: ResourceTypeConfig):
    super(ResourceType, self).__init__(repo, config)
    self.options = ResourceTypeOptions(config.options)
    self.client = CloudletAPIV3Client(self.options.edgerc, self.options.section, self.options.switch_key)

  def create_resource(self, path: str, **kwargs):
    return SharedPolicyResource(path, **kwargs)

  def get_resource_status(self, resource: SharedPolicyResource):
    try:
      policy = self.client.get_policy_by_name(resource.name)

      production_activations = dict()
      staging_activations = dict()
      interesting_versions = set()

      if policy is not None:
        if policy.currentActivations.production.latest != None:
          interesting_versions.add(policy.currentActivations.production.latest.policyVersion)
          production_activations[policy.currentActivations.production.latest.policyVersion] = policy.currentActivations.production.latest
        if policy.currentActivations.production.effective != None:        
          interesting_versions.add(policy.currentActivations.production.effective.policyVersion)
          production_activations[policy.currentActivations.production.effective.policyVersion] = policy.currentActivations.production.effective
        if policy.currentActivations.staging.latest != None:
          interesting_versions.add(policy.currentActivations.staging.latest.policyVersion)
          staging_activations[policy.currentActivations.staging.latest.policyVersion] = policy.currentActivations.staging.latest
        if policy.currentActivations.staging.effective != None:        
          interesting_versions.add(policy.currentActivations.staging.effective.policyVersion)
          staging_activations[policy.currentActivations.staging.effective.policyVersion] = policy.currentActivations.staging.effective
        latest_version = self.client.get_latest_policy_version(policy.id)
        latest_versions = []
        if len(interesting_versions):
          window = max(latest_version.version - min(interesting_versions) + 1, 10)
          latest_versions = self.client.get_latest_policy_versions(policy.id, window)
        elif latest_version != None:
          latest_versions = [latest_version]
        if latest_version != None:
          interesting_versions.add(latest_version.version)
      return SharedPolicyStatus(self.repo, resource, [
          SharedPolicyVersionStatus(
            self.repo,
            resource,
            v,
            production_activations.get(v.version, None),
            staging_activations.get(v.version, None)
          )
          for v in latest_versions
          if v.version in interesting_versions
        ],
        exists=True
      )
    except CloudletAPIV3Error as e:
      return SharedPolicyStatus(self.repo, resource, [], exists=False, error=e)

  def is_pending(self, resource: SharedPolicyResource, revision: Revision):
    notes = revision.get_notes(resource.path)
    if notes.get("has_errors", False):
      return False
    return not self.is_applied(resource, revision)

  def is_applied(self, resource: SharedPolicyResource, revision: Revision):
    notes = revision.get_notes(resource.path)
    policy_version = notes.get("policy_version", None)
    return policy_version is not None

  def get_revision_details(self, resource: SharedPolicyResource, revision: Revision) -> RevisionDetails:
    notes = revision.get_notes(resource.path)
    policy_version = notes.get("policy_version", None)
    return RevisionDetails(id=revision.id, details="v"+str(policy_version) if policy_version else None)

  def apply_change(self, resource: SharedPolicyResource, revision: Revision, previous_revision: Revision) -> ResourceApplyResultABC:
    # we should only call this function if the Revision concerns the resource
    assert len(set(resource.paths).intersection(revision.affected_paths)) > 0

    notes = SimpleNamespace(
      policy_id=None,
      policy_version=None,
      has_errors=False
    )

    try:

      try:
        # Get the policy json from the commit
        policy_data = revision.show_path(resource.policy_path, textconv=True)
        if policy_data is None:
          raise PolicyVersionValidationError("missing policy version JSON")
        policy_data = json.loads(policy_data)
        # before changing anything in API, check that the json files are valid
        validate_policy_version(policy_data)
        policy_data: SharedPolicyAsCode = self.client.converter.structure(policy_data, SharedPolicyAsCode)
      except PolicyVersionValidationError as e:
        notes.has_errors = True
        raise e

      try:
        # If the policy exists, retrieve it
        policy = self.client.get_policy_by_name(resource.name)
      except PolicyNameNotFound:
        # Otherwise, create it
        policy = self.client.create_policy(resource.name, policy_data.description, policy_data.cloudletType, policy_data.groupId)

      policy_version = self.client.create_policy_version(
        policy.id,
        str(GenericVersionComments.from_revision(revision)),
        policy_data.matchRules
      )

      notes.policy_id = policy.id
      notes.policy_version = policy_version.version

      return SharedPolicyApplyResult(resource, revision, policy_version)
    except RuntimeError as e:
        return SharedPolicyApplyResult(resource, revision, error=e)
    finally:
      # Finally, assign the updated values to the git notes
      revision.get_notes(resource.path).set(**vars(notes))

  def validate_working_tree(self, resource: SharedPolicyResource):
    try:
      with open(resource.policy_path, "r") as fd:
        policy_data = json.loads(fd.read())
        validate_policy_version(policy_data)
    except (NotADirectoryError, FileNotFoundError) as e:
      raise PolicyVersionValidationError("file not found {}".format(e.filename))

  def _release(self, network: Network, resource: SharedPolicyResource, revision: Revision, on_update: callable = lambda resource, status, progress: None):
    notes = revision.get_notes(resource.path)
    policy_id = notes.get("policy_id")
    if not policy_id:
      policy_id = self.client.get_policy_by_name(resource.name).id
    policy_version = notes.get("policy_version")
    if not policy_id:
      on_update(resource, "[magenta]Policy does not exist[/]", None)
      return
    if not policy_version:
      on_update(resource, "[magenta]Revision not deployed[/]", 1)
      return
    if notes.get("has_errors") == True:
      on_update(resource, ":boom: [grey53]v{:<3}[/] Policy version has validation errors".format(policy_version), 1)
      return

    describe = lambda activation_status: "[{}]{}[/] [grey53]v{:<3}[/] [bright_white]{}[/]".format(network.color, network.alias, policy_version, activation_status)

    try:
      on_update(resource, describe("STARTING"), None)
      activation = self.client.activate_policy_version(policy_id, policy_version, network)
      on_update(resource, describe(activation.status.value), 0.5)
      while activation.status == SharedPolicyActivationStatus.IN_PROGRESS:
        time.sleep(random.randint(-10, 10) + 20)
        activation = self.client.get_policy_version_activation_status(activation)
        on_update(resource, describe(activation.status.value), 0.5)
      on_update(resource, describe(activation.status.value), 1)
    except CloudletAPIV3Error as e:
      on_update(resource, ":boom: [grey53]v{policy_version:<3}[/] {error}".format(policy_version=policy_version, error=e), 1)
    except RuntimeError as e:
      on_update(resource, ":boom: [grey53]v{policy_version:<3}[/] An error occurred: {e}".format(policy_version=policy_version, e=e), 1)

  def prerelease(self, resource: ResourceABC, revision: Revision, on_update: callable = lambda resource, status, progress: None):
    return self._release(Network.STAGING, resource, revision, on_update)

  def release(self, resource: ResourceABC, revision: Revision, on_update: callable = lambda resource, status, progress: None):
    return self._release(Network.PRODUCTION, resource, revision, on_update)
