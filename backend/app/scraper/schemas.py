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
