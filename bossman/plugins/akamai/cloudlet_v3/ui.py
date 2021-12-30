import re
from functools import cached_property
from typing import List
from bossman.abc import ResourceApplyResultABC, ResourceStatusABC
from bossman.errors import BossmanError
from bossman.plugins.akamai.cloudlet_v3.resource import SharedPolicyResource
from bossman.plugins.akamai.cloudlet_v3.data import Network, SharedPolicyActivationStatus, SharedPolicyVersion, SharedPolicyActivation
from bossman.plugins.akamai.utils import GenericVersionComments
from bossman.repo import Repo, Revision
from bossman.rich import bracketize



class SharedPolicyVersionStatus:
  def __init__(self, repo: Repo, resource: SharedPolicyResource, policyVersion: SharedPolicyVersion, productionActivation: SharedPolicyActivation, stagingActivation: SharedPolicyActivation):
    self.repo = repo
    self.resource = resource
    self.policyVersion = policyVersion
    self.productionActivation = productionActivation
    self.stagingActivation = stagingActivation

  @property
  def version(self) -> int:
    return self.policyVersion.version

  @cached_property
  def comments(self) -> GenericVersionComments:
    return GenericVersionComments(self.policyVersion.description)

  @cached_property
  def author(self):
    return self.comments.author or self.policyVersion.modifiedBy

  @cached_property
  def productionStatus(self):
    return self.productionActivation.status if self.productionActivation != None else None

  @cached_property
  def stagingStatus(self):
    return self.stagingActivation.status if self.stagingActivation != None else None

  def __rich_console__(self, *args, **kwargs):
    parts = []
    comments = self.comments

    parts.append(r'[grey53]v{version}[/]'.format(version=self.version))

    if comments.commit:
      try:
        revision = self.repo.get_revision(comments.commit, self.resource.paths)
        notes = revision.get_notes(self.resource.path)
        if notes.get("has_errors", False) == True:
          parts.append(":boom:")
      except BossmanError:
        # if the commit is not found, maybe it wasn't pushed by the other party
        pass

    networks = []
    for network in (Network.PRODUCTION, Network.STAGING):
      networkStatus = self.productionStatus if network == Network.PRODUCTION else self.stagingStatus
      statusIndicator = ""
      if networkStatus == SharedPolicyActivationStatus.IN_PROGRESS:
        statusIndicator = ":hourglass:"
      if networkStatus in (SharedPolicyActivationStatus.SUCCESS, SharedPolicyActivationStatus.IN_PROGRESS):
        networks.append("[bold {}]{}{}[/]".format(network.color, network.alias,  statusIndicator))
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
      parts.append(r'[{}]{}[/]'.format(color, bracketize(ref)))

    if comments.commit:
      parts.append(r'[grey53]{}[/]'.format(bracketize(comments.commit)))
      rev_branches = []
      if self.repo.rev_is_reachable(comments.commit):
        rev_branches.append(self.repo.get_current_branch())
      rev_branches += self.repo.get_branches(points_at=comments.commit, all=True)
      rev_branches = list(dict.fromkeys(rev_branches))
      for branch in rev_branches:
        branch_status(branch)
      for tag in self.repo.get_tags_pointing_at(comments.commit):
        parts.append(r'[bright_cyan]{}[/bright_cyan]'.format(bracketize(tag)))

    if self.author:
      parts.append("[grey53]{}[/]".format(self.author.rsplit(" ", 1)[0]))

    yield " ".join(parts)



class SharedPolicyStatus(ResourceStatusABC):
  def __init__(self, repo: Repo, resource: SharedPolicyResource, versions: List[SharedPolicyVersionStatus], exists: bool, error=None):
    self.repo = repo
    self.resource = resource
    self.versions = sorted(versions, key=lambda v: int(v.version), reverse=True)
    self._exists = exists
    self.error = error

  @property
  def exists(self) -> bool:
    return self._exists

  @property
  def dirty(self) -> bool:
    if not self.exists:
      return False
    if len(self.versions) == 0:
      return False
    comments = self.versions[0].comments
    if comments.commit:
        return False
    return True

  def __rich_console__(self, *args, **kwargs):
    if self.error is not None:
      from rich.panel import Panel
      from rich.syntax import Syntax
      import yaml
      error_yaml = yaml.safe_dump(self.error.args[0])
      yield '{}\n{}'.format(type(self.error).__name__, Syntax(error_yaml, "yaml").highlight(error_yaml))
    elif not self.exists:
      yield "[gray31]not found[/]"
    elif len(self.versions) == 0:
      yield "[gray31]no policy versions[/]"
    else:
      for version in self.versions:
        yield version

class SharedPolicyApplyResult(ResourceApplyResultABC):
  def __init__(self,
              resource: SharedPolicyResource,
              revision: Revision,
              policy_version: SharedPolicyVersion=None,
              error=None):
    self.resource = resource
    self.revision = revision
    self.policy_version = policy_version
    self.error = error

  @property
  def had_errors(self) -> bool:
    return self.error != None

  def __rich_console__(self, *args, **kwargs):
    parts = []
    parts.append(r':arrow_up:')
    parts.append(self.resource.__rich__())
    parts.append(r'[grey53][{h}][/]'.format(h=self.revision.id))
    if self.policy_version:
      parts.append(r'[grey53]v{version}[/]'.format(version=self.policy_version.version))
    if self.revision.short_message:
      parts.append(r'[bright_white]"{subject_line}"[/]'.format(subject_line=self.revision.short_message))
    author = self.revision.author_name
    if author:
      parts.append("[grey53]{}[/]".format(author))
    if self.had_errors:
      parts.append(":boom:")
    yield " ".join(parts)
    if self.error is not None:
      from rich.panel import Panel
      from rich.syntax import Syntax
      import yaml
      error_yaml = yaml.safe_dump(self.error.args[0])
      yield '{}\n{}'.format(type(self.error).__name__, Syntax(error_yaml, "yaml").highlight(error_yaml))
