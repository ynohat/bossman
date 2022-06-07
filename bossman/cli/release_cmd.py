from functools import partial
from concurrent.futures import ThreadPoolExecutor
from os import getcwd
import argparse

from rich.padding import PaddingDimensions
from bossman import Bossman
from bossman.repo import Revision
from bossman.abc import ResourceABC
from rich.panel import Panel
from rich.console import Console, RenderGroup
from rich.progress import Progress, TextColumn, BarColumn
from rich.table import Table
from rich.columns import Columns
from rich.prompt import Prompt

console = Console()

def init(subparsers: argparse._SubParsersAction):
  prerelease_parser = subparsers.add_parser("prerelease", help="prerelease applicable resources")
  prerelease_parser.add_argument("-e", "--exact-match", action="store_true", default=False, help="match resource exactly")
  prerelease_parser.add_argument("--yes", action="store_true", default=False, help="don't prompt")
  prerelease_parser.add_argument("--rev", required=False, default="HEAD", help="commit id or git ref to prerelease")
  prerelease_parser.add_argument("glob", nargs="*", default="*", help="select resources by glob pattern")
  prerelease_parser.set_defaults(func=exec, action="prerelease")

  release_parser = subparsers.add_parser("release", help="release applicable resources")
  release_parser.add_argument("-e", "--exact-match", action="store_true", default=False, help="match resource exactly")
  release_parser.add_argument("--yes", action="store_true", default=False, help="don't prompt")
  release_parser.add_argument("--rev", required=False, default="HEAD", help="commit id or git ref to release")
  release_parser.add_argument("glob", nargs="*", default="*", help="select resources by glob pattern")
  release_parser.set_defaults(func=exec, action="release")

def exec(bossman: Bossman, yes, rev, glob, exact_match:bool, action, *args, **kwargs):
  resources = bossman.get_resources(*glob, rev=rev, exact_match=exact_match)
  revision = bossman.get_revision(rev, resources)
  deployed, undeployed = [], []
  # a (pre)release operation should only be possible on resources that have been deployed by
  # a previous apply operation.
  bossman.repo.fetch_notes('*')
  for resource in resources:
    deployed.append(resource) if bossman.is_applied(resource, revision) else undeployed.append(resource)

  console.print("Preparing to {}:".format(action))
  console.print(Panel(RenderGroup(
    revision,
    "\n",
    Columns(deployed, expand=True, equal=True))
  ))
  if len(undeployed):
    console.print("\nThe following resources were selected but {} was not applied to them:\n".format(revision.id))
    console.print(Columns(undeployed, expand=True, equal=True))


  if not yes and not console.is_terminal:
    console.print("Input or output is not a terminal. Consider using --yes to forgo validation.")
    return
  if (not yes):
    if Prompt.ask("\nShall we proceed?", choices=("yes", "no"), default="no") != "yes":
      console.print("OK!")
      return

  with Progress(
      "[progress.description]{task.description}",
      BarColumn(bar_width=20),
      TextColumn("[progress.description]{task.fields[activation_status]}"),
    ) as progress_ui:

    from collections import defaultdict
    last_status = defaultdict(lambda: None)

    def on_update(task_id, resource: ResourceABC, status: str, progress: float):
      if isinstance(progress, (float, int)):
        progress_ui.start_task(task_id)
        progress = progress * 100
      progress_ui.update(task_id, completed=progress, activation_status=status)
      progress_ui.refresh()
      if not console.is_terminal:
        res_last_status = last_status.get(resource.path)
        if res_last_status != status:
          console.print(resource, status)
        last_status[resource.path] = status

    futures = []
    with ThreadPoolExecutor(100, "prereleasse") as executor:
      for resource in deployed:
        description = str(resource)
        if hasattr(resource, "__rich__"):
          description = resource.__rich__()
        task_id = progress_ui.add_task(description, total=100, activation_status="-", start=False)
        _on_update = partial(on_update, task_id)
        futures.append(executor.submit(getattr(bossman, action), resource, revision, _on_update))
      for resource, future in zip(deployed, futures):
        try:
          future.result()
        except Exception as e:
          print(":exclamation_mark:", resource, e)
          console.print_exception()

