from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

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


# --- COMBINED INTELLIGENCE SCHEMAS ---

class SupportingEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(description="'post' or 'review'")
    business_name: Optional[str] = Field(default=None, description="Competitor or business name")
    quote_or_summary: str = Field(description="Specific observation or excerpt supporting the insight")

class ActionableRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Concise recommendation title")
    description: str = Field(description="Detailed actionable recommendation")
    category: str = Field(description="Category: 'marketing', 'service', 'positioning', 'operations'")
    rationale: str = Field(description="Why this recommendation was generated")
    priority: str = Field(description="'HIGH', 'MEDIUM', or 'LOW'")
    supporting_evidence: List[SupportingEvidence] = Field(description="Citations and evidence from observed posts and reviews")

class StrategicDisconnect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    competitor_name: str = Field(description="Competitor exhibiting the disconnect")
    advertised_promise: str = Field(description="What the competitor promotes in their Google Maps posts")
    customer_reality: str = Field(description="What customers actually report in customer reviews")
    opportunity: str = Field(description="Strategic opportunity for our business to stand out")
    recommended_action: str = Field(description="Specific marketing or operational response")

class CompetitorInsightItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    competitor_name: str
    strengths: List[str]
    weaknesses: List[str]
    customer_sentiment: str
    recurring_complaints: List[str]
    marketing_patterns: List[str]
    positioning: str

class MarketingIntelligenceSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frequently_promoted_topics: List[str]
    common_offers: List[str]
    posting_frequency: str
    content_formats: List[str]
    effective_ctas: List[str]

class ContentIdeaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Content concept title")
    hook: str = Field(description="Compelling hook for Google Maps update or social post")
    angle: str = Field(description="Why this angle resonates based on competitor weaknesses")
    suggested_format: str = Field(description="'Image with caption', 'Offer badge', 'Short announcement'")
    target_audience: str = Field(description="Target segment or need addressed")
    evidence_backed_reason: str = Field(description="Direct reference to competitor post or review finding")

class CombinedIntelligenceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    competitor_insights: List[CompetitorInsightItem]
    marketing_intelligence: MarketingIntelligenceSection
    strategic_disconnects: List[StrategicDisconnect]
    business_opportunities: List[str]
    actionable_recommendations: List[ActionableRecommendation]
    content_ideas: List[ContentIdeaItem]

class IntelligenceReportResponse(BaseModel):
    id: str
    project_id: str
    posts_analyzed: int
    reviews_analyzed: int
    competitors_analyzed: int
    competitor_insights: Optional[List[Dict[str, Any]]] = None
    marketing_intelligence: Optional[Dict[str, Any]] = None
    strategic_disconnects: Optional[List[Dict[str, Any]]] = None
    business_opportunities: Optional[List[Any]] = None
    actionable_recommendations: Optional[List[Dict[str, Any]]] = None
    content_ideas: Optional[List[Dict[str, Any]]] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
