from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime

class BusinessProfileMinimalResponse(BaseModel):
    id: str
    business_name: str
    model_config = ConfigDict(from_attributes=True)

class ScrapeRunCompetitorResponse(BaseModel):
    id: str
    business_id: str
    business: Optional[BusinessProfileMinimalResponse] = None
    status: str
    posts_discovered: int
    new_posts: int
    duplicates_skipped: int
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ScrapeRunResponse(BaseModel):
    id: str
    project_id: str
    run_number: Optional[int] = None
    display_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str
    competitors_attempted: int
    competitors_succeeded: int
    competitors_failed: int
    competitor_runs: Optional[List[ScrapeRunCompetitorResponse]] = None
    total_competitors: Optional[int] = None
    competitors_completed: Optional[int] = None
    competitors_remaining: Optional[int] = None
    currently_processing_index: Optional[int] = None
    currently_processing_name: Optional[str] = None
    estimated_remaining_seconds: Optional[int] = None
    estimated_remaining_formatted: Optional[str] = None

    @field_validator("currently_processing_name", "estimated_remaining_formatted", mode="before")
    @classmethod
    def validate_optional_str(cls, v):
        if not isinstance(v, str):
            return None
        return v

    @field_validator(
        "total_competitors",
        "competitors_completed",
        "competitors_remaining",
        "currently_processing_index",
        "estimated_remaining_seconds",
        mode="before"
    )
    @classmethod
    def validate_optional_int(cls, v):
        if not isinstance(v, int):
            return None
        return v

    model_config = ConfigDict(from_attributes=True)

class ScrapeScheduleBase(BaseModel):
    enabled: bool
    frequency: str = "DAILY"
    time_of_day: str
    timezone: str

class ScrapeScheduleUpdate(ScrapeScheduleBase):
    pass

class ScrapeScheduleResponse(ScrapeScheduleBase):
    id: str
    project_id: str
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
