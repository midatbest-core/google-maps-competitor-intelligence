from pydantic import BaseModel, ConfigDict
from typing import Optional

class BusinessProfileBase(BaseModel):
    business_name: str
    google_maps_url: Optional[str] = None

class CompetitorCreate(BusinessProfileBase):
    pass

class BusinessProfileResponse(BaseModel):
    id: str
    business_name: str
    google_maps_url: Optional[str] = None
    canonical_source_id: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class CompetitorResponse(BaseModel):
    id: str
    project_id: str
    business_id: str
    is_active: bool
    business: Optional[BusinessProfileResponse] = None

    model_config = ConfigDict(from_attributes=True)
