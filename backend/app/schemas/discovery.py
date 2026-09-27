from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class DiscoveryCandidateSchema(BaseModel):
    source_identifier: Optional[str] = None
    source_url: Optional[str] = None
    business_name: str
    category: Optional[str] = None
    address: Optional[str] = None
    locality: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    phone: Optional[str] = None
    website: Optional[str] = None

class DiscoveryRunCreate(BaseModel):
    query: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius: Optional[int] = None
    category: Optional[str] = None

class DiscoveryRunResponse(BaseModel):
    id: str
    project_id: str
    query: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius: Optional[int] = None
    category: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_candidates: int
    duplicates_skipped: int
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

class DiscoveryCandidateResponse(BaseModel):
    id: str
    discovery_run_id: str
    source_identifier: Optional[str] = None
    source_url: Optional[str] = None
    business_name: str
    category: Optional[str] = None
    address: Optional[str] = None
    locality: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    status: str
    relevance_score: Optional[float] = None

    class Config:
        from_attributes = True

class DirectCompetitorCreate(BaseModel):
    source_identifier: Optional[str] = None
    source_url: Optional[str] = None
    business_name: str
    category: Optional[str] = None
    address: Optional[str] = None
    locality: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    phone: Optional[str] = None
    website: Optional[str] = None
