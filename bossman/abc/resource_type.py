from abc import ABC, abstractmethod
from bossman.config import ResourceTypeConfig
from bossman.repo import Repo, Revision
from bossman.logging import logger
from bossman.abc.resource import ResourceABC
from bossman.repo import RevisionDetails
import parse
from os.path import relpath, join

class ResourceTypeABC(ABC):
  """
  Abstract class for resource_types.
  """
  def __init__(self, repo: Repo, config: ResourceTypeConfig):
    self.repo = repo
    self.config = config
    self.logger = logger.getChild(
      "{module_name}.{class_name}".format(
        module_name=self.__class__.__module__,
        class_name=self.__class__.__name__
      )
    )
    self.logger.info("config={config}".format(config=str(config)))

  def get_resources(self, paths: list):
    """
    Given a list of paths relative to the repo, determine the subset managed
    by this resource type and return the list of {ResourceABC}s.
    """
    return set(
      resource
      for resource
      in (
        self.get_resource(path)
        for path
        in paths
      )
      if resource != None
    )

  def match(self, path: str) -> bool:
    result = parse.search(self.config.pattern, path)
    if result:
      canonical = self.config.pattern.format(**result.named)
      return path.startswith(canonical)
    return False

  def get_resource(self, path: str) -> ResourceABC:
    result = parse.search(self.config.pattern, path)
    if result:
      canonical = self.config.pattern.format(**result.named)
      if path.startswith(canonical):
        return self.create_resource(canonical, **result.named)
    return None

  @abstractmethod
  def create_resource(self, path, **kwargs) -> ResourceABC:
    pass

  @abstractmethod
  def get_resource_status(self, resource: ResourceABC):
    pass

  @abstractmethod
  def is_applied(self, resource: ResourceABC, revision: Revision) -> bool:
    pass

  @abstractmethod
  def get_revision_details(self, resource: ResourceABC, revision_id: str = None) -> RevisionDetails:
    """
    Returns plugin specific information about a given revision.
    If revision_id is None, then return information about the latest applied revision.
    """
    pass

  @abstractmethod
  def is_dirty(self, resource: ResourceABC) -> bool:
    pass

  @abstractmethod
  def apply_change(self, resource: ResourceABC, revision: Revision, previous_revision: Revision):
    pass

  @abstractmethod
  def validate_working_tree(self, resource: ResourceABC):
    pass

  @abstractmethod
  def prerelease(self, resources: list, revision: Revision):
    pass
