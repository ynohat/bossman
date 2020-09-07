from os import getcwd
import git
import argparse

def init(subparsers: argparse._SubParsersAction):
  parser = subparsers.add_parser("status", help="show resource status")
  parser.set_defaults(func=exec)

def exec(bossman, *args, **kwargs):
  resources = bossman.get_resources()
  #print("\n".join(resource.path for resource in resources))
  for resource in list(resources):
    resource_status = bossman.get_resource_status(resource)
    print(resource, resource_status)
