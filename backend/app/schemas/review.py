from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

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
