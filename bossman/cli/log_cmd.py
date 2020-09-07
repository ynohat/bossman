from os import getcwd
import git
import argparse
from bossman import Bossman
from bossman.resources import ResourceABC

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("log", help="show resource change history")
  parser.set_defaults(func=exec)

def exec(bossman, *args, **kwargs):
  changesets = bossman.get_changesets()
  for changeset in changesets:
    print(changeset)
