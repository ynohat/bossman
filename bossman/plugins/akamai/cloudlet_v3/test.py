
from os import getenv
from posixpath import expanduser
import git
import json
from bossman.config import ResourceTypeConfig
from bossman.errors import BossmanError
from rich import print

config = ResourceTypeConfig({
  "module": "bossman.plugins.akamai.cloudlet_v3",
  "pattern": "akamai/cloudlet/{name}",
  "options": {
    "edgerc": getenv("AKAMAI_EDGERC", expanduser("~/.edgerc")),
    "section": getenv("AKAMAI_EDGERC_SECTION", "default"),
    "switch_key": getenv("AKAMAI_EDGERC_SWITCHKEY", None),
  }
})

POLICY_NAME = 'ER_ak_hogg_fr_shared_policy'

##############################################################################

import git
from bossman.plugins.akamai.cloudlet_v3.client import CloudletAPIV3Client

client = CloudletAPIV3Client(config.options['edgerc'], config.options['section'], config.options.get('switch_key', None))
policy = client.get_policy_by_name(POLICY_NAME)
print(policy)

##############################################################################

policy_version = client.get_policy_version(policy.id, 1)
print(policy_version)

##############################################################################

from bossman.plugins.akamai.cloudlet_v3.resourcetype import ResourceType

rt = ResourceType(git.Repo(), config)

res = rt.create_resource('akamai/cloudlet/' + POLICY_NAME, name=POLICY_NAME)
print(res.name)
print(rt.get_resource_status(res))


##############################################################################

from bossman.plugins.akamai.cloudlet_v3.schema import validate_policy_version

data = json.loads(
  """
  {
      "descrip22tion": "Initial version",
      "matchRules": [
          {
              "end": 0,
              "name": "Redirect images",
              "matchURL": "/images/*",
              "redirectURL": "/static/images/*",
              "start": 0,
              "statusCode": 302,
              "type": "erMatchRule",
              "useIncomingQueryString": true,
              "useRelativeUrl": "relative_url"
          }
      ]
  }
  """
)

try:
  validate_policy_version(data)
except BossmanError as e:
  print(e)