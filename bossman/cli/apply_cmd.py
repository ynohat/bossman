from os import getcwd
import git
import argparse

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("apply", help="apply local changes to remotes")
  parser.set_defaults(func=exec)

def exec(bossman, *args, **kwargs):
  resources = bossman.get_resources()
  for resource in resources:
    print("checking {resource}...".format(resource=resource))
    status = bossman.get_resource_status(resource)
    for changeset in reversed(status.missing_changesets):
      print("applying {changeset}".format(changeset=changeset))
      for change in changeset.resource_changes.values():
        print("{resource}: applying {change}".format(resource=resource, change=change))
        bossman.apply_change(changeset, change)
    else:
      print("nothing left to do for {resource}".format(resource=resource))
