from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List, Optional

class AIAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Confidence score of the analysis between 0.0 and 1.0",
    )

class SentimentBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positive: float = Field(ge=0, le=100)
    neutral: float = Field(ge=0, le=100)
    negative: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def percentages_total_one_hundred(self):
        total = self.positive + self.neutral + self.negative
        if abs(total - 100.0) > 0.5:
            raise ValueError("sentiment percentages must total 100")
        return self

class AIReviewAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_sentiment: str = Field(
        min_length=1,
        description="Overall sentiment of the reviews",
    )
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
