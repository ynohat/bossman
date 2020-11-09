from os.path import abspath, commonpath, join
from fnmatch import fnmatch

from bossman.errors import BossmanError
from bossman.resources import ResourceManager
from bossman.abc import ResourceStatusABC
from bossman.abc import ResourceTypeABC
from bossman.abc import ResourceABC
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
    self.configure_repo()
    self.resource_manager = ResourceManager(self.config.resource_types, self.repo)
    self.logger = get_class_logger(self)

  @property
  def version(self):
    import pkg_resources
    return pkg_resources.require("bossman")[0].version

  def configure_repo(self):
    config = self.repo.config_writer()
    config.add_section("bossman")
    cur_version = config.get_value("bossman", "version", False)
    notes_refspec = "+refs/notes/*:refs/notes/*"

    for section in config.sections():
      if section.startswith("remote"):
        push_refspecs = config.get_values(section, "push", [])
        if notes_refspec not in push_refspecs:
          config.add_value(section, "push", notes_refspec)
        fetch_refspecs = config.get_values(section, "fetch", [])
        if notes_refspec not in fetch_refspecs:
          config.add_value(section, "fetch", notes_refspec)

    if cur_version != self.version:
      # TODO: migration if required
      pass
    config.set_value("bossman", "version", self.version)

  def get_resources(self, rev: str = "HEAD", glob: str = "*") -> list:
    resources = self.resource_manager.get_resources(self.repo, rev)
    glob = "*" + glob.strip("*") + "*"
    return list(sorted(filter(lambda resource: fnmatch(resource.path, glob), resources)))

  def get_missing_revisions(self, resource: ResourceABC) -> list:
    resource_type = self.resource_manager.get_resource_type(resource.path)
    revisions = self.get_revisions(resources=[resource])
    missing = []
    for revision in revisions:
      if not resource_type.is_applied(resource, revision):
        missing.append(revision)
      else:
        break
    return list(reversed(missing))

  def get_revision_details(self, resource: ResourceABC, revision: Revision):
    resource_type = self.resource_manager.get_resource_type(resource.path)
    return resource_type.get_revision_details(resource, revision)

  def get_resource_statuses(self, resources: list) -> list:
    from concurrent.futures import ThreadPoolExecutor
    futures = []
    with ThreadPoolExecutor(10, "get_status") as executor:
      for resource in resources:
        futures.append(executor.submit(self.get_resource_status, resource))
    return [f.result() for f in futures]

  def get_resource_status(self, resource: ResourceABC) -> ResourceStatusABC:
    resource_type = self.resource_manager.get_resource_type(resource.path)
    return resource_type.get_resource_status(resource)

  def get_revision(self, rev: str = None, resources: list = None) -> Revision:
    return self.repo.get_revision(rev, (p for r in resources for p in r.paths))

  def get_head_revision(self) -> Revision:
    return self.get_revision()

  def get_current_branch(self) -> str:
    return self.repo.get_current_branch()

  def get_revisions(self, since_rev: str = None, until_rev: str = "HEAD", resources: list = None) -> str:
    return self.repo.get_revisions(since_rev, until_rev, resources)

  def apply_change(self, resource: ResourceABC, revision: Revision):
    previous_revision = self.repo.get_last_revision(resource.paths, revision.parent_id)
    resource_type = self.resource_manager.get_resource_type(resource.path)
    return resource_type.apply_change(resource, revision, previous_revision)

  def validate(self, resource: ResourceABC):
    resource_type = self.resource_manager.get_resource_type(resource.path)
    resource_type.validate_working_tree(resource)

  def prerelease(self, resources: list, revision: Revision):
    resource_types = set(self.resource_manager.get_resource_type(resource.path) for resource in resources)
    for resource_type in resource_types:
      _resources = resource_type.get_resources(list(resource.path for resource in resources))
      resource_type.prerelease(_resources, revision)

  def release(self, resources: list, revision: Revision):
    resource_types = set(self.resource_manager.get_resource_type(resource.path) for resource in resources)
    for resource_type in resource_types:
      _resources = resource_type.get_resources(list(resource.path for resource in resources))
      resource_type.release(_resources, revision)
