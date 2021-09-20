import sys
from bossman.errors import BossmanValidationError
from os import getcwd
import git
import argparse
from rich import print
from rich.table import Table
from bossman import Bossman

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("validate", help="validates the working tree")
  parser.add_argument("glob", nargs="*", default="*", help="select resources by glob pattern")
  parser.set_defaults(func=exec)

def exec(bossman: Bossman, glob, *args, **kwargs):
  resources = bossman.get_resources_from_working_copy(*glob)
  if len(resources):
    table = Table()
    table.add_column("Resource")
    table.add_column("Validation")
    table.add_column("Error")
    error_recorded = 0
    for resource in resources:
      error = ""
      try:
        bossman.validate(resource)
        status = ":thumbs_up:"
      except BossmanValidationError as e:
        status = ":thumbs_down:"
        error = e
        error_recorded = 1
      table.add_row(
        resource,
        status,
        error
      )
    print(table)
    if error_recorded == 1:
      sys.exit(1)
  else:
    print("No resources to show: check the glob pattern if provided, or the configuration.")
