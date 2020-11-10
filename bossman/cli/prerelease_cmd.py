from os import getcwd
import git
import argparse
from bossman import Bossman
from bossman.repo import Revision
from bossman.abc import ResourceABC
from rich.console import Console

console = Console()

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("prerelease", help="prerelease applicable resources")
  parser.add_argument("--rev", required=False, default="HEAD", help="commit id or git ref to prerelease")
  parser.add_argument("glob", nargs="?", default="*", help="select resources by glob pattern")
  parser.set_defaults(func=exec)

def exec(bossman: Bossman, rev, glob, *args, **kwargs):
  resources = bossman.get_resources(glob=glob)
  revision = bossman.get_revision(rev, resources)
  bossman.prerelease(resources, revision)
