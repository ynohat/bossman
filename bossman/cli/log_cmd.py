from os import getcwd
import git
import argparse
from bossman import Bossman
from bossman.repo import Revision
from bossman.abc import ResourceABC
from rich.console import Console

console = Console()

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("log", help="show resource change history")
  parser.add_argument("glob", nargs="?", default="*", help="select resources by glob pattern")
  parser.set_defaults(func=exec)

def exec(bossman: Bossman, glob, *args, **kwargs):
  resources = bossman.get_resources(glob=glob)
  revisions = bossman.get_revisions(resources=resources)
  for revision in revisions:
    view = RevisionView(bossman, revision, resources)
    console.print(view, end="")
    console.print("\n")

class RevisionView:
  def __init__(self, bossman: Bossman, revision: Revision, resources: list):
    self.bossman = bossman
    self.revision = revision
    self.resources = resources

  def __rich_console__(self, console, options):
    yield "\[{}] [yellow]{}[/] | [grey62]{}[/]".format(self.revision.id, self.revision.short_message, self.revision.author_name)
    for resource in self.resources:
      if set(resource.paths).intersection(self.revision.affected_paths):
        changes = self.revision.get_changes(resource.paths)
        details = self.bossman.get_revision_details(resource, self.revision)
        if len(changes):
          change_type = lambda ct: "+" if ct == "A" else "-" if ct == "D" else "~"
          changes = ("[grey37]{}{}[/]".format(change_type(c.change_type), c.basename) for c in changes)
          details = " ({})".format(details.details) if details else ""
          yield "| [blue]{}[/] {} {}".format(resource, " ".join(list(changes)), details)
