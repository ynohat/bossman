
class BossmanError(RuntimeError):
  """
  Base class for bossman-specific runtime errors.
  """
  def __rich__(self):
    return "{}: {}".format(self.__class__.__name__, " ".join(str(arg) for arg in self.args))

class BossmanConfigurationError(BossmanError):
  """
  Configuration errors indicate that improper options have been passed to bossman.
  """

class MultipleMatchingPluginsError(BossmanError):
  """
  Bossman matches plugins to resources using glob patterns.
  """
  def __init__(self, resource, plugins):
    super(MultipleMatchingPluginsError, self).__init__("Only one plugin should match a resource.")
    self.resource = resource
    self.plugins = plugins
