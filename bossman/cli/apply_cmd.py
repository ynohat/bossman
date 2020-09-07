from os import getcwd
import git
import argparse
from rich.console import Console
from rich.panel import Panel

console = Console()

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("apply", help="apply local changes to remotes")
  parser.add_argument("--force", action="store_true", default=False, help="don't skip dirty resources")
  parser.add_argument("glob", nargs="?", default="*", help="select resources by glob pattern")
  parser.set_defaults(func=exec)

def exec(bossman, glob, force=False, **kwargs):
  resources = bossman.get_resources(glob=glob)
  for resource in resources:
    console.rule(str(resource))
    status = bossman.get_resource_status(resource)
    missing = list(status.missing_changesets)
    console.print(":notebook: {} changes pending".format(len(missing)), justify="center")
    if status.dirty:
      if not force:
        console.print(":stop_sign: [magenta]dirty, skipping[/magenta] :stop_sign:", justify="center")
        continue
      else:
        console.print(":exclamation_mark: [red]dirty, force applying[/red] :exclamation_mark:", justify="center")
    for (idx, changeset) in enumerate(missing):
      console.print(Panel(changeset, title="{}/{}".format(idx+1, len(missing))))
      for change in changeset.resource_changes.values():
        bossman.apply_change(changeset, change)
    else:
      console.print(":cookie: [green]all done[green] :cookie:", justify="center")
