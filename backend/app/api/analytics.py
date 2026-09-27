from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_analytics_service, get_analysis_service
from app.services.analytics_service import AnalyticsService
from app.services.analysis_service import AnalysisService

analytics_router = APIRouter(prefix="/projects", tags=["analytics"])

@analytics_router.get("/{project_id}/analytics/topics")
def get_topics(project_id: str, service: AnalyticsService = Depends(get_analytics_service)):
    return service.get_topic_frequency(project_id)

@analytics_router.get("/{project_id}/analytics/competitors")
def get_competitor_coverage(project_id: str, service: AnalyticsService = Depends(get_analytics_service)):
    return service.get_competitor_coverage(project_id)

@analytics_router.get("/{project_id}/analytics/keywords")
def get_keywords(project_id: str, service: AnalyticsService = Depends(get_analytics_service)):
    return service.get_keyword_frequency(project_id)

@analytics_router.get("/{project_id}/analytics/publishing")
def get_publishing(project_id: str, service: AnalyticsService = Depends(get_analytics_service)):
    return service.get_publishing_patterns(project_id)

@analytics_router.get("/{project_id}/analytics/gaps")
def get_gaps(project_id: str, service: AnalyticsService = Depends(get_analytics_service)):
    return service.get_content_gaps(project_id)

intelligence_router = APIRouter(prefix="/posts", tags=["intelligence"])

@intelligence_router.post("/{post_id}/analyze")
async def trigger_analysis(post_id: str, service: AnalysisService = Depends(get_analysis_service)):
    analysis = await service.analyze_post(post_id)
    if not analysis:
        raise HTTPException(status_code=400, detail="Failed to analyze post")
    return {"status": "success", "analysis_id": analysis.id}

@intelligence_router.post("/{post_id}/embed")
async def trigger_embed(post_id: str, service: AnalysisService = Depends(get_analysis_service)):
    embed = await service.embed_post(post_id)
    if not embed:
        raise HTTPException(status_code=400, detail="Failed to embed post")
    return {"status": "success", "embed_id": embed.id}
