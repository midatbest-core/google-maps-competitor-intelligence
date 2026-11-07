from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class NormalizedPost(BaseModel):
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    text_content: Optional[str] = None
    published_date: Optional[datetime] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    media_urls: List[str] = []
    
    # Generated fingerprint after normalization
    fingerprint: Optional[str] = None

class ExtractionFailure(BaseModel):
    reason: str
    raw_content_preview: Optional[str] = None

class ScrapeResult(BaseModel):
    posts: List[NormalizedPost] = []
    failures: List[ExtractionFailure] = []
    status: str = "SUCCESS" # SUCCESS, VERIFICATION_REQUIRED, NO_DATA, ERROR
    error_message: Optional[str] = None

class ExtractedReview(BaseModel):
    source_id: Optional[str] = None
    author_name: Optional[str] = None
    author_photo_url: Optional[str] = None
    rating: Optional[float] = None
    text: Optional[str] = None
    language: Optional[str] = None
    published_at: Optional[datetime] = None
    relative_time_description: Optional[str] = None
    response_text: Optional[str] = None
    response_date: Optional[datetime] = None
    sentiment: Optional[str] = None
    aspects: List[str] = []
    source: str = "browser_scraper"
    fingerprint: Optional[str] = None

class ReviewScrapeResult(BaseModel):
    reviews: List[ExtractedReview] = []
    failures: List[ExtractionFailure] = []
    status: str = "SUCCESS" # SUCCESS, VERIFICATION_REQUIRED, NO_DATA, ERROR
    error_message: Optional[str] = None
