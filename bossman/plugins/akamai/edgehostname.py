from bossman.plugins.akamai.lib.edgegrid import EdgegridError
import json
from os.path import expanduser
from types import SimpleNamespace

from bossman.errors import BossmanError, BossmanValidationError
from bossman.abc import ResourceTypeABC
from bossman.abc import ResourceStatusABC
from bossman.abc import ResourceABC
from bossman.abc import ResourceApplyResultABC
from bossman.plugins.akamai.utils import GenericVersionComments
from bossman.repo import Repo, Revision, RevisionDetails
from bossman.plugins.akamai.lib.papi import (
  PAPIClient,
  PAPIEdgeHostnameChangeAlreadyInProgressError,
  PAPIEdgeHostnameNotAvailableError,
  PAPIError,
)
from bossman.rich import bracketize
from rich import print

class EdgeHostnameValidationError(BossmanValidationError):
  pass

class EdgeHostnameNotFoundError(BossmanError):
  pass

class EdgeHostnameResource(ResourceABC):
  def __init__(self, path, **kwargs):
    super(EdgeHostnameResource, self).__init__(path)
    self.__name = kwargs.get("name")

  @property
  def certEnrollmentId(self):
    return self.__name

  @property
  def name(self):
    return self.__name

  @property
  def paths(self):
    return (self.path,)

  def __rich__(self):
    path = self.path.replace(self.name, f'[/][yellow]{self.name}[/][grey53]')
    return f'[grey53]{path}[/]'

class EdgeHostnameStatus(ResourceStatusABC):
  def __init__(self, repo: Repo, resource: EdgeHostnameResource, error=None):
    self.repo = repo
    self.resource = resource
    self.error = error

  @property
  def exists(self):
    return False

  @property
  def dirty(self) -> bool:
    if not self.exists:
      return False
    return True

  def __rich_console__(self, *args, **kwargs):
    yield "[gray31](status not implemented for EdgeHostnames yet)[/]"

class EdgeHostnameApplyResult(ResourceApplyResultABC):
  def __init__(self,
              resource: EdgeHostnameResource,
              revision: Revision,
              error=None):
    self.resource = resource
    self.revision = revision
    self.error = error

  @property
  def had_errors(self) -> bool:
    return self.error != None

  def __rich_console__(self, *args, **kwargs):
    parts = []
    parts.append(r':arrow_up:')
    parts.append(self.resource.__rich__())
    parts.append(r'[grey53]{h}[/]'.format(h=bracketize(self.revision.id)))
    yield " ".join(parts)
    if self.error is not None:
      from rich.syntax import Syntax
      import yaml
      error_yaml = yaml.safe_dump(self.error.args[0])
      yield '{}\n{}'.format(type(self.error).__name__, Syntax(error_yaml, "yaml").highlight(error_yaml))

class ResourceTypeOptions:
  def __init__(self, options):
    from os import environ
    self.env_prefix = options.get("env_prefix", "")
    self.edgerc = expanduser(environ.get("%sEDGERC" % self.env_prefix, options.get("edgerc", "~/.edgerc")))
    self.section = environ.get("%sEDGERC_SECTION" % self.env_prefix, options.get("section", "default"))
    switch_key_opt = options.get("account_key", options.get("switch_key", None))
    if "switch_key" in options:
      print('[red]WARNING: "switch_key" option is deprecated; use "account_key" instead[/]')
    self.switch_key = environ.get("%sEDGERC_SWITCH_KEY" % self.env_prefix, switch_key_opt)

class ResourceType(ResourceTypeABC):
  def __init__(self, repo: Repo, config):
    super(ResourceType, self).__init__(repo, config)
    self.options = ResourceTypeOptions(config.options)
    self.papi = PAPIClient(self.options.edgerc, self.options.section, self.options.switch_key)

  def create_resource(self, path: str, **kwargs):
    return EdgeHostnameResource(path, **kwargs)

  def get_resource_status(self, resource: EdgeHostnameResource):
    try:
      return EdgeHostnameStatus(self.repo, resource, [])
    except BossmanError as e:
      return EdgeHostnameStatus(self.repo, resource, [], error=e)

  def is_pending(self, resource: EdgeHostnameResource, revision: Revision):
    return not self.is_applied(resource, revision)

  def is_applied(self, resource: EdgeHostnameResource, revision: Revision):
    if self.affects(resource, revision):
      notes = revision.get_notes(resource.path)
      return notes.get('is_applied', False)
    return True

  def get_revision_details(self, resource: ResourceABC, revision: Revision) -> RevisionDetails:
    return RevisionDetails(id=revision.id, details=None)

  def apply_change(self, resource: EdgeHostnameResource, revision: Revision, previous_revision: Revision=None) -> EdgeHostnameApplyResult:
    # we should only call this function if the Revision concerns the resource
    assert self.affects(resource, revision)

    notes = SimpleNamespace(
      is_applied=None,
      has_errors=False,
      edgehostname_id=None,
    )

    try:
      data = revision.show_path(resource.path, textconv=True)
      args = self.validate(resource, data)
      result = self.papi.create_edgehostname(**args)
      notes.edgehostname_id = result.edgeHostnameId
      notes.is_applied = True
      return EdgeHostnameApplyResult(resource, revision, error=None)
    except (PAPIEdgeHostnameNotAvailableError, PAPIEdgeHostnameChangeAlreadyInProgressError) as e:
      notes.is_applied = True
      notes.has_errors = False
      return EdgeHostnameApplyResult(resource, revision)
    except (EdgeHostnameValidationError, PAPIError) as e:
      notes.is_applied = True
      notes.has_errors = False
      return EdgeHostnameApplyResult(resource, revision, error=e)
    except EdgegridError as e:
      return EdgeHostnameApplyResult(resource, revision, error=e)
    finally:
      revision.get_notes(resource.path).set(**vars(notes))

  def validate_working_tree(self, resource: EdgeHostnameResource):
    try:
      with open(resource.path, "r") as hfd:
        self.validate(resource, hfd.read())
    except (NotADirectoryError, FileNotFoundError) as e:
      raise EdgeHostnameValidationError("file not found {}".format(e.filename))

  def validate(self, resource, data):
    if data is None:
      raise EdgeHostnameValidationError(f'{resource.path}: missing')
    try:
      data = json.loads(data)
    except json.JSONDecodeError as e:
      raise EdgeHostnameValidationError(f'{resource.path}: ({e.lineno}:{e.colno}) {e.msg}')
    requiredFields = ("groupId", "contractId", "edgeHostname")
    missing = list(field for field in requiredFields if field not in data)
    if not "edgeHostname" in missing:
      requiredFields = ("domainPrefix", "domainSuffix", "ipVersionBehavior", "productId", "secureNetwork")
      missing += list(f'edgeHostname.{field}' for field in requiredFields if field not in data["edgeHostname"])
      if "secureNetwork" in data["edgeHostname"] and data["edgeHostname"]["secureNetwork"] == "ENHANCED_TLS":
        missing += list(f'edgeHostname.{field}' for field in ["certEnrollmentId"] if field not in data["edgeHostname"])
    if len(missing):
      raise EdgeHostnameValidationError(f'{resource.path}: missing required fields: {", ".join(missing)}')
    return dict(
      groupId=data.get('groupId'),
      contractId=data.get('contractId'),
      **data.get('edgeHostname'),
    )

  def prerelease(self, resource: ResourceABC, revision: Revision, on_update: callable = lambda resource, status, progress: None):
    on_update(resource, '[grey53]STG Nothing to do[/]', 1)

  def release(self, resource: ResourceABC, revision: Revision, on_update: callable = lambda resource, status, progress: None):
    on_update(resource, '[grey53]PRD Nothing to do[/]', 1)

  def get_ehn_id(self, ehn: EdgeHostnameResource):
    revision = self.repo.get_last_revision(paths=[ehn.path])
    if revision == None:
      self.get_working_copy_ehn_data(ehn)
      return None
    blob = revision.show_path(ehn.path, textconv=True)
    data = json.loads(blob)
    groupId = data.get('groupId')

  def get_working_copy_ehn_data(self, ehn: EdgeHostnameResource):
    with open(ehn.path, 'r') as fd:
      print(fd.read())
