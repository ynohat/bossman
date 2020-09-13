from os import getcwd
import git
import argparse
from bossman import Bossman
from bossman.resources import ResourceABC
from rich.console import Console

console = Console()

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("log", help="show resource change history")
  parser.add_argument("glob", nargs="?", default="*", help="select resources by glob pattern")
  parser.set_defaults(func=exec)

def exec(bossman: Bossman, glob, *args, **kwargs):
  resources = bossman.get_resources(glob=glob)
  revisions = bossman.get_revisions(resources=resources)
  for revision in revisions:
    console.print(revision)
    for resource in resources:
      changes = revision.get_changes(resource.paths)
      if len(changes):
        console.print(resource)
        console.print(*changes)       
