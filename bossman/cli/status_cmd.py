from os import getcwd
import git
import argparse
from rich import print
from rich.table import Table

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("status", help="show resource status")
  parser.add_argument("glob", nargs="?", default="*", help="select resources by glob pattern")
  parser.set_defaults(func=exec)

def exec(bossman, glob, *args, **kwargs):
  resources = bossman.get_resources(glob=glob)
  if len(resources):
    table = Table()
    table.add_column("Resource")
    table.add_column("Revision")
    table.add_column("Pending")
    table.add_column("Remote")
    for resource in resources:
      status = bossman.get_resource_status(resource)
      table.add_row(
        resource,
        render_revision(resource, status),
        render_pending(resource, status),
        render_remote(resource, status)
      )
    print(table)
  else:
    print("No resources to show... Check glob?")

def render_revision(resource, status):
  if status.remote_rev and status.remote_rev.local_rev:
    return "[green]{rev} -> v{remote_rev}[/green]".format(rev=status.remote_rev.local_rev, remote_rev=status.remote_rev.remote_rev)
  return "[magenta]{rev}[/magenta]".format(rev=status.local_rev)

def render_pending(resource, status):
  missing = status.missing_changesets
  if len(missing) > 0:
    if len(missing) > 1:
      first, last = status.remote_rev.local_rev, missing[-1]
      return "{n} ({first}...{last})".format(n=len(missing), first=first, last=last.rev)
    return "{n} ({rev})".format(n=len(missing), rev=missing[0].rev)
  return "[green]0[/green] :heavy_check_mark:"

def render_remote(resource, status):
  if status.dirty:
    return ":stop_sign: [red][b]dirty[/b][/red]"
  return ":thumbs_up:"