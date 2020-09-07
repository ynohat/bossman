import sys
from os.path import dirname, join

sys.path.append(dirname(__file__))




from src.logger import logger


def get_property_notes():
  from textwrap import dedent
  from src.git import get_head_info
  head = get_head_info()
  return dedent(
    """\
    {message}
    commit: {commit}\
    """
  ).format(
    message=head.message,
    commit=head.commit,
    branch=head.branch
  )

def get_latest_git_version(propertyName):
  from src.papi import PAPIClient
  import re
  papi = PAPIClient("/Users/ahogg/.edgerc", "lvm")
  propertyId = papi.get_property_id(propertyName)
  latestGitVersion = papi.find_latest_property_version(
    propertyId,
    lambda v: RE_PROPERTY_NOTE_COMMIT.search(v.get("note", ""))
  )
  return latestGitVersion


def get_latest_version(propertyName):
  from src.papi import PAPIClient
  papi = PAPIClient("/Users/ahogg/.edgerc", "lvm")
  propertyId = papi.get_property_id(propertyName)
  latestVersion = papi.get_latest_property_version(propertyId)
  return latestVersion

class PropertyStatus:
  def __init__(self, propertyName):
    self.name = propertyName
    self.latestVersion = None
    self.latestCommit = None
    self.latestCommitVersion = None
    self.dirty = True
    self.outdated = False

def get_property_rule_tree(propertyName):
  from os.path import join
  import json
  ruleTreePath = join("build", "property", propertyName, "rules.json")
  return json.load(open(ruleTreePath, "r"))

def get_property_status(propertyName):
  status = PropertyStatus(propertyName)
  latestVersion = get_latest_version(propertyName)
  status.latestVersion = latestVersion.get("propertyVersion")
  latestGitVersion = get_latest_git_version(propertyName)
  if latestGitVersion:
    status.latestCommit = RE_PROPERTY_NOTE_COMMIT.search(latestGitVersion.get("note")).group(1)
    status.dirty = latestVersion.get("propertyVersion") != latestGitVersion.get("propertyVersion")
  return status

def update_property(propertyName):
  def really_update_property():
    papi = PAPIClient("/Users/ahogg/.edgerc", "lvm")
    propertyId = papi.get_property_id(propertyName)
    ruleTree = get_property_rule_tree(propertyName)
    ruleTree.update(comments=get_property_notes())
    version = papi.create_property_version(propertyId, status.latestCommitVersion if status.latestCommitVersion else status.latestVersion)
    papi.update_property_rule_tree(propertyId, version.get("propertyVersion"), ruleTree)

  from src.papi import PAPIClient
  status = get_property_status(propertyName)
  if status.dirty:
    logger.warning("property {propertyName} is dirty".format(propertyName=propertyName))
    really_update_property()
  elif status.outdated:
    really_update_property()
  else:
    print("nothing to do")

update_property("lvm-static_jsonnettest")

# def get_changes(dir):
#   repo = get_git_repo()
#   return [
#     (diff.change_type, diff.b_path if diff.b_path else diff.a_path)
#     for diff in  repo.head.commit.diff(None)
#     if diff.a_mode != None and diff.b_mode != None and diff.b_path.startswith(dir)
#   ]
# changes = get_changes("build/")
# print(changes)

# print(get_property_notes())
