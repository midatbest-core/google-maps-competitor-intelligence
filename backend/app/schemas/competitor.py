from pydantic import BaseModel, ConfigDict
from typing import Optional
from pydantic import Field, field_validator

class BusinessProfileBase(BaseModel):
    business_name: str = Field(min_length=1, max_length=300)
    google_maps_url: Optional[str] = None

    @field_validator("business_name")
    @classmethod
    def business_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Business name must not be blank")
        return value

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
