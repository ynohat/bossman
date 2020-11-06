import re
import json
from io import StringIO
from os import getenv
from os.path import expanduser, basename, dirname, join
from collections import OrderedDict
import jsonschema

from bossman.cache import cache
from bossman.errors import BossmanError
from bossman.abc.resource_type import ResourceTypeABC
from bossman.abc.resource_status import ResourceStatusABC
from bossman.abc.resource import ResourceABC
from bossman.repo import Repo, Revision, RevisionDetails
from bossman.plugins.akamai.lib.papi import PAPIClient, PAPIBulkActivation

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
    prefix = self.path.rstrip("/").replace(self.name, "")
    return "[grey37]{}[/][yellow]{}[/]".format(prefix, self.name)

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
    return self.message.split("\n")[0][:72] # 72 chars matches GitHub guidance

  @property
  def branch(self):
    return self.metadata.get("branch", None)

  @property
  def author(self):
    return self.metadata.get("author", None)

  @property
  def committer(self):
    return self.metadata.get("committer", None)

class PropertyResourceStatus(ResourceStatusABC):
  def __init__(self, resource: PropertyResource, versions: list):
    self.resource = resource
    self.versions = sorted(versions, key=lambda v: int(v.get("propertyVersion")), reverse=True)

  @property
  def exists(self):
    return len(self.versions) > 0

  @property
  def dirty(self) -> bool:
    if not self.exists:
      return False
    comments = PropertyVersionComments(self.versions[0].get("note", ""))
    if comments.commit:
      return False
    return True

  def __rich_console__(self, *args, **kwargs):
    if len(self.versions) == 0:
      yield "[gray31]not found[/]"
    else:
      for version in self.versions:
        parts = []
        comments = PropertyVersionComments(version.get("note", ""))

        networks = []
        for network in ("production", "staging"):
          color = "green" if network == "production" else "magenta"
          alias  = re.sub("[aeiou]", "", network)[:3].upper()
          networkStatusField = "{}Status".format(network)
          networkStatus = version.get(networkStatusField)
          statusIndicator = ""
          if networkStatus == "PENDING":
            statusIndicator = ":hourglass:"
          if networkStatus in ("ACTIVE", "PENDING"):
            networks.append("[bold {}]{}{}[/]".format(color, alias,  statusIndicator))
        if len(networks):
          parts.append(r"\[" + ",".join(networks) + "]")

        version_map = (
          "v{} : {}".format(version.get("propertyVersion"), comments.commit)
          if comments.commit
          else "v{} :red_circle:".format(version.get("propertyVersion"))
        )
        parts.append(r'[bright_white]"{subject_line}"[/] [gray]({version})[/]'.format(subject_line=comments.subject_line, version=version_map))

        yield " ".join(parts)

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
    versions = self.papi.find_by_property_name(resource.name)
    return PropertyResourceStatus(resource, versions)

  def is_applied(self, resource: PropertyResource, revision: Revision):
    notes = revision.get_notes(resource.path)
    property_version = notes.get("property_version", None)
    return property_version is not None

  def get_revision_details(self, resource: ResourceABC, revision: Revision) -> RevisionDetails:
    version_number = None
    notes = revision.get_notes(resource.path)
    property_id = notes.get("property_id")
    if property_id is None:
      property_id = self.papi.get_property_id(resource.name)
    if property_id is not None: # if the property exists
      version_number = notes.get("property_version", None)
      if version_number is None:
        property_version = self.get_property_version_for_revision_id(property_id, revision.id)
        if property_version:
          notes.set(
            property_version=property_version.get("propertyVersion"),
            property_id=property_version.get("propertyId"),
            etag=property_version.get("etag")
          )
          version_number = property_version.get("propertyVersion")
    return RevisionDetails(id=revision.id, details="v"+str(version_number) if version_number else None)

  def get_property_id(self, property_name):
    property_id = self.papi.get_property_id(property_name)
    if not property_id:
      raise PropertyNotFoundError(property_name, "not found")
    return property_id

  def apply_change(self, resource: PropertyResource, revision: Revision, previous_revision: Revision=None):
    # we should only call this function if the Revision concerns the resource
    assert len(set(resource.paths).intersection(revision.affected_paths)) > 0

    # Get the rules json from the commit
    rules = revision.show_path(resource.rules_path)
    if rules is None:
      raise PropertyError("missing rule tree")

    # before changing anything in PAPI, check that the json files are valid
    rules_json = self.validate_rules(resource, rules)
    hostnames_json = None
    if resource.hostnames_path in revision.affected_paths:
      hostnames = revision.show_path(resource.hostnames_path)
      hostnames_json = self.validate_hostnames(resource, hostnames)

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
      next_version = self.papi.create_property_version(property_id, latest_version.get("propertyVersion"))
      print("created new version: ", next_version.get("propertyVersion"), "for rev", revision.id, revision.message)
    except PropertyNotFoundError:
      requiredForCreate = ("groupId", "contractId", "ruleFormat", "productId")
      missing = list(field for field in requiredForCreate if field not in rules_json)
      if len(missing):
        raise PropertyError("missing fields in {}: {}".format(resource.rules_path, ", ".join(missing)))
      property_id = self.papi.create_property(
        resource.name,
        rules_json.get("productId"),
        rules_json.get("ruleFormat"),
        rules_json.get("contractId"),
        rules_json.get("groupId"),
      )
      # If we managed to create the property, we can simply use v1
      latest_version = self.papi.get_latest_property_version(property_id)
      next_version = latest_version

    # first, we apply the hostnames change
    if hostnames_json:
      self.papi.update_property_hostnames(property_id, next_version.get("propertyVersion"), hostnames_json)
    # then, regardless of whether there was a change to the rule tree, we need to update it with
    # the commit message and id, otherwise we will get a dirty status
    comments = PropertyVersionComments.from_revision(revision)
    rules_json.update(comments=str(comments))
    result = self.papi.update_property_rule_tree(property_id, next_version.get("propertyVersion"), rules_json)

    # Finally, assign the updated values to the git notes
    revision.get_notes(resource.path).set(
      property_version=result.get("propertyVersion"),
      property_id=result.get("propertyId"),
      etag=result.get("etag")
    )

  def get_property_version_for_revision_id(self, property_id, revision_id):
    cache = _cache.key("property_version", property_id, revision_id)
    property_version = cache.get_json()
    if property_version is None:
      search = r'commit: {}'.format(revision_id)
      predicate = lambda v: search in v.get("note", "")
      property_version = self.papi.find_latest_property_version(property_id, predicate)
      if property_version != None:
        cache.update_json(property_version)
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
      # it is the easiest and most standard way of telling bossman how to validate
      # and version-freeze.
      if not "productId" in rules_json:
        raise PropertyError("{}: productId field is missing")
      if not "ruleFormat" in rules_json:
        raise PropertyError("{}: ruleFormat field is missing")

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
      if property_id is None:
        try:
          property_id = self.get_property_id(resource.name)
          if property_id:
            notes.set(property_id=property_id)
        except:
          pass
      property_version = notes.get("property_version")
      if property_version is None:
        try:
          property_version = self.get_property_version_for_revision_id(property_id, revision.id)
          if property_version:
            property_version = property_version.get("propertyVersion")
            notes.set(property_version=property_version)
        except:
          pass
      if property_version:
        print("{}: {}".format(resource.path, "preparing to activate {}@{} (v{}) on {}`)".format(resource.path, revision.id, property_version, network)))
        bulk_activation.add(property_id, property_version, network, [revision.author_email])
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
