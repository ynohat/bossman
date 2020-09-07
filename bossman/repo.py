import git
from bossman.logging import get_class_logger

def true(*args, **kwargs):
  return True

def short_rev(rev):
  return rev[:8] if rev else rev

class Diff:
  def __init__(self, diff: git.Diff):
    self.change_type = diff.change_type
    self.a_path = diff.a_path
    self.a_blob = diff.a_blob
    self.b_path = diff.b_path
    self.b_blob = diff.b_blob

class Commit:
  def __init__(self, commit: git.Commit):
    self.rev = short_rev(commit.hexsha)
    self.date = commit.committed_datetime
    self.message = commit.message
    self.author = commit.author
    self.diffs = []

class Repo:
  def __init__(self, root):
    self.logger = get_class_logger(self)
    self._repo = git.Repo(root)

  def get_paths(self, rev: str = "HEAD", predicate = true) -> list:
    """
    Lists the paths versioned for revision {rev}, optionally filtered
    by {predicate}.
    """
    commit = self._repo.rev_parse(rev)
    paths = []
    def visit(blob, visited):
      if blob.path in visited:
        return # avoid infinite recursion
      visited.add(blob.path)
      if type(blob) == git.Tree:
        for child in blob:
          visit(child, visited)
      elif type(blob) == git.Blob:
        if predicate(blob.path):
          # the repository likely contains non-resource files too
          paths.append(blob.path)
    visit(commit.tree, set())
    return paths

  def get_last_change_rev(self, paths: list, rev: str = "HEAD") -> str:
    try:
      commit = next(self._repo.iter_commits(rev, paths=paths))
      return short_rev(commit.hexsha)
    except StopIteration:
      return None

  def get_commits(self, since_rev: str = None, until_rev: str = "HEAD",  paths: list = None) -> list:
    commitRange = ("{since_rev}..{until_rev}".format(since_rev=since_rev, until_rev=until_rev)
      if since_rev
      else until_rev)
    commits = self._repo.iter_commits(commitRange, paths=paths)
    diffSets = []
    for commit in commits:
      prev = git.NULL_TREE
      if commit.parents:
        prev = commit.parents[0]
      diffs = commit.diff(prev, paths=paths, R=True) # R=True -> reverse
      if len(diffs):
        diffSet = Commit(commit)
        for diff in diffs:
          diffSet.diffs.append(Diff(diff))
        diffSets.append(diffSet)
    return diffSets
