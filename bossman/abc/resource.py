from abc import ABC, abstractproperty

class ResourceABC(ABC):
  """
  A {ResourceABC} is just a thing that lives at a path.
  """
  def __init__(self, path):
    self.path = path

  @abstractproperty
  def paths(self):
    pass

  def __eq__(self, other):
    if isinstance(other, ResourceABC):
      return self.path == other.path
    return False

  def __hash__(self):
    return hash(self.path)

  def __str__(self):
    return self.path

  def __rich__(self):
    return "[yellow]{path}[/yellow]".format(path=self.path)
