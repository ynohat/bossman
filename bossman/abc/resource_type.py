from abc import ABC, abstractmethod
from bossman.config import ResourceTypeConfig
from bossman.changes import Change, ChangeSet
from bossman.logging import logger
from bossman.abc.resource import ResourceABC
import parse
from os.path import relpath, join

class ResourceTypeABC(ABC):
  @staticmethod
  def create(config: ResourceTypeConfig):
    import importlib
    plugin = importlib.import_module(config.module)
    return plugin.ResourceType(config)

  """
  Abstract class for resource_types.
  """
  def __init__(self, config: ResourceTypeConfig):
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

  def describe_diffs(self, resource: ResourceABC, diffs: list) -> Change:
    change = Change(resource)
    change.diffs = diffs
    return change

  @abstractmethod
  def create_resource(self, path, **kwargs) -> ResourceABC:
    pass

  @abstractmethod
  def get_remote_rev(self, resource: ResourceABC) -> str:
    pass

  @abstractmethod
  def is_dirty(self, resource: ResourceABC) -> bool:
    pass

  @abstractmethod
  def apply(self, changeset: ChangeSet, change: Change) -> bool:
    pass
