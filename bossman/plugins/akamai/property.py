import re
import json
from io import StringIO
from os import getenv
from os.path import expanduser, basename, dirname, join
from collections import OrderedDict
import jsonschema

from bossman.cache import cache
from bossman.errors import BossmanError
from bossman.abc import ResourceTypeABC
from bossman.abc import ResourceStatusABC
from bossman.abc import ResourceABC
from bossman.repo import Repo, Revision, RevisionDetails
from bossman.plugins.akamai.lib.papi import PAPIClient, PAPIPropertyVersion, PAPIBulkActivation, PAPIError

RE_COMMIT = re.compile("^commit: ([a-z0-9]*)", re.MULTILINE)

_cache = cache.key(__name__)

class PropertyError(BossmanError):
  pass

class PropertyNotFoundError(BossmanError):
  pass

class PropertyResource(ResourceABC):
  def __init__(self, path, **kwargs):
    super(PropertyResource, self).__init__(path)
    self.__name = kwargs.get("name")

  @property
  def name(self):
    return self.__name

  @property
  def rules_path(self):
    return join(self.path, "rules.json")

  @property
  def hostnames_path(self):
    return join(self.path, "hostnames.json")

  @property
  def paths(self):
    return (self.rules_path, self.hostnames_path)

  def __rich__(self):
    prefix = self.path.replace(self.name, "")
    return "[grey53]{}[/][yellow]{}[/]".format(prefix, self.name)

class PropertyVersionComments:
  @staticmethod
  def from_revision(revision: Revision):
    comments = StringIO()
    comments.write(revision.message.strip())
    comments.write("\n\n")
    comments.write("commit: {}\n".format(revision.id))
    comments.write("branch: {}\n".format(", ".join(revision.branches)))
    comments.write("author: {} <{}>\n".format(revision.author_name, revision.author_email))
    if revision.author_email != revision.committer_email:
      comments.write("committer: {} <{}>\n".format(revision.commit.committer.name, revision.commit.committer.email))
    return PropertyVersionComments(comments.getvalue())

  def __init__(self, comments: str):
    parts = comments.strip().rsplit("\n\n", 1)
    self.message = parts[0]
    self.metadata = (OrderedDict(re.findall(r"^([^:]+):\s*(.*)$", parts[1], re.MULTILINE))
      if len(parts) == 2
      else {})

  def __str__(self) -> str:
    return "{}\n\n{}".format(
      self.message,
      "\n".join(
        "{}: {}".format(k, v)
        for k, v in self.metadata.items()
      )
    )

  @property
  def commit(self):
    return self.metadata.get("commit", None)

  @property
  def subject_line(self):
    # 72 chars matches GitHub guidance, but it's a bit long for the console
    return self.message.split("\n")[0][:40]

  @property
  def branch(self):
    return self.metadata.get("branch", None)

  @property
  def author(self):
    return self.metadata.get("author", None)

  @property
  def committer(self):
    return self.metadata.get("committer", None)

class PropertyStatus(ResourceStatusABC):
  def __init__(self, repo: Repo, resource: PropertyResource, versions: list, error=None):
    self.repo = repo
    self.resource = resource
    self.versions = sorted(versions, key=lambda v: int(v.propertyVersion), reverse=True)
    self.error = error

  @property
  def exists(self):
    return len(self.versions) > 0

  @property
  def dirty(self) -> bool:
    if not self.exists:
      return False
    if self.versions[0].note is not None:
      comments = PropertyVersionComments(self.versions[0].note)
      if comments.commit and self.repo.rev_exists(comments.commit):
        return False
    return True

  def __rich_console__(self, *args, **kwargs):
    if self.error is not None:
      from rich.panel import Panel
      from rich.syntax import Syntax
      import yaml
      error_yaml = yaml.safe_dump(self.error.args[0])
      yield '{}\n{}'.format(type(self.error).__name__, Syntax(error_yaml, "yaml").highlight(error_yaml))
    elif len(self.versions) == 0:
      yield "[gray31]not found[/]"
    else:
      for version in self.versions:
        parts = []
        comments = PropertyVersionComments(version.note)

        parts.append(r'[grey53]v{version}[/]'.format(version=version.propertyVersion))

        networks = []
        for network in ("production", "staging"):
          color = "green" if network == "production" else "magenta"
          alias  = re.sub("[aeiou]", "", network)[:3].upper()
          networkStatusField = "{}Status".format(network)
          networkStatus = getattr(version, networkStatusField)
          statusIndicator = ""
          if networkStatus == "PENDING":
            statusIndicator = ":hourglass:"
          if networkStatus in ("ACTIVE", "PENDING"):
            networks.append("[bold {}]{}{}[/]".format(color, alias,  statusIndicator))
        if len(networks):
          parts.append(",".join(networks))

        if not comments.commit:
          parts.append(":stop_sign: [magenta]dirty[/]")

        if comments.subject_line:
          parts.append(r'[bright_white]"{subject_line}"[/]'.format(subject_line=comments.subject_line))

        def branch_status(branch):
          revs_since = self.repo.get_revisions(comments.commit, branch)
          missing_revs_since = self.repo.get_revisions(comments.commit, branch, self.resource.paths)
          ref = branch
          if len(revs_since):
            ref += "~{}".format(len(revs_since))
          color = "dark_olive_green3"
          if len(missing_revs_since):
            color = "rosy_brown"
          parts.append(r'[{}]\[{}][/]'.format(color, ref))

        if comments.commit:
          rev_branches = self.repo.get_branches_containing(comments.commit)
          if len(rev_branches) == 0:
            # If the comment referenced no commit, or if the commit was not found
            # on any branch (which is possible if history was rewritten or the branch
            # containing that commit was dropped without being merged), indicate question mark
            parts.append(r':question:')
          else:
            for branch in rev_branches:
              branch_status(branch)
            for tag in self.repo.get_tags_pointing_at(comments.commit):
              parts.append(r'[bright_cyan]\[{}][/]'.format(tag))

        author = comments.author
        if author:
          author = author.rsplit(" ", 1)[0]
          parts.append("[grey53]{}[/]".format(author))

        yield " ".join(parts)

class PropertyApplyResult:
  def __init__(self,
              resource: PropertyResource,
              revision: Revision, 
              property_version: PAPIPropertyVersion=None,
              error=None):
    self.resource = resource
    self.revision = revision
    self.property_version = property_version
    self.error = error

  def __rich_console__(self, *args, **kwargs):
    parts = []
    parts.append(r':arrow_up:')
    parts.append(self.resource.__rich__())
    parts.append(r'[grey53]\[{h}][/]'.format(h=self.revision.id))
    if self.property_version:
      parts.append(r'[grey53]v{version}[/]'.format(version=self.property_version.propertyVersion))
    if self.revision.short_message:
      parts.append(r'[bright_white]"{subject_line}"[/]'.format(subject_line=self.revision.short_message))
    author = self.revision.author_name
    if author:
      parts.append("[grey53]{}[/]".format(author))
    yield " ".join(parts)
    if self.error is not None:
      from rich.panel import Panel
      from rich.syntax import Syntax
      import yaml
      error_yaml = yaml.safe_dump(self.error.args[0])
      yield '{}\n{}'.format(type(self.error).__name__, Syntax(error_yaml, "yaml").highlight(error_yaml))

class ResourceTypeOptions:
  def __init__(self, options):
    self.edgerc = expanduser(options.get("edgerc", "~/.edgerc"))
    self.section = options.get("section", "papi")
    self.switch_key = options.get("switch_key", None)

class ResourceType(ResourceTypeABC):
  def __init__(self, repo: Repo, config):
    super(ResourceType, self).__init__(repo, config)
    self.options = ResourceTypeOptions(config.options)
    self.papi = PAPIClient(self.options.edgerc, self.options.section, self.options.switch_key)

  def create_resource(self, path: str, **kwargs):
    return PropertyResource(path, **kwargs)

  def get_resource_status(self, resource: PropertyResource):
    try:
      prop = self.papi.get_property(resource.name)

      interesting_versions = set()
      versions = []

      if prop is not None:
        interesting_versions.add(prop.stagingVersion)
        interesting_versions.add(prop.productionVersion)
        interesting_versions.add(prop.latestVersion)
        for branch in self.repo.get_branches():
          head = self.repo.get_revision(branch, resource.paths)
          notes = head.get_notes(resource.path)
          v = notes.get("property_version", None)
          if v is not None:
            interesting_versions.add(int(v))
        interesting_versions = set(iv for iv in interesting_versions if isinstance(iv, int))
        oldest = min(interesting_versions)
        fetch_last_count = (prop.latestVersion - oldest) + 1

        versions = [
          version 
            for version 
            in self.papi.get_property_versions(prop.propertyId, fetch_last_count)
            if version.propertyVersion in interesting_versions
        ]

      return PropertyStatus(self.repo, resource, versions)
    except PAPIError as e:
      return PropertyStatus(self.repo, resource, [], error=e)

  def is_applied(self, resource: PropertyResource, revision: Revision):
    notes = revision.get_notes(resource.path)
    property_version = notes.get("property_version", None)
    return property_version is not None

  def get_revision_details(self, resource: ResourceABC, revision: Revision) -> RevisionDetails:
    notes = revision.get_notes(resource.path)
    version_number = notes.get("property_version", None)
    return RevisionDetails(id=revision.id, details="v"+str(version_number) if version_number else None)

  def get_property_id(self, property_name):
    property_id = self.papi.get_property_id(property_name)
    if not property_id:
      raise PropertyNotFoundError(property_name, "not found")
    return property_id

  def apply_change(self, resource: PropertyResource, revision: Revision, previous_revision: Revision=None):
    # we should only call this function if the Revision concerns the resource
    assert len(set(resource.paths).intersection(revision.affected_paths)) > 0

    try:
      # Get the rules json from the commit
      rules = revision.show_path(resource.rules_path)
      if rules is None:
        raise PropertyError("missing rule tree")

      # before changing anything in PAPI, check that the json files are valid
      rules_json = self.validate_rules(resource, rules)
      # Update the rule tree with metadata from the revision commit.
      comments = PropertyVersionComments.from_revision(revision)
      rules_json.update(comments=str(comments))

      hostnames_json = None
      hostnames = revision.show_path(resource.hostnames_path)
      hostnames_json = self.validate_hostnames(resource, hostnames)
    except RuntimeError as e:
      return PropertyApplyResult(resource, revision, error=e)

    latest_version = next_version = None

    try:
      property_id = self.get_property_id(resource.name)
      # If previous_revision was provided and this is not a new property, we can
      # figure out the property version to base the new version on
      if previous_revision:
        latest_version = self.get_property_version_for_revision_id(property_id, previous_revision.id)
      # if we failed to figure out the version from a previous revision, we use the latest
      if not latest_version:
        latest_version = self.papi.get_latest_property_version(property_id)
      # now we can create the new version in PAPI
      next_version = self.papi.create_property_version(property_id, latest_version.propertyVersion)
    except PropertyNotFoundError:
      property_id = self.papi.create_property(
        resource.name,
        rules_json.get("productId"),
        rules_json.get("ruleFormat"),
        rules_json.get("contractId"),
        rules_json.get("groupId"),
      )
      try:
        # If we managed to create the property, we can simply use v1
        latest_version = self.papi.get_latest_property_version(property_id)
        next_version = latest_version
      except RuntimeError as e:
        return PropertyApplyResult(resource, revision, error=e)
    except RuntimeError as e:
      return PropertyApplyResult(resource, revision, error=e)

    try:
      # first, we apply the hostnames change
      self.papi.update_property_hostnames(property_id, next_version.propertyVersion, hostnames_json)
      # then, regardless of whether there was a change to the rule tree, we need to update it with
      # the commit message and id, otherwise we will get a dirty status
      result = self.papi.update_property_rule_tree(property_id, next_version.propertyVersion, rules_json)

      # Finally, assign the updated values to the git notes
      revision.get_notes(resource.path).set(
        property_version=result.propertyVersion,
        property_id=result.propertyId,
        etag=result.etag
      )
      return PropertyApplyResult(resource, revision, next_version)
    except RuntimeError as e:
      return PropertyApplyResult(resource, revision, error=e)


  def get_property_version_for_revision_id(self, property_id, revision_id):
    cache = _cache.key("property_version", property_id, revision_id)
    property_version = cache.get_json()
    if property_version is None:
      search = r'commit: {}'.format(revision_id)
      predicate = lambda v: search in v.note
      property_version = self.papi.find_latest_property_version(property_id, predicate)
      if property_version != None:
        cache.update_json(property_version.__dict__)
    else:
      property_version = PAPIPropertyVersion(**property_version)
    return property_version

  def get_last_applied_revision_id(self, property_id):
    """
    Return the last revision id applied to the resource.
    This works by searching for a pattern in the property version notes.
    """
    property_version = self.papi.find_latest_property_version(
      property_id,
      lambda v: RE_COMMIT.search(v.get("note", ""))
    )
    if property_version:
      return RE_COMMIT.search(property_version.get("note")).group(1)
    return None

  def validate_working_tree(self, resource: PropertyResource):
    with open(resource.hostnames_path, "r") as hfd:
      hostnames = hfd.read()
      self.validate_hostnames(resource, hostnames)
    with open(resource.rules_path, "r") as hfd:
      rules = hfd.read()
      self.validate_rules(resource, rules)

  def validate_rules(self, resource: PropertyResource, rules: str):
    try:
      rules_json = json.loads(rules)
      # While these are not mandatory in PAPI, they ARE mandatory in bossman since
      # it is the easiest and most standard way of telling bossman how to validate,
      # version-freeze and create properties without imperative logic.
      requiredFields = ("groupId", "contractId", "ruleFormat", "productId")
      missing = list(field for field in requiredFields if field not in rules_json)
      if len(missing):
        raise PropertyError("{}: {} field is required".format(resource.rules_path, ", ".join(missing)))

      schema = self.papi.get_rule_format_schema(rules_json.get("productId"), rules_json.get("ruleFormat"))
      jsonschema.validate(rules_json, schema)
      return rules_json
    except json.decoder.JSONDecodeError as err:
      self.logger.error("{}: bad rules.json - {}", resource, err.args)
      raise PropertyError(resource, "bad rules.json", err.args)
    except jsonschema.ValidationError as err:
      self.logger.error("{}: invalid rules.json - {}", resource, err.args)
      raise PropertyError(resource, "invalid rules.json", err.args)

  def validate_hostnames(self, resource: PropertyResource, hostnames: str):
    try:
      hostnames_json = json.loads(hostnames)
      schema = self.papi.get_request_schema("SetPropertyVersionsHostnamesRequestV0.json")
      jsonschema.validate(hostnames_json, schema)
      return hostnames_json
    except json.decoder.JSONDecodeError as err:
      self.logger.error("{}: bad hostnames.json - {}", resource, err.args)
      raise PropertyError(resource, "bad hostnames.json", err.args)
    except jsonschema.ValidationError as err:
      self.logger.error("{}: bad hostnames.json - {}", resource, err.args)
      raise PropertyError(resource, "invalid hostnames.json", err.args)

  def _release(self, resources: list, revision: Revision, network: str):
    bulk_activation = PAPIBulkActivation()
    resources = sorted(resources)
    for resource in resources:
      notes = revision.get_notes(resource.path)
      property_id = notes.get("property_id")
      property_version = notes.get("property_version")
      if property_version:
        print("{}: {}".format(resource.path, "preparing to activate {}@{} (v{}) on {}`)".format(resource.path, revision.id, property_version, network)))
        emails = [revision.author_email]
        if revision.committer_email and revision.committer_email != revision.author_email:
          emails.append(revision.committer_email)
        bulk_activation.add(property_id, property_version, network, emails)
      else:
        print("{}: {}".format(resource.path, "skipping {}@{} (use `bossman apply --rev {} {}`)".format(resource.path, revision.id, revision.id, resource.path)))
    if bulk_activation.length > 0:
      result = self.papi.bulk_activate(bulk_activation)
      for resource in resources:
        status = result.get(resource.name)
        if status is not None:
          msg = "activation of v{propertyVersion} on {network} started".format(**status)
          if status.get("taskStatus") == "SUBMISSION_ERROR":
            fatalError = json.loads(status.get("fatalError"))
            msg = "activation of v{propertyVersion} on {network} failed: {error}".format(error=fatalError.get("title", status.get("taskStatus")), **status)
          print("{}: {}".format(resource.path, msg))

  def prerelease(self, resources: list, revision: Revision):
    self._release(resources, revision, "STAGING")

  def release(self, resources: list, revision: Revision):
    self._release(resources, revision, "PRODUCTION")
