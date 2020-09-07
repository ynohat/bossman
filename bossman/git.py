from git import Repo, NULL_TREE
from os import getcwd
from types import SimpleNamespace

def get_repo(workingDir=getcwd()):
  return Repo(workingDir)

def get_head_info():
  repo = get_repo()
  return SimpleNamespace(
    branch=repo.head.reference.name,
    commit=repo.head.commit.hexsha,
    message=repo.head.commit.message,
  )

def print_commit_tree(commit="HEAD"):
  repo = get_repo()
  commit = repo.rev_parse(commit)
  def visit(blob, depth=0):
    if type(blob) == Tree:
      print("  " * depth + blob.name)
      for child in blob:
        visit(child, depth+1)
    elif type(blob) == Blob:
      print("  " * depth + blob.name)
  visit(commit.tree)

# >>> repo.is_ancestor("88bfd2eb3c939bcf5409b003026c22a4fe9c8fa2", "9a7df4dc079ac844f96b2f74a501ab3b84ddcad1")
# True

# >>> repo.rev_parse("1f8bbdec8e0d42262d273cd9bbaa217a85573db6")
# <git.Commit "1f8bbdec8e0d42262d273cd9bbaa217a85573db6">

# >>> repo.head.commit.diff("1f8bbdec8e0d42262d273cd9bbaa217a85573db6", "build/property")
# []
