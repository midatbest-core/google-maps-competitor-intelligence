from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.arq import get_redis_pool
from app.schemas.project import ProjectCreate, ProjectResponse
from app.schemas.competitor import CompetitorCreate, CompetitorResponse
from app.schemas.scrape import ScrapeRunResponse
from app.api.dependencies import get_project_service, get_scrape_service
from app.services.project_service import ProjectService
from app.services.scrape_service import ScrapeService
import urllib.parse
from app.core.config import settings

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
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@project_router.post("/{project_id}/competitors", response_model=CompetitorResponse, status_code=status.HTTP_201_CREATED)
def add_competitor(project_id: str, competitor: CompetitorCreate, service: ProjectService = Depends(get_project_service)):
    return service.add_competitor(project_id, competitor)

@project_router.get("/{project_id}/competitors", response_model=list[CompetitorResponse])
def get_competitors(project_id: str, service: ProjectService = Depends(get_project_service)):
    return service.get_competitors(project_id)

@project_router.post("/{project_id}/scrape", response_model=ScrapeRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_scrape(project_id: str, service: ScrapeService = Depends(get_scrape_service)):
    run = service.create_scrape_run(project_id)
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
    return service.get_runs_for_project(project_id)

@scrape_router.get("/{run_id}", response_model=ScrapeRunResponse)
def get_scrape_run(run_id: str, service: ScrapeService = Depends(get_scrape_service)):
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Scrape run not found")
    return run

@scrape_router.post("/{run_id}/resume", response_model=ScrapeRunResponse)
async def resume_scrape_run(run_id: str, service: ScrapeService = Depends(get_scrape_service)):
    run = service.resume_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Scrape run not found")
    
    try:
        pool = await get_redis_pool()
        await pool.enqueue_job("scrape_job", run.id)
        await pool.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to enqueue resume job")
    
    return run
