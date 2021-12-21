import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional



class Network(Enum):
  PRODUCTION = 'PRODUCTION'
  STAGING = 'STAGING'
  
  @property
  def alias(self) -> str:
    return re.sub("[aeiou]", "", self.value, flags=re.IGNORECASE)[:3].upper()
  
  @property
  def color(self) -> str:
    return "green" if self == Network.PRODUCTION else "magenta"

class SharedPolicyActivationOperation(Enum):
  ACTIVATION = 'ACTIVATION'
  DEACTIVATION = 'DEACTIVATION'

class SharedPolicyActivationStatus(Enum):
  IN_PROGRESS = 'IN_PROGRESS'
  SUCCESS = 'SUCCESS'
  FAILED = 'FAILED'

class SharedPolicyPolicyType(Enum):
  SHARED = 'SHARED'

class SharedPolicyCloudletType(Enum):
  ER = 'ER'
  FR = 'FR'
  AS = 'AS'

@dataclass
class SharedPolicyActivation:
  id: int
  createdBy: str
  createdDate: datetime
  finishDate: Optional[datetime]
  network: Network
  operation: SharedPolicyActivationOperation
  status: SharedPolicyActivationStatus
  policyId: int
  policyVersion: int
  policyVersionDeleted: bool

@dataclass
class SharedPolicyCurrentActivationsNetwork:
  effective: Optional[SharedPolicyActivation] = None
  latest: Optional[SharedPolicyActivation] = None

@dataclass
class SharedPolicyCurrentActivations:
  production: SharedPolicyCurrentActivationsNetwork = None
  staging: SharedPolicyCurrentActivationsNetwork = None

@dataclass
class SharedPolicy:
  id: int
  name: str
  description: str
  policyType: SharedPolicyPolicyType
  cloudletType: SharedPolicyCloudletType
  createdBy: str
  createdDate: datetime
  currentActivations: SharedPolicyCurrentActivations
  groupId: int
  modifiedBy: str
  modifiedDate: datetime

@dataclass
class GetPoliciesResponse:
  content: List[SharedPolicy]

@dataclass
class SharedPolicyVersion:
  policyId: int
  version: int
  createdBy: str
  createdDate: datetime
  modifiedBy: str
  modifiedDate: datetime
  description: str
  matchRules: Optional[List[Dict]] = None

@dataclass
class GetPolicyVersionsResponse:
  content: List[SharedPolicyVersion]

@dataclass
class SharedPolicyAsCode:
  """
  Subset of SharedPolicy that must be versioned in order to support CRUD.
  """
  description: str
  groupId: int
  cloudletType: SharedPolicyCloudletType
  matchRules: Optional[List[Dict]] = None
