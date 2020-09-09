from os import getcwd
import git
import argparse
from bossman import Bossman
from bossman.resources import ResourceABC
from rich.console import Console

console = Console()

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("log", help="show resource change history")
  parser.set_defaults(func=exec)

def exec(bossman: Bossman, *args, **kwargs):
  resources = bossman.get_resources()
  revisions = bossman.get_revisions(resources=resources)
  for revision in revisions:
    console.print(revision)
    for resource in resources:
      changes = revision.get_changes(resource.paths)
      if len(changes):
        console.print(resource)
        console.print(*changes)       
