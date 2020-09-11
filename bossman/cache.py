import dbm
import json
import os
from bossman.logging import logger

logger = logger.getChild(__name__)

_not_found = object()

class _cache:
  def __init__(self, ns, dbm):
    self.__ns = ns
    self.__dbm = dbm
    self.__logger = logger.getChild(ns)

  def key(self, *ns):
    return _cache(".".join([self.__ns, *ns]), self.__dbm)

  def update(self, value):
    self.__logger.debug("update {}".format(value))
    self.__dbm[self.__ns] = value
    return self

  def update_json(self, value):
    return self.update(json.dumps(value))

  def get(self, default=None) -> bytes:
    if self.__dbm.get(self.__ns, _not_found) != _not_found:
      self.__logger.debug("hit")
      return self.__dbm.get(self.__ns, default)
    else:
      self.__logger.debug("miss")
      return default

  def get_str(self, default=None) -> str:
    val = self.get()
    return val.decode() if val is not None else default

  def get_json(self, default=None) -> str:
    val = self.get()
    return json.loads(val) if val is not None else default

  def delete(self):
    try:
      del self.__dbm[self.__ns]
      return True
    except:
      return False

cache = _cache("", dbm.open(os.getenv("BOSSMAN_CACHE") or ".bossmancache", "c", 0o600))

