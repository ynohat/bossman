from types import SimpleNamespace
from bossman.repo import Repo
from bossman.abc.resource_type import ResourceTypeABC
from bossman.abc.resource import ResourceABC

class RemoteRev:
  def __init__(self, local_rev=None, remote_rev=None):
    self.local_rev = local_rev
    self.remote_rev = remote_rev

  def __str__(self):
    return "{} ({})".format(self.local_rev, self.remote_rev)

class ResourceStatus:
  def __init__(self, local_rev, remote_rev, dirty, missing_changesets):
    self.local_rev = local_rev
    self.remote_rev = remote_rev
    self.dirty = dirty
    self.missing_changesets = missing_changesets

  def __str__(self):
    return "local_rev={local_rev} remote_rev={remote_rev} dirty={dirty} changes={changes}".format(
      local_rev=self.local_rev,
      remote_rev=self.remote_rev,
      dirty=self.dirty,
      changes=len(self.missing_changesets)
    )

class ResourceManager:
  def __init__(self):
    self.resource_types = list()

  def register_resource_type(self, resource_type: ResourceTypeABC):
    self.resource_types.append(resource_type)

  def get_resource_type(self, path: str) -> ResourceTypeABC:
    for resource_type in self.resource_types:
      if resource_type.match(path):
        return resource_type
    return None

  def get_resource(self, path: str) -> ResourceABC:
    resource_type = self.get_resource_type(path)
    if resource_type:
      return resource_type.get_resource(path)
    return None

  def get_resources(self, repo: Repo, rev: str = "HEAD") -> list:
    paths = repo.get_paths(rev)
    resources = []
    for resource_type in self.resource_types:
      resources.extend(resource_type.get_resources(paths))
    return resources
