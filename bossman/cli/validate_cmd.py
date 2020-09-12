from os import getcwd
import git
import argparse
from rich import print
from rich.table import Table
from bossman import Bossman

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("validate", help="validates the working tree")
  parser.add_argument("glob", nargs="?", default="*", help="select resources by glob pattern")
  parser.set_defaults(func=exec)

def exec(bossman: Bossman, glob, *args, **kwargs):
  resources = bossman.get_resources(glob=glob)
  if len(resources):
    table = Table()
    table.add_column("Resource")
    table.add_column("Validation")
    for resource in resources:
      try:
        bossman.validate(resource)
        status = ":thumbs_up:"
      except:
        status = ":thumbs_down:"
      table.add_row(
        resource,
        status,
      )
    print(table)
  else:
    print("No resources to show: check the glob pattern if provided, or the configuration.")
