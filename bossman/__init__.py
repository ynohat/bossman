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
    return list(sorted(filter(lambda resource: fnmatch(resource.path, glob), resources)))

  def get_missing_revisions(self, resource: ResourceABC) -> list:
    resource_type = self.resource_manager.get_resource_type(resource.path)
    revs = self.get_revisions(resources=[resource])
    missing = []
    for rev in revs:
      rev_details = resource_type.get_revision_details(resource, rev.id)
      if rev_details.details is None:
        missing.append(rev)
      else:
        break
    return list(reversed(missing))

  def get_resource_status(self, resource: ResourceABC) -> ResourceStatus:
    resource_type = self.resource_manager.get_resource_type(resource.path)
    # latest commit affecting this resource
    last_revision = self.repo.get_last_revision(resource.paths)
    # get info from the plugin about that revision (remote version number?)
    last_revision_details = resource_type.get_revision_details(resource, last_revision.id)
    missing_revisions = self.get_missing_revisions(resource)
    dirty = resource_type.is_dirty(resource)
    return ResourceStatus(
      last_revision=last_revision,
      last_revision_details=last_revision_details,
      dirty=dirty,
      missing_revisions=list(reversed(missing_revisions))
    )

  def get_revision(self, rev: str = None, resources: list = None) -> str:
    return self.repo.get_revision(rev, (p for r in resources for p in r.paths))

  def get_revisions(self, since_rev: str = None, until_rev: str = "HEAD", resources: list = None) -> str:
    return self.repo.get_revisions(since_rev, until_rev, resources)

  def apply_change(self, resource: ResourceABC, revision: Revision):
    previous_revision = self.repo.get_last_revision(resource.paths, revision.parent_id)
    resource_type = self.resource_manager.get_resource_type(resource.path)
    resource_type.apply_change(resource, revision, previous_revision)

  def validate(self, resource: ResourceABC):
    resource_type = self.resource_manager.get_resource_type(resource.path)
    resource_type.validate_working_tree(resource)