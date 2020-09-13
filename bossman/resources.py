from types import SimpleNamespace
from bossman.repo import Repo
from bossman.abc.resource_type import ResourceTypeABC
from bossman.abc.resource import ResourceABC

class ResourceStatus:
  def __init__(self, last_revision, last_revision_details, last_applied_revision, last_applied_revision_details, dirty, missing_revisions):
    self.last_revision = last_revision
    self.last_revision_details = last_revision_details
    self.last_applied_revision = last_applied_revision
    self.last_applied_revision_details = last_applied_revision_details
    self.dirty = dirty
    self.missing_revisions = missing_revisions

  def __str__(self):
    return "last_revision={last_revision} last_applied_revision={last_applied_revision} dirty={dirty} changes={changes}".format(
      last_revision=self.last_revision.id,
      last_applied_revision=self.last_applied_revision,
      dirty=self.dirty,
      changes=len(self.missing_revisions)
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
