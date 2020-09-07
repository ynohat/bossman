from os import getcwd
from os.path import expanduser, isabs, relpath, abspath, dirname, join
from bossman.errors import BossmanConfigurationError
from bossman.logging import logger

logger = logger.getChild(__name__)

def getenv(key, default=None):
  from os import getenv
  v = getenv(key)
  if v == None:
    return default

_DEFAULT_RESOURCE_TYPES = (
  {
    "module": "bossman.plugins.akamai.property",
    "pattern": "akamai/property/{name}",
    "options": {
      "edgerc": getenv("AKAMAI_EDGERC", expanduser("~/.edgerc")),
      "section": getenv("AKAMAI_EDGERC_SECTION", "papi"),
      "switch_key": getenv("AKAMAI_EDGERC_SWITCHKEY", None),
    }
  },
)

class ResourceTypeConfig:
  def __init__(self, data):
    self.pattern = data.get("pattern")
    self.module = data.get("module")
    self.options = data.get("options", {})

  def __str__(self):
    return _dump(self)

class Config:
  def __init__(self, data):
    self.resource_types = (
      ResourceTypeConfig(config)
      for config
      in data.get("resources", _DEFAULT_RESOURCE_TYPES)
    )

  def __str__(self):
    return _dump(self)

def _dump(obj):
  def simplify(obj):
    try:
      __dict__ = object.__getattribute__(obj, "__dict__")
      return dict(
        (k, simplify(v))
        for (k, v)
        in __dict__.items()
      )
    except AttributeError:
      return obj
  return str(simplify(obj))

 