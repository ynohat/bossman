from os import getcwd
import git
import argparse
from rich import print, box
from rich.table import Table
from bossman import Bossman
from bossman.abc import ResourceStatusABC

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("status", help="show resource status")
  parser.add_argument("glob", nargs="*", default="*", help="select resources by glob pattern")
  parser.set_defaults(func=exec)

def exec(bossman: Bossman, glob, *args, **kwargs):
  resources = bossman.get_resources(*glob)
  if len(resources):
    print("On branch", bossman.get_current_branch())

    statuses = bossman.get_resource_statuses(resources)

    col_width = min(max(len(resource.path) for resource in resources) + 2, 60)
    table = Table(expand=False, box=box.HORIZONTALS, show_lines=True)
    table.add_column("Resource", width=col_width)
    table.add_column("Status")
    for resource, status in zip(resources, statuses):
      table.add_row(resource, status)
    print(table)
  else:
    print("No resources to show: check the glob pattern if provided, or the configuration.")
