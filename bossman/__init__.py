from os.path import abspath, commonpath, join
from fnmatch import fnmatch
from functools import cached_property

from rich.console import Console
from rich.progress import Progress

from bossman.errors import BossmanError
from bossman.resources import ResourceManager
from bossman.abc import ResourceStatusABC
from bossman.abc import ResourceTypeABC
from bossman.abc import ResourceABC
from bossman.config import Config, ResourceTypeConfig
from bossman.logging import get_class_logger
from bossman.repo import Repo, Revision, Change


def if_initialized(func):
  def wrapper(bossman, *args, **kwargs):
    if bossman.initialized:
      return func(bossman, *args, **kwargs)
    raise BossmanError("Repository not initialized or needs migration, please run `bossman init`.")
  return wrapper

class Bossman:
  def __init__(self, root, config: Config):
    self.config = config
    self.root = root
    self.logger = get_class_logger(self)

  @cached_property
  def repo(self):
    return Repo(self.root)

  @cached_property
  def resource_manager(self):
    return ResourceManager(self.config.resource_types, self.repo)

  @cached_property
  def initialized(self):
    config = self.repo.config_reader()
    if "bossman" in config.sections():
      from .migrations import required
      if required(config):
        return False
      return True
    return False

  @cached_property
  def version(self):
    import pkg_resources
    return pkg_resources.require("bossman")[0].version

  def init(self, console: Console):
    self.init_git_config(console)

  def init_git_config(self, console: Console):
    from .migrations import migrate
    conf = self.repo.config_writer()
    migrate(conf, self.repo, console)
    conf.set_value("bossman", "version", self.version)


  @if_initialized
  def get_resources(self, *globs, rev: str = "HEAD") -> list:
    resources = self.resource_manager.get_resources(self.repo, rev)
    globs = list(globs)
    # by default, all resources
    if len(globs) == 0:
      globs = globs.append("*")
    # enable partial matches
    globs = list("*" + glob.strip("*") + "*" for glob in globs)
    match = lambda resource: any(fnmatch(resource.path, glob) for glob in globs)
    return list(sorted(filter(match, resources)))

  @if_initialized
  def get_resources_from_working_copy(self, *globs) -> list:
    resources = self.resource_manager.get_resources_from_working_copy(self.repo)
    globs = list(globs)
    # by default, all resources
    if len(globs) == 0:
      globs = globs.append("*")
    # enable partial matches
    globs = list("*" + glob.strip("*") + "*" for glob in globs)
    match = lambda resource: any(fnmatch(resource.path, glob) for glob in globs)
    return list(sorted(filter(match, resources)))

  @if_initialized
  def get_missing_revisions(self, resource: ResourceABC, since_rev: str = None) -> list:
    resource_type = self.resource_manager.get_resource_type(resource.path)
    revisions = self.get_revisions(resources=[resource], since_rev=since_rev)
    missing = []
    for revision in revisions:
      # The revision may affect a file that is in the resource folder, but
      # is not managed by the resource. Only add the revision if it actually
      # affects it.
      if resource_type.affects(resource, revision):
        if resource_type.is_pending(resource, revision):
          missing.append(revision)
        else:
          break
    return list(reversed(missing))

  @if_initialized
  def get_revision_details(self, resource: ResourceABC, revision: Revision):
    resource_type = self.resource_manager.get_resource_type(resource.path)
    return resource_type.get_revision_details(resource, revision)

  @if_initialized
  def get_resource_statuses(self, resources: list) -> list:
    from concurrent.futures import ThreadPoolExecutor
    futures = []
    with ThreadPoolExecutor(10, "get_status") as executor:
      for resource in resources:
        futures.append(executor.submit(self.get_resource_status, resource))
    return [f.result() for f in futures]

  @if_initialized
  def get_resource_status(self, resource: ResourceABC) -> ResourceStatusABC:
    self.repo.fetch_notes(resource.path)
    resource_type = self.resource_manager.get_resource_type(resource.path)
    return resource_type.get_resource_status(resource)

  @if_initialized
  def get_revision(self, rev: str = None, resources: list = None) -> Revision:
    return self.repo.get_revision(rev, (p for r in resources for p in r.paths))

  @if_initialized
  def get_head_revision(self) -> Revision:
    return self.get_revision()

  @if_initialized
  def get_current_branch(self) -> str:
    return self.repo.get_current_branch()

  @if_initialized
  def get_revisions(self, since_rev: str = None, until_rev: str = "HEAD", resources: list = None) -> str:
    return self.repo.get_revisions(since_rev, until_rev, resources)

  @if_initialized
  def apply_change(self, resource: ResourceABC, revision: Revision):
    self.repo.fetch_notes(resource.path)
    previous_revision = self.repo.get_last_revision(resource.paths, revision.parent_id)
    resource_type = self.resource_manager.get_resource_type(resource.path)
    result = resource_type.apply_change(resource, revision, previous_revision)
    self.repo.push_notes(resource.path)
    return result

  @if_initialized
  def validate(self, resource: ResourceABC):
    resource_type = self.resource_manager.get_resource_type(resource.path)
    resource_type.validate_working_tree(resource)

  @if_initialized
  def prerelease(self, resource: ResourceABC, revision: Revision, on_update: callable):
    self.repo.fetch_notes(resource.path)
    resource_type = self.resource_manager.get_resource_type(resource.path)
    resource_type.prerelease(resource, revision, on_update)

  @if_initialized
  def release(self, resource: ResourceABC, revision: Revision, on_update: callable):
    self.repo.fetch_notes(resource.path)
    resource_type = self.resource_manager.get_resource_type(resource.path)
    resource_type.release(resource, revision, on_update)

  # @if_initialized
  # def prerelease(self, resources: list, revision: Revision):
  #   resource_types = set(self.resource_manager.get_resource_type(resource.path) for resource in resources)
  #   for resource_type in resource_types:
  #     _resources = resource_type.get_resources(list(resource.path for resource in resources))
  #     resource_type.prerelease(_resources, revision)

  # @if_initialized
  # def release(self, resources: list, revision: Revision):
  #   resource_types = set(self.resource_manager.get_resource_type(resource.path) for resource in resources)
  #   for resource_type in resource_types:
  #     _resources = resource_type.get_resources(list(resource.path for resource in resources))
  #     resource_type.release(_resources, revision)
