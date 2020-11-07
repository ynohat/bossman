import importlib
from types import SimpleNamespace
from bossman.repo import Repo
from bossman.repo import Repo
from bossman.abc import ResourceTypeABC
from bossman.abc import ResourceABC

class ResourceManager:
  def __init__(self, resource_type_configs, repo: Repo):
    self.resource_types = list()
    for config in resource_type_configs:
      plugin = importlib.import_module(config.module)
      self.resource_types.append(plugin.ResourceType(repo, config))
    self.repo = repo

  def get_resource_type(self, path: str) -> ResourceTypeABC:
    for resource_type in self.resource_types:
      if resource_type.match(path):
        return resource_type
    return None

  def get_resource(self, path: str) -> ResourceABC:
    resource_type = self.get_resource_type(path)
    if resource_type:
      return resource_type.get_resource(path)
    return None

  def get_resources(self, repo: Repo, rev: str = "HEAD") -> list:
    paths = repo.get_paths(rev)
    resources = []
    for resource_type in self.resource_types:
      resources.extend(resource_type.get_resources(paths))
    return resources
