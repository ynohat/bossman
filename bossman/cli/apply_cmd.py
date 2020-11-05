from os import getcwd
import git
import argparse
from rich.console import Console
from rich.panel import Panel
from bossman import Bossman

console = Console()

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("apply", help="apply local changes to remotes")
  parser.add_argument("--force", action="store_true", default=False, help="don't skip dirty resources")
  parser.add_argument("glob", nargs="?", default="*", help="select resources by glob pattern")
  parser.set_defaults(func=exec)

def exec(bossman: Bossman, glob, force=False, **kwargs):
  resources = bossman.get_resources(glob=glob)
  for resource in resources:
    console.rule(str(resource))
    status = bossman.get_resource_status(resource)
    missing_revisions = bossman.get_missing_revisions(resource)
    console.print(":notebook: {} changes pending".format(len(missing_revisions)), justify="center")
    if status.dirty:
      if not force:
        console.print(":stop_sign: [magenta]dirty, skipping[/magenta] :stop_sign:", justify="center")
        continue
      else:
        console.print(":exclamation_mark: [red]dirty, force applying[/red] :exclamation_mark:", justify="center")
    for (idx, revision) in enumerate(missing_revisions):
      console.print(Panel(revision, title="{}/{}".format(idx+1, len(missing_revisions))))
      bossman.apply_change(resource, revision)
  else:
    console.print(":cookie: [green]all done[green] :cookie:", justify="center")
