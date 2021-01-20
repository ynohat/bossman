import yaml
from rich.panel import Panel
from rich.syntax import Syntax
from rich.padding import Padding

class BossmanError(RuntimeError):
  """
  Base class for bossman-specific runtime errors.
  """
  def __rich_console__(self, *args):
    error_yaml = yaml.safe_dump(self.args)
    yield Panel(
      Syntax(error_yaml, "yaml").highlight(error_yaml),
      title="[bold red]{}[/]".format(type(self).__name__),
      title_align="left",
      padding=(0, 0, 0, 4)
    )

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

class BossmanValidationError(BossmanError):
  """
  Raised by plugins when a resource is invalid.
  """