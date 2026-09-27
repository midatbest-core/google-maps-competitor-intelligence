from pydantic import BaseModel, ConfigDict
from typing import Optional

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    own_business_id: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    own_business_id: Optional[str] = None

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
