from os import getcwd
import git
import argparse
from bossman import Bossman
from rich.console import Console

console = Console()

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("init", help="initialize bossman")
  parser.set_defaults(func=exec)

def exec(bossman: Bossman, *args, **kwargs):
  console.print("Initializing...")
  bossman.init(console)
