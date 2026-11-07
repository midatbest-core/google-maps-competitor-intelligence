from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class ReviewResponse(BaseModel):
    id: str
    business_id: str
    business_name: Optional[str] = None
    source: str
    source_id: Optional[str] = None
    author_name: Optional[str] = None
    author_photo_url: Optional[str] = None
    rating: Optional[float] = None
    text: Optional[str] = None
    language: Optional[str] = None
    published_at: Optional[datetime] = None
    relative_time_description: Optional[str] = None
    response_text: Optional[str] = None
    sentiment: Optional[str] = None
    aspects: Optional[List[str]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ReviewListResponse(BaseModel):
    items: List[ReviewResponse]
    total: int
    page: int
    page_size: int
    pages: int

class ReviewIntelligenceResponse(BaseModel):
    id: str
    project_id: str
    business_id: str
    reviews_analyzed_count: int
    overall_sentiment: Optional[str] = None
    positive_percentage: Optional[float] = None
    neutral_percentage: Optional[float] = None
    negative_percentage: Optional[float] = None
    average_rating: Optional[float] = None
    praise_themes: Optional[List[str]] = None
    complaint_themes: Optional[List[str]] = None
    pain_points: Optional[List[str]] = None
    customer_needs: Optional[List[str]] = None
    frequently_mentioned_services: Optional[List[str]] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    business_opportunities: Optional[List[str]] = None
    recommended_actions: Optional[List[str]] = None
    analysis_provider: Optional[str] = None
    model_version: Optional[str] = None
    analyzed_at: datetime

    model_config = ConfigDict(from_attributes=True)
