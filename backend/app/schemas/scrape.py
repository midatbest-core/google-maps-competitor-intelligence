from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class ScrapeRunResponse(BaseModel):
    id: str
    project_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str
    competitors_attempted: int
    competitors_succeeded: int
    competitors_failed: int
    
    model_config = ConfigDict(from_attributes=True)
