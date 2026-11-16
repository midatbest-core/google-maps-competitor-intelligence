from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class GenerationRequest(BaseModel):
    generation_type: str = Field(..., description="IDEA or FULL")
    workflow_mode: Optional[str] = Field(None, description="MARKETING_OPPORTUNITIES or CREATE_CONTENT")
    count: int = Field(1, ge=1, le=5)
    topic: Optional[str] = None
    content_type: Optional[str] = None
    keywords: Optional[List[str]] = None
    cta_style: Optional[str] = None
    campaign_context: Optional[str] = None
    context_type: Optional[str] = None
    context_value: Optional[str] = None
    context_generation_id: Optional[str] = None
    
class RegenerateRequest(BaseModel):
    regeneration_reason: Optional[str] = None
    
class GeneratedContentResponse(BaseModel):
    id: str
    project_id: str
    generation_type: str
    topic: Optional[str]
    generated_idea: Optional[str]
    full_copy: Optional[str]
    keywords: Optional[List[str]]
    cta: Optional[str]
    image_concept: Optional[str]
    content_type: Optional[str]
    
    provider: Optional[str]
    model_name: Optional[str]
    prompt_version: Optional[str]
    
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    parent_generation_id: Optional[str]
    regeneration_reason: Optional[str]
    source_context: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}

class AIStructuredOutput(BaseModel):
    topic: str
    title: str
    body: str
    keywords: List[str]
    cta: str
    offer: Optional[str]
    image_concept: str
    content_type: str
    rationale: str
