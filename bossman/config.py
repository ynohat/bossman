import parse, re
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

class PathPatternMatch:
  """
  canonical: the canonical resource path
  values: the variables extracted by the pattern match
  """
  def __init__(self, canonical, values):
    self.canonical = canonical
    self.values = values

class PathPattern:

  @staticmethod
  @parse.with_pattern(r'[^/]+')
  def PathComponent(s):
    return s

  def __init__(self, pattern):
    # A pattern might look like this: /a/{b}/{c}.
    # A resource path can be created using string formatting:
    #   pattern.format(b="foo", c="bar")
    self._format_pattern = pattern
    # We also need to be able to match a real path against the pattern.
    # We constrain the placeholders to only match path components, using
    # a custom regular expression. So we need to turn /a/{b}/{c} into
    # /a/{b:PathComponent}/{c:PathComponent}.
    self._match_pattern = self._format_pattern
    # So we parse the pattern with itself, retrieving dict(b="{b}", c="{c}")
    names = parse.parse(pattern, pattern).named
    # And we manipulate the match pattern based on the placeholders we discovered.
    for name, placeholder in names.items():
      placeholder_re = re.escape(placeholder)
      final_placeholder = "{{{}:PathComponent}}".format(name)
      self._match_pattern = re.sub(placeholder_re, final_placeholder, self._match_pattern)

  def match(self, path):
    """
    Matches path against the pattern. Returns a `PathPatternMatch` if successful, None otherwise.
    """
    result = parse.search(self._match_pattern, path, extra_types=dict(PathComponent=PathPattern.PathComponent))
    if result:
      canonical = self._format_pattern.format(**result.named)
      if path.startswith(canonical):
        return PathPatternMatch(canonical, result.named)
    return None

class ResourceTypeConfig:
  def __init__(self, data):
    self.pattern = PathPattern(data.get("pattern"))
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

 