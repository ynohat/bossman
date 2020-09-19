from abc import ABC, abstractmethod, abstractproperty
import git
from os.path import basename
from bossman.errors import BossmanError
from bossman.logging import get_class_logger
from datetime import datetime
import gitdb.exc

def true(*args, **kwargs):
  return True

def short_rev(rev):
  return rev[:8] if rev else rev

class RepoError(RuntimeError):
  pass

class TreeVisitor:
  """
  Callable to visit all the blobs in a tree.
  """
  def __init__(self, func):
    self.func = func

  def __call__(self, tree: git.objects.tree.Tree):
    def visit(blob, visited):
      if blob.path in visited:
        return # avoid infinite recursion
      visited.add(blob.path)
      if type(blob) == git.Tree:
        for child in blob:
          visit(child, visited)
      elif type(blob) == git.Blob:
        self.func(blob)
    visit(tree, set())

class Change(ABC):
  @staticmethod
  def from_diff(diff: git.diff.Diff):
    if diff.change_type == "R":
      return RenameChange(diff)
    if diff.change_type == "A":
      return AddChange(diff)
    if diff.change_type == "M":
      return ModifyChange(diff)
    if diff.change_type == "D":
      return DeleteChange(diff)
    raise RepoError("unknown change type {}".format(diff.change_type))

  def __init__(self, diff: git.Diff):
    self.diff = diff

  @property
  def path(self):
    return self.diff.b_path

  @property
  def contents(self):
    return self.diff.b_blob.data_stream.read()

  @property
  def diff_text(self):
    return str(self.diff)

  def __str__(self):
    return "{} {}".format(self.diff.change_type, self.path)

  def __rich_console__(self, console, options):
    color = "yellow"
    yield "[{color}]{change_type} {name}[{color}]".format(
      color=color,
      change_type=self.diff.change_type,
      name=basename(self.path),
    )

class AddChange(Change):
  pass

class RenameChange(Change):
  @property
  def from_path(self):
    return self.diff.a_path

class ModifyChange(Change):
  pass

class DeleteChange(Change):
  @property
  def path(self):
    return self.diff.a_path

  @property
  def contents(self):
    return self.diff.a_blob.data_stream.read()



class Revision:
  def __init__(self, commit: git.Commit, diffs: git.Diff):
    self.commit = commit
    self.changes = dict(
      (diff.b_path or diff.a_path, Change.from_diff(diff))
      for diff
      in diffs
    )

  @property
  def id(self):
    return short_rev(self.commit.hexsha)

  @property
  def parent_id(self):
    try:
      return short_rev(self.commit.parents[0].hexsha)
    except IndexError:
      return None

  @property
  def branches(self):
    cmd = git.cmd.Git(self.commit.repo.working_tree_dir)
    branches = cmd.branch(contains=self.id, format="%(refname:short)")
    return branches.splitlines()

  @property
  def date(self) -> datetime:
    return self.commit.committed_datetime

  @property
  def message(self) -> str:
    return self.commit.message

  @property
  def short_message(self) -> str:
    return self.message.split("\n").pop(0)

  @property
  def author_name(self) -> str:
    return self.commit.author.name

  @property
  def author_email(self) -> str:
    return self.commit.author.email

  def affected_paths(self) -> list:
    return self.changes.keys()

  def show_path(self, path) -> dict:
    contents = self.show_paths([path])
    return contents.get(path, None)

  def show_paths(self, paths: list) -> dict:
    contents = dict()
    def get_blob_contents(blob):
      if blob.path in paths:
        contents[blob.path] = blob.data_stream.read()
    visitor = TreeVisitor(get_blob_contents)
    visitor(self.commit.tree)
    return contents

  def get_changes(self, paths: str) -> Change:
    return list(change for (path, change) in self.changes.items() if path in paths)

  def get_change(self, path: str) -> Change:
    return self.changes.get(path, None)

  def __str__(self):
    s = "[{}] {} {} | {}".format(self.id, self.short_message, self.author_name, self.date)
    if len(self.changes):
      s += "\n\n  "
      s += "\n  ".join(str(change) for change in self.changes.values())
      s += "\n"
    return s

  def __rich_console__(self, console, options):
    yield "[b][{}][/b] {} | {} {}".format(self.id, self.short_message, self.author_name, self.date)
    # for change in self.changes.values():
    #   yield change

class RevisionDetails:
  """
  Bossman creates new versions of resources through plugins. It doesn't need
  to know much about the implementation details of the plugin, but it does
  provide an opportunity to give context about an applied revision.
  
  Instances of this class join a revision id to plugin specific details, which
  could typically be a remote version number.
  """
  def __init__(self, id, details):
    self.id = id
    self.details = details

  def __str__(self):
    return "{} ({})".format(self.id, self.details)

class Repo:
  def __init__(self, root):
    self.logger = get_class_logger(self)
    self._repo = git.Repo(root)

  def get_paths(self, rev: str = "HEAD", predicate = true) -> list:
    """
    Lists the paths versioned for revision {rev}, optionally filtered
    by {predicate}.
    """
    try:
      commit = self._repo.rev_parse(rev)
    except gitdb.exc.BadName:
      raise BossmanError("This branch likely has no commits yet.")

    paths = []
    visitor = TreeVisitor(lambda blob: paths.append(blob.path))
    visitor(commit.tree)
    return paths

  def get_last_revision(self, paths: list, rev: str = "HEAD") -> Revision:
    try:
      commit = next(self._repo.iter_commits(rev, paths=paths))
      prev = git.NULL_TREE
      if commit.parents:
        prev = commit.parents[0]
      diffs = commit.diff(prev, paths=paths, R=True)
      return Revision(commit, diffs)
    except StopIteration:
      return None

  def get_revision(self, rev: str, paths: list = None):
    commit = self._repo.rev_parse(rev)
    prev = git.NULL_TREE
    diffs = []
    if commit.parents:
      prev = commit.parents[0]
      diffs = commit.diff(prev, paths=paths, R=True) # R=True -> reverse
    return Revision(commit, diffs)

  def get_revisions(self, since_rev: str = None, until_rev: str = "HEAD",  paths: list = None) -> list:
    commitRange = ("{since_rev}..{until_rev}".format(since_rev=since_rev, until_rev=until_rev)
      if since_rev
      else until_rev)
    commits = self._repo.iter_commits(commitRange, paths=paths)
    revisions = []
    for commit in commits:
      prev = git.NULL_TREE
      if commit.parents:
        prev = commit.parents[0]
      diffs = commit.diff(prev, paths=paths, R=True) # R=True -> reverse
      if len(diffs):
        revisions.append(Revision(commit, diffs))
    return revisions
