from abc import ABC, abstractproperty, abstractmethod
from bossman.config import ResourceTypeConfig
from bossman.repo import Repo, Revision
from bossman.logging import logger
from bossman.repo import RevisionDetails
import pathlib
from os.path import relpath, join

class ResourceABC(ABC):
  """
  A {ResourceABC} is just a thing that lives at a path.
  """
  def __init__(self, path):
    self.path = path

  @abstractproperty
  def paths(self):
    pass

  @abstractproperty
  def name(self):
    pass

  def __eq__(self, other):
    if isinstance(other, ResourceABC):
      return self.path == other.path
    return False

  def __lt__(self, other):
    if isinstance(other, ResourceABC):
      return self.path < other.path
    return False

  def __hash__(self):
    return hash(self.path)

  def __str__(self):
    return self.path

  def __rich__(self):
    return "[yellow]{path}[/yellow]".format(path=self.path)



class ResourceStatusABC(ABC):
  @abstractproperty
  def exists(self) -> bool:
    """
    Return True if the resource exists, False if it is only in git.
    """
    pass

  @abstractproperty
  def dirty(self) -> bool:
    """
    Return True if the resource has a remote state that has diverged
    from the state known by bossman. If True, `apply --force` will
    be required when deploying a new revision.
    """
    pass



class ResourceApplyResultABC(ABC):
  @abstractproperty
  def had_errors(self) -> bool:
    """
    Return True if any errors occurred applying a change to the resource.
    """
    pass



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
    return self.config.pattern.match(path) is not None

  def get_resource(self, path: str) -> ResourceABC:
    match = self.config.pattern.match(path)
    if match is not None:
      return self.create_resource(match.canonical, **match.values)
    return None

  @abstractmethod
  def create_resource(self, path, **kwargs) -> ResourceABC:
    pass

  @abstractmethod
  def get_resource_status(self, resource: ResourceABC):
    pass

  def affects(self, resource: ResourceABC, revision: Revision) -> bool:
    return len(set(resource.paths).intersection(revision.affected_paths)) > 0

  @abstractmethod
  def is_pending(self, resource: ResourceABC, revision: Revision) -> bool:
    """
    Returns True if the given {revision} is missing from the {resource}, serving as an
    indication to bossman that it should apply it.

    The implementation will return False if a previous apply was attempted but failed
    because the contents of {revision} are invalid.
    """
    pass

  @abstractmethod
  def is_applied(self, resource: ResourceABC, revision: Revision) -> bool:
    """
    Returns True if the given {revision} has been successfully applied to the {resource}.
    """
    pass

  @abstractmethod
  def get_revision_details(self, resource: ResourceABC, revision_id: str = None) -> RevisionDetails:
    """
    Returns plugin specific information about a given revision.
    If revision_id is None, then return information about the latest applied revision.
    """
    pass

  @abstractmethod
  def apply_change(self, resource: ResourceABC, revision: Revision, previous_revision: Revision) -> ResourceApplyResultABC:
    pass

  @abstractmethod
  def validate_working_tree(self, resource: ResourceABC):
    pass

  @abstractmethod
  def prerelease(self, resource: ResourceABC, revision: Revision, on_update: callable = lambda status, progress: None):
    pass

  @abstractmethod
  def release(self, resource: ResourceABC, revision: Revision, on_update: callable = lambda status, progress: None):
    pass

