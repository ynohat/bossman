import pathlib
from bossman.abc import ResourceABC

class SharedPolicyResource(ResourceABC):
  def __init__(self, path, **kwargs):
    super(SharedPolicyResource, self).__init__(path)
    self.__name = kwargs.get("name")

  @property
  def name(self):
    return self.__name

  @property
  def policy_path(self):
    # All operations use unix-style paths; this is important
    return str(pathlib.PurePosixPath(self.path) / "policy.json")

  @property
  def paths(self):
    return (self.policy_path,)

  def __rich__(self):
    prefix = self.path.replace(self.name, "")
    return "[grey53]{}[/][yellow]{}[/]".format(prefix, self.name)
