from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional

class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    own_business_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name must not be blank")
        return value

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    own_business_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Project name must not be blank")
        return value

class ProjectResponse(ProjectBase):
    id: str

    model_config = ConfigDict(from_attributes=True)

class ProjectSummaryResponse(BaseModel):
    project: ProjectResponse
    competitor_count: int
    post_count: int
    generated_content_count: int
    latest_scrape: Optional[str] = None
    latest_scrape_status: Optional[str] = None
    discovery_count: int
