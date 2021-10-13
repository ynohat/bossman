from bossman.errors import BossmanError

class CloudletAPIV3Error(BossmanError):
  pass

class PolicyNameNotFound(CloudletAPIV3Error):
  pass

class PolicyVersionValidationError(CloudletAPIV3Error):
  pass
