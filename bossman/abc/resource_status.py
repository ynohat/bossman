from abc import ABC, abstractproperty

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