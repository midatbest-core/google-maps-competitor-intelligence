from pydantic import BaseModel, ConfigDict
from typing import Optional

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    own_business_id: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: str

    model_config = ConfigDict(from_attributes=True)
