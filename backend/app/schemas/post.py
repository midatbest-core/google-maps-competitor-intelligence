from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.schemas.analysis import AIAnalysisResult

class PostMediaResponse(BaseModel):
    id: str
    media_url: Optional[str]
    media_type: Optional[str]
    mime_type: Optional[str]
    width: Optional[int]
    height: Optional[int]
    file_size: Optional[int]

    class Config:
        from_attributes = True

class BusinessInfoResponse(BaseModel):
    id: str
    business_name: str

    class Config:
        from_attributes = True

class PostResponse(BaseModel):
    id: str
    business_id: str
    business: BusinessInfoResponse
    source_url: Optional[str]
    text_content: Optional[str]
    published_date: Optional[datetime]
    scraped_date: datetime
    
    # We will embed one analysis if available
    analysis: Optional[AIAnalysisResult] = None
    media: List[PostMediaResponse] = []

    class Config:
        from_attributes = True

class PostListResponse(BaseModel):
    items: List[PostResponse]
    total: int
    page: int
    page_size: int
    pages: int
