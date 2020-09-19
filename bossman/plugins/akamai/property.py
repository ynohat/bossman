import re
import json
from os import getenv
from os.path import expanduser, basename, dirname, join
import jsonschema

from bossman.cache import cache
from bossman.errors import BossmanError
from bossman.abc.resource_type import ResourceTypeABC
from bossman.abc.resource import ResourceABC
from bossman.repo import Revision, RevisionDetails
from bossman.plugins.akamai.lib.papi import PAPIClient

RE_COMMIT = re.compile("^commit: ([a-z0-9]*)", re.MULTILINE)

_cache = cache.key(__name__)

class PropertyError(BossmanError):
  pass

class PropertyResource(ResourceABC):
  def __init__(self, path, **kwargs):
    super(PropertyResource, self).__init__(path)
    self.name = kwargs.get("name")

  @property
  def rules_path(self):
    return join(self.path, "rules.json")

  @property
  def hostnames_path(self):
    return join(self.path, "hostnames.json")

  @property
  def paths(self):
    return (self.rules_path, self.hostnames_path)


class ResourceTypeOptions:
  def __init__(self, options):
    self.edgerc = expanduser(options.get("edgerc", "~/.edgerc"))
    self.section = options.get("section", "papi")
    self.switch_key = options.get("switch_key", None)

class ResourceType(ResourceTypeABC):
  def __init__(self, config):
    super(ResourceType, self).__init__(config)
    self.options = ResourceTypeOptions(config.options)
    self.papi = PAPIClient(self.options.edgerc, self.options.section, self.options.switch_key)

  def create_resource(self, path: str, **kwargs):
    return PropertyResource(path, **kwargs)

  def get_revision_details(self, resource: ResourceABC, revision_id: str = None) -> RevisionDetails:
    version_number = None
    property_id = self.papi.get_property_id(resource.name)
    if property_id is not None: # if the property exists
      if revision_id is None:
        revision_id = self.get_last_applied_revision_id(property_id)
      if revision_id is not None: # revision_id will be None if bossman never applied any changes to this config
        property_version = self.get_property_version_for_revision_id(property_id, revision_id)
        if property_version:
          version_number = property_version.get("propertyVersion")
    return RevisionDetails(id=revision_id, details="v"+str(version_number) if version_number else None)

  def is_dirty(self, resource: PropertyResource) -> bool:
    """
    An Akamai property is dirty if its latest version does not refer to a
    revision in its notes.
    """
    is_dirty = True
    property_id = self.papi.get_property_id(resource.name)
    if property_id is not None:
      property_version = self.papi.get_latest_property_version(property_id)
      if property_version:
        is_dirty = not bool(RE_COMMIT.search(property_version.get("note", "")))
    return is_dirty

  def apply_change(self, resource: PropertyResource, revision: Revision, previous_revision: Revision=None):
    # we should only call this function if the Revision concerns the resource
    assert len(set(resource.paths).intersection(revision.affected_paths())) > 0

    property_id = self.papi.get_property_id(resource.name)
    if not property_id:
      raise PropertyError(resource, "not found")

    latest_version = None
    # if previous_revision was provided, we can figure out the property version to base
    # the new version on
    if previous_revision:
      latest_version = self.get_property_version_for_revision_id(property_id, previous_revision.id)
    # if we failed to figure out the version from a previous revision, we use the latest
    if not latest_version:
      latest_version = self.papi.get_latest_property_version(property_id)

    # before changing anything in PAPI, check that the json files are valid
    rules = revision.show_path(resource.rules_path)
    rules_json = self.validate_rules(resource, rules)
    hostnames_json = None
    if resource.hostnames_path in revision.affected_paths():
      hostnames = revision.show_path(resource.hostnames_path)
      hostnames_json = self.validate_hostnames(resource, hostnames)

    # now we can create the new version in PAPI
    next_version = self.papi.create_property_version(property_id, latest_version.get("propertyVersion"))
    print("created new version: ", next_version.get("propertyVersion"), "for rev", revision.id, revision.message)

    # first, we apply the hostnames change
    if hostnames_json:
      self.papi.update_property_hostnames(property_id, next_version.get("propertyVersion"), hostnames_json)
    # then, regardless of whether there was a change to the rule tree, we need to update it with
    # the commit message and id, otherwise we will get a dirty status
    rules_json.update(comments="{}\n\ncommit: {}\nbranch: {}".format(revision.message.strip(), revision.id, ", ".join(revision.branches)))
    self.papi.update_property_rule_tree(property_id, next_version.get("propertyVersion"), rules_json)

  def get_property_version_for_revision_id(self, property_id, revision_id):
    cache = _cache.key("property_version", property_id, revision_id)
    property_version = cache.get_json()
    if property_version is None:
      search = r'commit: {}'.format(revision_id)
      predicate = lambda v: search in v.get("note", "")
      property_version = self.papi.find_latest_property_version(property_id, predicate)
      if property_version != None:
        cache.update_json(property_version)
    return property_version

  def get_last_applied_revision_id(self, property_id):
    """
    Return the last revision id applied to the resource.
    This works by searching for a pattern in the property version notes.
    """
    property_version = self.papi.find_latest_property_version(
      property_id,
      lambda v: RE_COMMIT.search(v.get("note", ""))
    )
    if property_version:
      return RE_COMMIT.search(property_version.get("note")).group(1)
    return None

  def validate_working_tree(self, resource: PropertyResource):
    with open(resource.hostnames_path, "r") as hfd:
      hostnames = hfd.read()
      self.validate_hostnames(resource, hostnames)
    with open(resource.rules_path, "r") as hfd:
      rules = hfd.read()
      self.validate_rules(resource, rules)

  def validate_rules(self, resource: PropertyResource, rules: str):
    try:
      rules_json = json.loads(rules)
      # While these are not mandatory in PAPI, they ARE mandatory in bossman since
      # it is the easiest and most standard way of telling bossman how to validate
      # and version-freeze.
      if not "productId" in rules_json:
        raise PropertyError("{}: productId field is missing")
      if not "ruleFormat" in rules_json:
        raise PropertyError("{}: ruleFormat field is missing")

      schema = self.papi.get_rule_format_schema(rules_json.get("productId"), rules_json.get("ruleFormat"))
      jsonschema.validate(rules_json, schema)
      return rules_json
    except json.decoder.JSONDecodeError as err:
      self.logger.error("{}: bad rules.json - {}", resource, err.args)
      raise PropertyError(resource, "bad rules.json", err.args)
    except jsonschema.ValidationError as err:
      self.logger.error("{}: invalid rules.json - {}", resource, err.args)
      raise PropertyError(resource, "invalid rules.json", err.args)

  def validate_hostnames(self, resource: PropertyResource, hostnames: str):
    try:
      hostnames_json = json.loads(hostnames)
      schema = self.papi.get_request_schema("SetPropertyVersionsHostnamesRequestV0.json")
      jsonschema.validate(hostnames_json, schema)
      return hostnames_json
    except json.decoder.JSONDecodeError as err:
      self.logger.error("{}: bad hostnames.json - {}", resource, err.args)
      raise PropertyError(resource, "bad hostnames.json", err.args)
    except jsonschema.ValidationError as err:
      self.logger.error("{}: bad hostnames.json - {}", resource, err.args)
      raise PropertyError(resource, "invalid hostnames.json", err.args)

