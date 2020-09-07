from os.path import abspath, commonpath, join
from fnmatch import fnmatch

from bossman.resources import ResourceManager, ResourceStatus
from bossman.abc.resource_type import ResourceTypeABC
from bossman.abc.resource import ResourceABC
from bossman.changes import Change, ChangeSet
from bossman.config import Config, ResourceTypeConfig
from bossman.logging import get_class_logger
from bossman.repo import Repo


class Bossman:
  def __init__(self, repo_path, config: Config):
    self.config = config
    self.repo = Repo(repo_path)
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
    local_rev = self.repo.get_last_change_rev(resource.paths)
    remote_rev = resource_type.get_remote_rev(resource)
    missing_changesets = self.get_changesets(remote_rev.local_rev, local_rev, [resource])
    dirty = resource_type.is_dirty(resource)
    return ResourceStatus(
      local_rev=local_rev,
      remote_rev=remote_rev,
      dirty=dirty,
      missing_changesets=list(reversed(missing_changesets))
    )

  def get_changesets(self, since_rev: str = None, until_rev: str = "HEAD", resources: list = None) -> str:
    from collections import defaultdict
    resources = resources if resources else self.get_resources()
    paths = [resource.path for resource in resources]
    commits = self.repo.get_commits(since_rev, until_rev, paths)
    changeSets = []
    for commit in commits:
      changeSet = ChangeSet(commit)
      changeSets.append(changeSet)
      resources = dict()
      for diff in commit.diffs:
        the_path = diff.b_path or diff.a_path
        resource = self.resource_manager.get_resource(the_path)
        if resource:
          changeSet.add_resource_diff(resource, diff)
    return changeSets

  def apply_change(self, changeset: ChangeSet, change: Change):
    resource_type = self.resource_manager.get_resource_type(change.resource.path)
    resource_type.apply(changeset, change)
