from abc import ABC, abstractmethod, abstractproperty
import git
from os.path import basename
from bossman.errors import BossmanError
from bossman.logging import get_class_logger
from datetime import datetime
import gitdb.exc
import yaml
import threading

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
  def basename(self):
    return basename(self.path)

  @property
  def change_type(self):
    return self.diff.change_type

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
      name=self.basename,
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

class Notes:
  def __init__(self, repo, commit: git.Commit, ns: str = None):
    self.repo = repo
    self.commit = commit
    self.ns = ns.strip("/")

  def set(self, **kwargs):
    notes = self.read()
    notes.update(kwargs)
    self.write(notes)

  def get(self, k: str, default=None):
    notes = self.read()
    return notes.get(k, default)

  def read(self) -> dict:
    with self.repo._lock:
      try:
        args = []
        if self.ns is not None:
          args.extend(("--ref", self.ns))
        args.extend(("show", self.commit.hexsha))
        notes = self.commit.repo.git.notes(*args)
        return yaml.safe_load(notes if notes else '{}')
      except git.GitCommandError:
        return {}

  def write(self, notes):
    try:
      with self.repo._lock:
        args = []
        if self.ns is not None:
          args.extend(("--ref", self.ns))
        args.extend(("add", "-f", "-m", yaml.safe_dump(notes), self.commit.hexsha))
        self.commit.repo.git.notes(*args)
    except git.GitCommandError as err:
      raise BossmanError(err)



class Revision:
  def __init__(self, repo, commit: git.Commit, diffs: git.Diff):
    self.repo = repo
    self.commit = commit
    self.changes = dict(
      (diff.b_path or diff.a_path, Change.from_diff(diff))
      for diff
      in diffs
    )

  @property
  def id(self):
    with self.repo._lock:
      return short_rev(self.commit.hexsha)

  @property
  def parent_id(self):
    try:
      with self.repo._lock:
        return short_rev(self.commit.parents[0].hexsha)
    except IndexError:
      return None

  @property
  def branches(self):
    with self.repo._lock:
      return self.repo.get_branches_containing(self.id)

  @property
  def date(self) -> datetime:
    with self.repo._lock:
      return self.commit.committed_datetime

  @property
  def message(self) -> str:
    with self.repo._lock:
      return self.commit.message

  @property
  def short_message(self) -> str:
    with self.repo._lock:
      return self.message.split("\n").pop(0)

  @property
  def author_name(self) -> str:
    with self.repo._lock:
      return self.commit.author.name

  @property
  def author_email(self) -> str:
    with self.repo._lock:
      return self.commit.author.email

  @property
  def committer_name(self) -> str:
    with self.repo._lock:
      return self.commit.committer.name

  @property
  def committer_email(self) -> str:
    with self.repo._lock:
      return self.commit.committer.email

  @property
  def affected_paths(self) -> list:
    with self.repo._lock:
      return self.changes.keys()

  def show_path(self, path) -> dict:
    with self.repo._lock:
      contents = self.show_paths([path])
      return contents.get(path, None)

  def show_paths(self, paths: list) -> dict:
    with self.repo._lock:
      contents = dict()
      def get_blob_contents(blob):
        if blob.path in paths:
          contents[blob.path] = blob.data_stream.read()
      visitor = TreeVisitor(get_blob_contents)
      visitor(self.commit.tree)
      return contents

  def get_changes(self, paths: str) -> Change:
    with self.repo._lock:
      return list(change for (path, change) in self.changes.items() if path in paths)

  def get_change(self, path: str) -> Change:
    with self.repo._lock:
      return self.changes.get(path, None)

  def get_notes(self, ns: str = None) -> Notes:
    with self.repo._lock:
      return Notes(self.repo, self.commit, ns)

  def __str__(self):
    with self.repo._lock:
      s = "[{}] {} {} | {}".format(self.id, self.short_message, self.author_name, self.date)
      if len(self.changes):
        s += "\n\n  "
        s += "\n  ".join(str(change) for change in self.changes.values())
        s += "\n"
      return s

  def __rich_console__(self, console, options):
    with self.repo._lock:
      yield "[b]\[{}][/b] {} | {} {}".format(self.id, self.short_message, self.author_name, self.date)
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

def synchronized(method):
  def wrapper(self, *arg, **kws):
    with self._lock:
      return method(self, *arg, **kws)
  return wrapper

class Repo:

  def __init__(self, root):
    self.logger = get_class_logger(self)
    self._repo = git.Repo(root)
    self._lock = threading.RLock()

  def config_writer(self):
    return self._repo.config_writer()

  @synchronized
  def rev_parse(self, rev: str) -> str:
    # We can't use Repo.rev_parse since it doesn't support
    # short hexshas or indirect refs such as tag names or branches.
    try:
      hexsha = self._repo.git.rev_parse(rev)
      return self._repo.rev_parse(hexsha)
    except git.GitCommandError:
      raise BossmanError("failed to resolve revision {}, please make sure it is a valid commit/tag name".format(rev))

  @synchronized
  def rev_exists(self, rev: str) -> str:
    try:
      return isinstance(self.rev_parse(rev), git.Commit)
    except BossmanError:
      return False

  @synchronized
  def rev_is_reachable(self, rev: str, from_rev: str = "HEAD") -> str:
    """
    Returns True if {rev} is an ancestor of {from_rev}.
    """
    try:
      rev = self.rev_parse(rev)
      for parent_rev in self._repo.iter_commits(from_rev):
        if parent_rev.hexsha == rev.hexsha:
          return True
      else:
        return False
    except BossmanError:
      return False

  @synchronized
  def get_paths(self, rev: str = "HEAD", predicate = true) -> list:
    """
    Lists the paths versioned for revision {rev}, optionally filtered
    by {predicate}.
    """
    try:
      commit = self.rev_parse(rev)
    except gitdb.exc.BadName:
      raise BossmanError("This branch likely has no commits yet.")

    paths = []
    visitor = TreeVisitor(lambda blob: paths.append(blob.path))
    visitor(commit.tree)
    return paths

  @synchronized
  def get_head(self):
    """
    Returns the HEAD revision, or None if this is the first commit.
    """
    try:
      commit = next(self._repo.iter_commits())
      prev = git.NULL_TREE
      if commit.parents:
        prev = commit.parents[0]
      diffs = commit.diff(prev, R=True)
      return Revision(self, commit, diffs)
    except StopIteration:
      return None

  @synchronized
  def get_last_revision(self, paths: list, rev: str = "HEAD") -> Revision:
    """
    Returns the last revision in {rev}'s ancestry to have affected {paths}.
    """
    try:
      rev = self.rev_parse(rev)
      commit = next(self._repo.iter_commits(rev, paths=paths))
      prev = git.NULL_TREE
      if commit.parents:
        prev = commit.parents[0]
      diffs = commit.diff(prev, paths=paths, R=True)
      return Revision(self, commit, diffs)
    except StopIteration:
      return None

  @synchronized
  def get_revision(self, rev: str, paths: list = None):
    """
    Returns the revision {rev}, with diffs for {paths}.
    """
    commit = self.rev_parse(rev)
    prev = git.NULL_TREE
    diffs = []
    if commit.parents:
      prev = commit.parents[0]
      diffs = commit.diff(prev, paths=paths, R=True) # R=True -> reverse
    return Revision(self, commit, diffs)

  @synchronized
  def get_current_branch(self):
    return self._repo.head.ref.name

  @synchronized
  def get_branches(self) -> list:
    return tuple(branch.name for branch in self._repo.branches)

  @synchronized
  def get_branches_containing(self, rev: str) -> list:
    try:
      result = self._repo.git.branch(contains=rev, format="%(refname:short)")
      return result.splitlines()
    except git.GitCommandError:
      return []

  @synchronized
  def get_revisions(self, since_rev: str = None, until_rev: str = "HEAD",  paths: list = None) -> list:
    """
    Returns all revisions having affected {paths} in the ancestry of {until_rev}, bounded by {since_rev} if
    specified.
    """
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
        revisions.append(Revision(self, commit, diffs))
    return revisions

  @synchronized
  def get_tags_pointing_at(self, rev="HEAD") -> list:
    try:
      rev = self.rev_parse(rev)
      result = self._repo.git.tag(points_at=rev)
      return result.splitlines()
    except BossmanError:
      return []