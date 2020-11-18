from functools import partial
from concurrent.futures import ThreadPoolExecutor
from os import getcwd
import git
import argparse
from bossman import Bossman
from bossman.repo import Revision
from bossman.abc import ResourceABC
from rich.panel import Panel
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn
from rich.table import Table
from rich.columns import Columns
from rich.prompt import Prompt

console = Console()

def init(subparsers: argparse._SubParsersAction):
  prerelease_parser = subparsers.add_parser("prerelease", help="prerelease applicable resources")
  prerelease_parser.add_argument("--rev", required=False, default="HEAD", help="commit id or git ref to prerelease")
  prerelease_parser.add_argument("glob", nargs="?", default="*", help="select resources by glob pattern")
  prerelease_parser.set_defaults(func=exec, action="prerelease")

  release_parser = subparsers.add_parser("release", help="release applicable resources")
  release_parser.add_argument("--rev", required=False, default="HEAD", help="commit id or git ref to release")
  release_parser.add_argument("glob", nargs="?", default="*", help="select resources by glob pattern")
  release_parser.set_defaults(func=exec, action="release")

def exec(bossman: Bossman, rev, glob, action, *args, **kwargs):
  resources = bossman.get_resources(glob=glob)
  revision = bossman.get_revision(rev, resources)

  console.print("Preparing to {}:".format(action))
  console.print(Panel(revision))
  console.print(Columns(resources, expand=False, equal=True))
  if Prompt.ask("Shall we proceed?", choices=("yes", "no"), default="no") != "yes":
    console.print("OK!")
    return

  with Progress(
      "[progress.description]{task.description}",
      BarColumn(bar_width=20),
      TextColumn("[progress.description]{task.fields[activation_status]}"),
    ) as progress_ui:

    def on_update(task_id, resource: ResourceABC, status: str, progress: float):
      if isinstance(progress, (float, int)):
        progress_ui.start_task(task_id)
        progress = progress * 100
      progress_ui.update(task_id, completed=progress, activation_status=status)
      progress_ui.refresh()

    futures = []
    with ThreadPoolExecutor(100, "prereleasse") as executor:
      for resource in resources:
        description = str(resource)
        if hasattr(resource, "__rich__"):
          description = resource.__rich__()
        task_id = progress_ui.add_task(description, total=100, activation_status="-", start=False)
        _on_update = partial(on_update, task_id)
        futures.append(executor.submit(getattr(bossman, action), resource, revision, _on_update))
      for resource, future in zip(resources, futures):
        try:
          future.result()
        except Exception as e:
          print(":exclamation_mark:", resource, e)
          console.print_exception()

