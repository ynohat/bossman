import re
import json
from os import getenv
from os.path import expanduser, basename, dirname, join

from bossman.cache import cache
from bossman.errors import BossmanError
from bossman.abc.resource_type import ResourceTypeABC
from bossman.abc.resource import ResourceABC
from bossman.repo import Revision
from bossman.plugins.akamai.lib.papi import PAPIClient
from bossman.resources import RemoteRev

RE_COMMIT = re.compile("^commit: ([a-z0-9]*)", re.MULTILINE)

_cache = cache.key(__name__)

class PropertyError(BossmanError):
  def __rich__(self):
    return "{}: {}".format(self.__class__.__name__, " ".join(self.args))

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

  def get_remote_rev(self, resource: PropertyResource) -> str:
    local_rev, remote_rev = None, None
    property_id = self.papi.get_property_id(resource.name)
    cache = _cache.key("remote_version", property_id)
    remote_version = cache.get_json()
    if remote_version is None:
      remote_version = self.papi.find_latest_property_version(
        property_id,
        lambda v: RE_COMMIT.search(v.get("note", ""))
      )
      self.logger.info("get_remote_rev {property_name} -> {property_version}".format(property_name=resource.name, property_version=remote_version))
      if remote_version:
        cache.update_json(remote_version)
    if remote_version:
      remote_rev = remote_version.get("propertyVersion")
      local_rev = RE_COMMIT.search(remote_version.get("note")).group(1)
    return RemoteRev(local_rev=local_rev, remote_rev=remote_rev)

  def is_dirty(self, resource: PropertyResource) -> bool:
    """
    An Akamai property is dirty if its latest version does not refer to a
    revision in its notes.
    """
    is_dirty = True
    property_id = self.papi.get_property_id(resource.name)
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
    rules_json = None
    hostnames_json = None

    try:
      rules = revision.show_path(resource.rules_path)
      rules_json = json.loads(rules)
    except json.decoder.JSONDecodeError as err:
      self.logger.error("{}: bad rules.json - {}", resource, err.args)
      raise PropertyError(resource, "bad rules.json", err.args)

    try:
      if resource.hostnames_path in revision.affected_paths():
        hostnames = revision.show_path(resource.hostnames_path)
        hostnames_json = json.loads(hostnames)
    except json.decoder.JSONDecodeError as err:
      self.logger.error("{}: bad hostnames.json - {}", resource, err.args)
      raise PropertyError(resource, "bad hostnames.json", err.args)

    # now we can create the new version in PAPI
    next_version = self.papi.create_property_version(property_id, latest_version.get("propertyVersion"))
    print("created new version: ", next_version.get("propertyVersion"), "for rev", revision.id, revision.message)

    # first, we apply the hostnames change
    if hostnames_json:
      self.papi.update_property_hostnames(property_id, next_version.get("propertyVersion"), hostnames_json)
    # then, regardless of whether there was a change to the rule tree, we need to update it with
    # the commit message and id, otherwise we will get a dirty status
    rules_json.update(comments="{}\n\ncommit: {}".format(revision.message.strip(), revision.id))
    self.papi.update_property_rule_tree(property_id, next_version.get("propertyVersion"), rules_json)

  def get_property_version_for_revision_id(self, property_id, revision_id):
    cache = _cache.key("property_version", property_id, revision_id)
    property_version = cache.get_str()
    if property_version is None:
      search = r'commit: {}'.format(revision_id)
      predicate = lambda v: search in v.get("note", "")
      property_version = self.papi.find_latest_property_version(property_id, predicate)
      if property_version != None:
        cache.update(property_version)
    return property_version
