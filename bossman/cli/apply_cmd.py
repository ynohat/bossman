from bossman.errors import BossmanError
from concurrent.futures import ThreadPoolExecutor, wait
from os import getcwd
import sys
import git
import argparse
from rich import get_console
from rich import print
from rich.padding import Padding
from rich.traceback import Traceback
from bossman import Bossman
from bossman.abc import ResourceABC

console = get_console()

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("apply", help="apply local changes to remotes")
  parser.add_argument("-e", "--exact-match", action="store_true", default=False, help="match resource exactly")
  parser.add_argument("--force", action="store_true", default=False, help="don't skip dirty resources")
  parser.add_argument("--dry-run", action="store_true", default=False, help="show what would be applied, but don't actually do anything")
  parser.add_argument("--since", default=None, help="apply only revisions since this commit ref (useful to skip early history)")
  parser.add_argument("glob", nargs="*", default="*", help="select resources by glob pattern")
  parser.set_defaults(func=exec)

def exec(bossman: Bossman, glob, exact_match:bool, force:bool, dry_run:bool, since, **kwargs):
  resources = bossman.get_resources(*glob, exact_match=exact_match)
  futures = []
  had_errors = False
  with ThreadPoolExecutor(10, "apply") as executor:
    for resource in resources:
      futures.append(executor.submit(apply_changes, bossman, resource, force, dry_run, since))
  for resource, future in zip(resources, futures):
    try:
      had_errors = future.result() or had_errors
    except Exception as e:
      had_errors = True
      print(":exclamation_mark:", resource)
      console.print_exception()
  print(":cookie: [green]all resources up to date[green]")
  if had_errors:
    print("[red]apply completed, but some errors occurred[/red]")
    sys.exit(3)

def apply_changes(bossman: Bossman, resource: ResourceABC, force: bool, dry_run: bool, since: str):
  try:
    status = bossman.get_resource_status(resource)
    revisions = bossman.get_missing_revisions(resource, since_rev=since)
    todo = len(revisions)
    had_errors = False
    if todo > 0:
      if status.dirty and not force:
        print(":stop_sign:", resource, "[magenta]dirty, skipping[/magenta]")
        return
      results = []
      for revision in revisions:
        try:
          results.append(bossman.apply_change(resource, revision, dry_run))
        except Exception as e:
          if not force:
            raise e
          results.append(":exclamation_mark: {} an error occurred while applying {}\n{}".format(resource, revision, e))
          console.print_exception()
      for result in results:
        had_errors = had_errors or result.had_errors
        print(result)
    else:
      print(":white_check_mark:", resource, "is up to date")
  except RuntimeError as e:
    had_errors = True
    print(":exclamation_mark:", resource, e)
  return had_errors
