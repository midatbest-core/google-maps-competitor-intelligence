from pydantic import BaseModel, ConfigDict
from typing import Optional

class BusinessProfileBase(BaseModel):
    business_name: str
    google_maps_url: Optional[str] = None

class CompetitorCreate(BusinessProfileBase):
    pass

class CompetitorResponse(BaseModel):
    id: str
    project_id: str
    business_id: str
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)
