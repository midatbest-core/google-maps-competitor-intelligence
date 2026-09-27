from pydantic import BaseModel, ConfigDict
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
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str
    competitors_attempted: int
    competitors_succeeded: int
    competitors_failed: int
    competitor_runs: Optional[List[ScrapeRunCompetitorResponse]] = None

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
