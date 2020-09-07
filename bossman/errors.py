
class BossmanRuntimeError(RuntimeError):
  """
  Base class for bossman-specific runtime errors.
  """
  pass

class BossmanConfigurationError(BossmanRuntimeError):
  """
  Configuration errors indicate that improper options have been passed to bossman.
  """

class MultipleMatchingPluginsError(BossmanRuntimeError):
  """
  Bossman matches plugins to resources using glob patterns.
  """
  def __init__(self, resource, plugins):
    super(MultipleMatchingPluginsError, self).__init__("Only one plugin should match a resource.")
    self.resource = resource
    self.plugins = plugins
