import re
import json
from os import getenv
from os.path import expanduser, basename, dirname, join

from bossman.abc.resource_type import ResourceTypeABC
from bossman.abc.resource import ResourceABC
from bossman.changes import Change
from bossman.plugins.akamai.lib.papi import PAPIClient
from bossman.changes import Change, ChangeSet
from bossman.resources import RemoteRev

RE_COMMIT = re.compile("^commit: ([a-z0-9]*)", re.MULTILINE)

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
    self.papi = PAPIClient(self.options.edgerc, self.options.section)

  def create_resource(self, path: str, **kwargs):
    return PropertyResource(path, **kwargs)

  def get_remote_rev(self, resource: ResourceABC) -> str:
    local_rev, remote_rev = None, None
    property_id = self.papi.get_property_id(resource.name)
    property_version = self.papi.find_latest_property_version(
      property_id,
      lambda v: RE_COMMIT.search(v.get("note", ""))
    )
    self.logger.info("get_remote_rev {property_name} -> {property_version}".format(property_name=resource.name, property_version=property_version))
    if property_version:
      remote_rev = property_version.get("propertyVersion")
      local_rev = RE_COMMIT.search(property_version.get("note")).group(1)
    return RemoteRev(local_rev=local_rev, remote_rev=remote_rev)

  def is_dirty(self, resource: ResourceABC) -> bool:
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

  def apply(self, changeset: ChangeSet, change: Change) -> bool:
    changes = self.get_concrete_changes(change)
    if len(changes):
      self.logger.info("apply {rev} {resource} ({changes})".format(
        rev=changeset.rev,
        resource=change.resource,
        changes=", ".join(changes.keys())
      ))
      property_id = self.papi.get_property_id(change.resource.name)
      latest_version = self.papi.get_latest_property_version(property_id)
      next_version = self.papi.create_property_version(property_id, latest_version.get("propertyVersion"))
      rule_tree = changes.get("rules", None)
      if rule_tree:
        rule_tree.update(comments=get_property_notes(changeset))
        self.papi.update_property_rule_tree(property_id, next_version.get("propertyVersion"), rule_tree)
      hostnames = changes.get("hostnames", None)
      if hostnames:
        self.papi.update_property_hostnames(property_id, next_version.get("propertyVersion"), hostnames)

  def get_concrete_changes(self, change: Change) -> dict:
    changes = dict()
    for diff in change.diffs:
      if diff.change_type in "RAM":
        if basename(diff.b_path) == "hostnames.json":
          changes.update(hostnames=json.loads(diff.b_blob.data_stream.read()))
        elif basename(diff.b_path) == "rules.json":
          changes.update(rules=json.loads(diff.b_blob.data_stream.read()))
    return changes

def get_property_notes(changeset: ChangeSet):
  from textwrap import dedent
  return dedent(
    """\
    {message}
    commit: {commit}\
    """
  ).format(
    message=changeset.message,
    commit=changeset.rev
  )
