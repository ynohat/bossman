import sys
from os import path, getcwd
import yaml
import argparse
from bossman.cli import status_cmd, log_cmd, apply_cmd
from bossman.config import Config
from bossman.logging import logger
from bossman import Bossman
from bossman.config import Config

logger = logger.getChild(globals().get("__name__"))

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--verbosity", action=SetVerbosity, default="ERROR", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR"])
  parser.add_argument("--repo", help="path to the repository", default=getcwd())

  subparsers = parser.add_subparsers(title="Subcommands")
  status_cmd.init(subparsers)
  log_cmd.init(subparsers)
  apply_cmd.init(subparsers)

  args = parser.parse_args()
  bossman = create_bossman(args)

  if "func" in args:
    args.func(bossman, **vars(args))
  else:
    parser.print_usage()

def create_bossman(args):
  conf_path = path.join(args.repo, ".bossman")
  conf_data = {}
  if path.exists(conf_path):
    fd = open(conf_path, "r")
    conf_data = yaml.safe_load(fd)

  config = Config(conf_data)

  bossman = Bossman(args.repo, config)
  return bossman

class SetVerbosity(argparse.Action):
  """
  Set logger verbosity when --verbosity argument is provided.
  """
  def __init__(self, *args, **kwargs):
    super(SetVerbosity, self).__init__(*args, **kwargs)

  def __call__(self, parser, namespace, values, option_string=None):
    import logging
    logging.basicConfig(level=values)
    logger.info("SetVerbosity verbosity={verbosity}".format(verbosity=values))
