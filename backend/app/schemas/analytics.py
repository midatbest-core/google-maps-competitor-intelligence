from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class TopicFrequency(BaseModel):
    topic: str
    count: int
    percentage: Optional[float] = None

class CompetitorTopicCoverage(BaseModel):
    topic: str
    competitor_count: int

class KeywordFrequency(BaseModel):
    keyword: str
    count: int

class PublishingPatterns(BaseModel):
    posts_per_competitor: List[Dict[str, Any]]

class ContentGaps(BaseModel):
    topic_gaps: List[str]
    keyword_gaps: List[str]

class DetailedTopicGap(BaseModel):
    topic: str
    competitor_frequency: int
    project_frequency: int
    gap_score: float

class DetailedKeywordGap(BaseModel):
    keyword: str
    competitor_frequency: int
    project_frequency: int
    gap_score: float

class DetailedContentTypeGap(BaseModel):
    content_type: str
    competitor_frequency: int
    project_frequency: int
    gap_score: float

class AnalyticsSummaryResponse(BaseModel):
    topics: List[TopicFrequency]
    competitor_coverage: List[CompetitorTopicCoverage]
    keywords: List[KeywordFrequency]
    publishing_patterns: PublishingPatterns
    content_gaps: ContentGaps
    detailed_topic_gaps: List[DetailedTopicGap]
    detailed_keyword_gaps: List[DetailedKeywordGap]
    detailed_content_type_gaps: List[DetailedContentTypeGap]
