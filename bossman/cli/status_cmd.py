from os import getcwd
import git
import argparse
from rich import print
from rich.table import Table
from bossman import Bossman
from bossman.resources import ResourceStatus

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("status", help="show resource status")
  parser.add_argument("glob", nargs="?", default="*", help="select resources by glob pattern")
  parser.set_defaults(func=exec)

def exec(bossman: Bossman, glob, *args, **kwargs):
  resources = bossman.get_resources(glob=glob)
  if len(resources):
    table = Table()
    table.add_column("Resource")
    table.add_column("Revision")
    table.add_column("Pending")
    table.add_column("Clean")
    for resource in resources:
      status = bossman.get_resource_status(resource)
      table.add_row(
        resource,
        "".join(render_revision(resource, status)),
        "".join(render_pending(resource, status)),
        "".join(render_clean(resource, status))
      )
    print(table)
  else:
    print("No resources to show: check the glob pattern if provided, or the configuration.")

def render_revision(resource, status: ResourceStatus):
  if status.last_revision:
    yield r"\[{}] {}".format(status.last_revision.id, status.last_revision.short_message)
    if status.last_revision_details.details is not None:
      yield " ({})".format(status.last_revision_details.details)

def render_pending(resource, status: ResourceStatus):
  # if status.last_applied_revision:
  #   yield "[{}] {}".format(status.last_applied_revision.id, status.last_applied_revision.short_message)
  #   if status.last_applied_revision_details.details:
  #     yield "({})".format(status.last_applied_revision_details.details)
  # else:
  #   yield "(never applied)"
  missing_revisions = status.missing_revisions
  if len(missing_revisions) > 0:
    if len(missing_revisions) > 1:
      first, last = missing_revisions[0].id, missing_revisions[-1].id
      yield "[magenta]{n} revisions pending ({first}^..{last})[/magenta]".format(n=len(missing_revisions), first=first, last=last)
    else:
      yield "[magenta]{n} revision pending ({rev})[/magenta]".format(n=len(missing_revisions), rev=missing_revisions[0].id)
  else:
    yield "[green]up to date[/green] :heavy_check_mark:"

def render_clean(resource, status):
  if status.dirty:
    return ":stop_sign:"
  return ":thumbs_up:"
