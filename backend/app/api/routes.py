from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.arq import get_redis_pool
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, ProjectSummaryResponse
from app.schemas.competitor import CompetitorCreate, CompetitorResponse
from app.schemas.scrape import ScrapeRunResponse, ScrapeScheduleResponse, ScrapeScheduleUpdate
from app.api.dependencies import get_project_service, get_scrape_service
from app.services.project_service import ProjectService
from app.services.scrape_service import ScrapeService
import urllib.parse
from app.core.config import settings
from app.schemas.post import PostListResponse, PostResponse
from app.schemas.analytics import AnalyticsSummaryResponse
from app.api.dependencies import get_project_service, get_scrape_service, get_post_service, get_analytics_service
from app.services.post_service import PostService
from app.services.analytics_service import AnalyticsService
from typing import Optional
from datetime import datetime
health_router = APIRouter()
project_router = APIRouter(prefix="/projects", tags=["projects"])
scrape_router = APIRouter(prefix="/scrape-runs", tags=["scrapes"])

@health_router.get("/health")
def health_check():
    return {"status": "ok"}

@health_router.get("/ready")
async def ready_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database not ready")

    try:
        # Check redis
        pool = await get_redis_pool()
        await pool.ping()
        await pool.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail="Redis not ready")

    return {"status": "ready"}

@project_router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(project: ProjectCreate, service: ProjectService = Depends(get_project_service)):
    return service.create_project(project)

@project_router.get("", response_model=list[ProjectResponse])
def get_projects(skip: int = 0, limit: int = 100, service: ProjectService = Depends(get_project_service)):
    return service.get_projects(skip=skip, limit=limit)

@project_router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, service: ProjectService = Depends(get_project_service)):
    try:
        project = service.get_project(project_id)
        return project
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, project_in: ProjectUpdate, service: ProjectService = Depends(get_project_service)):
    try:
        return service.update_project(project_id, project_in)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.get("/{project_id}/summary", response_model=ProjectSummaryResponse)
def get_project_summary(project_id: str, service: ProjectService = Depends(get_project_service)):
    try:
        return service.get_project_summary(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.post("/{project_id}/competitors", response_model=CompetitorResponse, status_code=status.HTTP_201_CREATED)
def add_competitor(project_id: str, competitor: CompetitorCreate, service: ProjectService = Depends(get_project_service)):
    try:
        return service.add_competitor(project_id, competitor)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.get("/{project_id}/competitors", response_model=list[CompetitorResponse])
def get_competitors(project_id: str, service: ProjectService = Depends(get_project_service)):
    try:
        return service.get_competitors(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.post("/{project_id}/scrape", response_model=ScrapeRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_scrape(project_id: str, service: ScrapeService = Depends(get_scrape_service)):
    try:
        run = service.create_scrape_run(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        pool = await get_redis_pool()
        await pool.enqueue_job("scrape_job", run.id)
        await pool.close()
    except Exception as e:
        # Mark failed if we can't enqueue
        raise HTTPException(status_code=500, detail="Failed to enqueue scrape job")
    return run

@project_router.get("/{project_id}/scrape-runs", response_model=list[ScrapeRunResponse])
def get_project_scrape_runs(project_id: str, service: ScrapeService = Depends(get_scrape_service)):
    try:
        return service.get_runs_for_project(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.get("/{project_id}/scrape-schedule", response_model=ScrapeScheduleResponse)
def get_scrape_schedule(project_id: str, service: ScrapeService = Depends(get_scrape_service)):
    try:
        schedule = service.get_schedule(project_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return schedule
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.put("/{project_id}/scrape-schedule", response_model=ScrapeScheduleResponse)
def update_scrape_schedule(project_id: str, schedule_in: ScrapeScheduleUpdate, service: ScrapeService = Depends(get_scrape_service)):
    try:
        return service.update_schedule(project_id, schedule_in)
    except ValueError as e:
        if "Invalid" in str(e) or "Unsupported" in str(e):
            raise HTTPException(status_code=422, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))

@project_router.get("/{project_id}/posts", response_model=PostListResponse)
def get_project_posts(
    project_id: str,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    competitor_id: Optional[str] = None,
    topic: Optional[str] = None,
    content_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    has_analysis: Optional[bool] = None,
    service: PostService = Depends(get_post_service)
):
    try:
        return service.get_posts(
            project_id=project_id,
            page=page,
            page_size=page_size,
            search=search,
            competitor_id=competitor_id,
            topic=topic,
            content_type=content_type,
            date_from=date_from,
            date_to=date_to,
            has_analysis=has_analysis
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.get("/{project_id}/posts/{post_id}", response_model=PostResponse)
def get_project_post(project_id: str, post_id: str, service: PostService = Depends(get_post_service)):
    try:
        return service.get_post_detail(project_id, post_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.get("/{project_id}/analytics/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(project_id: str, service: AnalyticsService = Depends(get_analytics_service)):
    try:
        topics = service.get_topic_percentage(project_id)
        coverage = service.get_competitor_coverage(project_id)
        keywords = service.get_keyword_frequency(project_id)
        publishing = service.get_publishing_patterns(project_id)
        gaps = service.get_content_gaps(project_id)
        detailed_topic_gaps = service.get_detailed_topic_gaps(project_id)
        detailed_keyword_gaps = service.get_detailed_keyword_gaps(project_id)
        detailed_content_type_gaps = service.get_content_type_gaps(project_id)

        # In case some fields are not available or are empty structures
        if not gaps:
            gaps = {"topic_gaps": [], "keyword_gaps": []}

        return {
            "topics": topics,
            "competitor_coverage": coverage,
            "keywords": keywords,
            "publishing_patterns": publishing,
            "content_gaps": gaps,
            "detailed_topic_gaps": detailed_topic_gaps,
            "detailed_keyword_gaps": detailed_keyword_gaps,
            "detailed_content_type_gaps": detailed_content_type_gaps
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@scrape_router.get("/{run_id}", response_model=ScrapeRunResponse)
def get_scrape_run(run_id: str, service: ScrapeService = Depends(get_scrape_service)):
    try:
        run = service.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Scrape run not found")
        return run
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@scrape_router.post("/{run_id}/resume", response_model=ScrapeRunResponse)
async def resume_scrape_run(run_id: str, service: ScrapeService = Depends(get_scrape_service)):
    try:
        run = service.resume_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Scrape run not found")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        pool = await get_redis_pool()
        await pool.enqueue_job("scrape_job", run.id)
        await pool.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to enqueue resume job")

    return run
