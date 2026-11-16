import logging
from datetime import datetime
from typing import Optional
import urllib.parse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.dependencies import (
    get_analytics_service,
    get_combined_intelligence_service,
    get_current_workspace,
    get_post_service,
    get_project_service,
    get_scrape_service,
)
from app.core.arq import get_redis_pool
from app.services.outbox_service import OutboxDispatcher
from app.core.config import settings
from app.core.database import get_db
from app.providers.ai.factory import get_ai_provider
from app.providers.ai.gemini import (
    GeminiAPIError,
    GeminiConfigurationError,
    GeminiResponseError,
)
from app.providers.places import GooglePlacesAPIError
from app.schemas.analytics import AnalyticsSummaryResponse
from app.schemas.analysis import IntelligenceReportResponse
from app.schemas.competitor import CompetitorCreate, CompetitorResponse
from app.schemas.post import PostListResponse, PostResponse
from app.schemas.review import ReviewListResponse, ReviewResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectSummaryResponse,
    ProjectUpdate,
)
from app.schemas.scrape import ScrapeRunResponse, ScrapeScheduleResponse, ScrapeScheduleUpdate
from app.services.analytics_service import AnalyticsService
from app.services.combined_intelligence_service import CombinedIntelligenceService
from app.services.post_service import PostService
from app.services.project_service import ProjectService
from app.services.review_service import ReviewService
from app.services.scrape_service import ScrapeService

health_router = APIRouter()
project_router = APIRouter(prefix="/projects", tags=["projects"])
scrape_router = APIRouter(prefix="/scrape-runs", tags=["scrapes"])

def get_review_service(
    db: Session = Depends(get_db),
    workspace=Depends(get_current_workspace),
):
    return ReviewService(db, get_ai_provider(), workspace=workspace)

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
async def add_competitor(project_id: str, competitor: CompetitorCreate, service: ProjectService = Depends(get_project_service)):
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

@project_router.delete("/{project_id}/competitors/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_competitor(project_id: str, competitor_id: str, service: ProjectService = Depends(get_project_service)):
    try:
        service.remove_competitor(project_id, competitor_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.post("/{project_id}/scrape", response_model=ScrapeRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_scrape(project_id: str, service: ScrapeService = Depends(get_scrape_service)):
    try:
        run = service.create_scrape_run(project_id)
    except ValueError as e:
        if "already has an active run" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))

    try:
        pool = await get_redis_pool()
        dispatcher = OutboxDispatcher(pool=pool)
        dispatched = 0
        if hasattr(service, "db") and hasattr(service.db, "scalars"):
            dispatched = await dispatcher.dispatch_pending(service.db, limit=10)
        if dispatched == 0:
            job = await pool.enqueue_job("scrape_job", run.id, _job_id=f"scrape_{run.id}")
            if job is None:
                logger.info(f"Scrape job for run {run.id} is already queued in ARQ")
            else:
                logger.info(f"Enqueued scrape_job for run {run.id} to Redis ARQ worker (job_id: {job.job_id})")
        await pool.close()
    except Exception as e:
        logger.error(f"Failed to enqueue scrape_job for run {run.id} to Redis ARQ: {e}")
        run.status = "FAILED"
        run.error_logs = [f"Queue service unavailable: {str(e)}"]
        if hasattr(service, "db") and hasattr(service.db, "commit"):
            from app.models.outbox import OutboxMessage
            try:
                pending_msgs = service.db.query(OutboxMessage).filter(
                    OutboxMessage.status.in_(["PENDING", "CLAIMED"]),
                    OutboxMessage.event_type == "SCRAPE_RUN_DISPATCH"
                ).all()
                for msg in pending_msgs:
                    if msg.payload and msg.payload.get("run_id") == run.id:
                        msg.status = "FAILED"
                        msg.error_message = f"API enqueue failed: {str(e)}"
            except Exception:
                pass
            service.db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background scraping queue service is unavailable. Please try again later."
        )

    return run

@project_router.get("/{project_id}/scrape-runs", response_model=list[ScrapeRunResponse])
def get_project_scrape_runs(project_id: str, service: ScrapeService = Depends(get_scrape_service)):
    try:
        return service.get_runs_for_project(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.delete("/{project_id}/scrape-runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_scrape_run(project_id: str, run_id: str, service: ScrapeService = Depends(get_scrape_service)):
    try:
        service.delete_run(project_id, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@project_router.get("/{project_id}/review-intelligence")
def get_review_intelligence(project_id: str, service: ReviewService = Depends(get_review_service)):
    intel = service.get_review_intelligence(project_id)
    return intel

@project_router.post("/{project_id}/review-intelligence")
async def generate_review_intelligence(project_id: str, service: ReviewService = Depends(get_review_service)):
    try:
        intel = await service.analyze_project_reviews(project_id)
        return intel
    except GeminiConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except (GeminiAPIError, GeminiResponseError) as e:
        raise HTTPException(status_code=502, detail=str(e))
    except GooglePlacesAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@project_router.get("/{project_id}/reviews", response_model=ReviewListResponse)
def get_project_reviews(
    project_id: str,
    page: int = 1,
    page_size: int = 20,
    competitor_id: Optional[str] = None,
    sentiment: Optional[str] = None,
    source: Optional[str] = None,
    service: ReviewService = Depends(get_review_service)
):
    try:
        return service.get_project_reviews(
            project_id=project_id,
            page=page,
            page_size=page_size,
            competitor_id=competitor_id,
            sentiment=sentiment,
            source=source
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.get("/{project_id}/intelligence", response_model=IntelligenceReportResponse)
def get_project_intelligence(
    project_id: str,
    service: CombinedIntelligenceService = Depends(get_combined_intelligence_service)
):
    try:
        report = service.get_latest_report(project_id)
        if not report:
            raise HTTPException(status_code=404, detail="No intelligence report generated yet")
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@project_router.post("/{project_id}/intelligence/analyze", response_model=IntelligenceReportResponse)
async def generate_project_intelligence(
    project_id: str,
    service: CombinedIntelligenceService = Depends(get_combined_intelligence_service)
):
    try:
        report = await service.generate_report(project_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate intelligence: {str(e)}")

@project_router.get("/{project_id}/intelligence/history", response_model=list[IntelligenceReportResponse])
def get_project_intelligence_history(
    project_id: str,
    limit: int = 10,
    service: CombinedIntelligenceService = Depends(get_combined_intelligence_service)
):
    try:
        return service.list_reports(project_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Schedule endpoints removed

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
        if "already active" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))

    try:
        pool = await get_redis_pool()
        dispatcher = OutboxDispatcher(pool=pool)
        dispatched = 0
        if hasattr(service, "db") and hasattr(service.db, "scalars"):
            dispatched = await dispatcher.dispatch_pending(service.db, limit=10)
        if dispatched == 0:
            job = await pool.enqueue_job("scrape_job", run.id, _job_id=f"scrape_{run.id}")
            if job is None:
                logger.info(f"Resume scrape job for run {run.id} is already queued in ARQ")
            else:
                logger.info(f"Enqueued resumed scrape_job for run {run.id} to Redis ARQ worker (job_id: {job.job_id})")
        await pool.close()
    except Exception as e:
        logger.error(f"Failed to enqueue resumed scrape_job for run {run.id} to Redis ARQ: {e}")
        run.status = "FAILED"
        run.error_logs = [f"Queue service unavailable during resume: {str(e)}"]
        if hasattr(service, "db") and hasattr(service.db, "commit"):
            from app.models.outbox import OutboxMessage
            try:
                pending_msgs = service.db.query(OutboxMessage).filter(
                    OutboxMessage.status.in_(["PENDING", "CLAIMED"]),
                    OutboxMessage.event_type == "SCRAPE_RUN_DISPATCH"
                ).all()
                for msg in pending_msgs:
                    if msg.payload and msg.payload.get("run_id") == run.id:
                        msg.status = "FAILED"
                        msg.error_message = f"API resume enqueue failed: {str(e)}"
            except Exception:
                pass
            service.db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background scraping queue service is unavailable. Please try again later."
        )

    return run
