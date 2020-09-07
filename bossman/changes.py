from os.path import basename
from bossman.repo import Commit, Diff
from bossman.abc.resource import ResourceABC
from collections import OrderedDict

class ChangeSet:
  def __init__(self, commit: Commit):
    self.rev = commit.rev
    self.message = commit.message
    self.author = commit.author
    self.date = commit.date
    self.resource_changes = OrderedDict()

  @property
  def message_firstline(self):
    return self.message.split("\n")[0]

  def add_resource_diff(self, resource: ResourceABC, diff: Diff):
    if not (resource in self.resource_changes):
      self.resource_changes[resource] = Change(resource)
    change = self.resource_changes.get(resource)
    change.diffs.append(diff)

  def __str__(self):
    s = "[{rev}] {date} {message} | {author}".format(rev=self.rev, message=self.message_firstline, author=self.author, date=self.date)
    if len(self.resource_changes):
      s += "\n\n  "
      s += "\n  ".join(str(change) for change in self.resource_changes.values())
      s += "\n"
    return s

  def __rich_console__(self, console, options):
    yield "[b][{}][/b] {} | {} {}".format(self.rev, self.message_firstline, self.author, self.date)
    for change in self.resource_changes.values():
      yield change

class Change:
  def __init__(self, resource: ResourceABC):
    self.resource = resource
    self.diffs = []

  def __str__(self):
    s = "{resource:<58} (".format(resource=str(self.resource))
    s += ", ".join(map(format_diff, self.diffs))
    s += ")"
    return s

  def __rich_console__(self, console, options):
    from rich.table import Table
    grid = Table.grid(expand=False, pad_edge=True, padding=(0, 2))
    for diff in self.diffs:
      grid.add_row(self.resource, format_diff(diff))
    yield grid

def format_diff(diff):
  if diff.change_type in 'D':
    return diff.change_type + " " + basename(diff.a_path)
  elif diff.change_type == 'R':
    return diff.change_type + " " + basename(diff.b_path)
  else:
    return diff.change_type + " " + basename(diff.b_path)
