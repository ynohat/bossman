from os.path import abspath, commonpath, join
from fnmatch import fnmatch

from bossman.errors import BossmanError
from bossman.resources import ResourceManager, ResourceStatus
from bossman.abc.resource_type import ResourceTypeABC
from bossman.abc.resource import ResourceABC
from bossman.config import Config, ResourceTypeConfig
from bossman.logging import get_class_logger
from bossman.repo import Repo, Revision, Change


class Bossman:
  def __init__(self, repo_path, config: Config):
    self.config = config
    try:
      self.repo = Repo(repo_path)
    except:
      raise BossmanError("An error occurred, please check that this is a git repository or working tree.")
    self.resource_manager = ResourceManager()
    for config in self.config.resource_types:
      resource_type = ResourceTypeABC.create(config)
      self.resource_manager.register_resource_type(resource_type)
    self.logger = get_class_logger(self)

  def get_resources(self, rev: str = "HEAD", glob: str = "*") -> list:
    resources = self.resource_manager.get_resources(self.repo, rev)
    return list(filter(lambda resource: fnmatch(resource.path, glob), resources))

  def get_resource_status(self, resource: ResourceABC) -> ResourceStatus:
    resource_type = self.resource_manager.get_resource_type(resource.path)
    last_rev = self.repo.get_last_revision(resource.paths)
    remote_rev = resource_type.get_remote_rev(resource)
    missing_revisions = self.repo.get_revisions(remote_rev.local_rev, last_rev.id, resource.paths)
    dirty = resource_type.is_dirty(resource)
    return ResourceStatus(
      local_rev=last_rev.id,
      remote_rev=remote_rev,
      dirty=dirty,
      missing_revisions=list(reversed(missing_revisions))
    )

  def get_revisions(self, since_rev: str = None, until_rev: str = "HEAD", resources: list = None) -> str:
    return self.repo.get_revisions(since_rev, until_rev, resources)

  def apply_change(self, resource: ResourceABC, revision: Revision):
    previous_revision = self.repo.get_last_revision(resource.paths, revision.parent_id)
    resource_type = self.resource_manager.get_resource_type(resource.path)
    resource_type.apply_change(resource, revision, previous_revision)
