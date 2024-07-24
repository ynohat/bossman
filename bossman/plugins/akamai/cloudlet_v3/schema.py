import jsonschema, jsonschema.validators, json
from importlib.resources import files

from bossman.plugins.akamai.cloudlet_v3.data import SharedPolicyAsCode

from .error import *

_PACKAGE = __name__.rsplit('.', 1)[0]

def get_schema(name):
  path = files(_PACKAGE).joinpath('schemas').joinpath(name)
  with open(path) as fd:
    return json.loads(fd.read())

def validate_policy_version(data: dict):
  try:
    schema = get_schema('update-policy-version.json')
    validator = jsonschema.validators.Draft4Validator(schema)
    for f in ['match_rule-AS-1.0.json', 'match_rule-ER-1.0.json', 'match_rule-FR-1.0.json', 'match-rules.json']:
      validator.resolver.store['file://' + f] = get_schema(f)
    validator.validate(data)
  except json.decoder.JSONDecodeError as err:
    raise PolicyVersionValidationError("bad rules.json", err.args)
  except jsonschema.ValidationError as err:
    raise PolicyVersionValidationError("invalid rules.json", {
      "message": err.message,
      "path": '/' + '/'.join(str(i) for i in err.absolute_path)
    })
