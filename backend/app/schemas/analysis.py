from pydantic import BaseModel, Field
from typing import List, Optional

class AIAnalysisResult(BaseModel):
    topic: Optional[str] = Field(default=None, description="Primary topic of the post")
    subtopic: Optional[str] = Field(default=None, description="Secondary topic or sub-theme")
    keywords: List[str] = Field(default_factory=list, description="List of relevant keywords extracted from the post")
    content_type: Optional[str] = Field(
        default=None, 
        description="Type of content, e.g., promotion, product/service, announcement, event, educational, testimonial/review, seasonal, informational, community, other"
    )
    cta_type: Optional[str] = Field(
        default=None, 
        description="Type of Call To Action, e.g., Call, Visit website, Book now, Learn more, Contact us, Get directions, None"
    )
    offer_or_promotion: Optional[str] = Field(
        default=None, 
        description="Details of any offer or promotion, e.g., discount, limited time, seasonal offer, bundle, event, no offer, other"
    )
    sentiment: Optional[str] = Field(default=None, description="Overall sentiment of the post, e.g., positive, neutral, negative")
    summary: Optional[str] = Field(default=None, description="A short summary of the post content")
    confidence: Optional[float] = Field(default=None, description="Confidence score of the analysis between 0.0 and 1.0")

from pydantic import BaseModel, Field
from typing import List, Optional

class SentimentBreakdown(BaseModel):
    positive: float
    neutral: float
    negative: float

class AIReviewAnalysisResult(BaseModel):
    overall_sentiment: str = Field(description="Overall sentiment of the reviews")
    sentiment_breakdown: SentimentBreakdown
    praise_themes: List[str] = Field(description="Common themes of praise")
    complaint_themes: List[str] = Field(description="Common themes of complaints")
    pain_points: List[str] = Field(description="Specific customer pain points")
    customer_needs: List[str] = Field(description="Customer needs mentioned in reviews")
    frequently_mentioned_services: List[str] = Field(description="Services or products frequently mentioned")
    strengths: List[str] = Field(description="Strengths of the business")
    weaknesses: List[str] = Field(description="Weaknesses of the business")
    business_opportunities: List[str] = Field(description="Business opportunities")
    recommended_actions: List[str] = Field(description="Recommended actions based on reviews")
