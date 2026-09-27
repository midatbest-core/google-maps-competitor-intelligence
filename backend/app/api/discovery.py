from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies import get_discovery_service
from app.services.discovery_service import DiscoveryService
from app.schemas.discovery import DiscoveryRunCreate, DiscoveryRunResponse, DiscoveryCandidateResponse, DirectCompetitorCreate
from app.schemas.competitor import CompetitorResponse
from app.core.arq import get_redis_pool
from typing import List

discovery_router = APIRouter(tags=["discovery"])

@discovery_router.post("/projects/{project_id}/discovery", response_model=DiscoveryRunResponse, status_code=status.HTTP_201_CREATED)
async def start_discovery(project_id: str, payload: DiscoveryRunCreate, service: DiscoveryService = Depends(get_discovery_service)):
    try:
        run = service.create_discovery_run(project_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    try:
        pool = await get_redis_pool()
        await pool.enqueue_job("discovery_job", run.id)
        await pool.close()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to enqueue discovery job")
        
    return run

@discovery_router.get("/projects/{project_id}/discovery-runs", response_model=List[DiscoveryRunResponse])
def list_discovery_runs(project_id: str, service: DiscoveryService = Depends(get_discovery_service)):
    return service.get_runs_for_project(project_id)

@discovery_router.get("/projects/{project_id}/discovery-runs/{run_id}", response_model=DiscoveryRunResponse)
def get_discovery_run(project_id: str, run_id: str, service: DiscoveryService = Depends(get_discovery_service)):
    run = service.get_run(run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

@discovery_router.get("/projects/{project_id}/discovery-candidates", response_model=List[DiscoveryCandidateResponse])
def list_candidates(project_id: str, skip: int = 0, limit: int = 50, service: DiscoveryService = Depends(get_discovery_service)):
    if limit > 100:
        limit = 100
    return service.get_candidates(project_id, skip=skip, limit=limit)

@discovery_router.post("/projects/{project_id}/discovery-candidates/{candidate_id}/select", response_model=CompetitorResponse)
def select_candidate(project_id: str, candidate_id: str, service: DiscoveryService = Depends(get_discovery_service)):
    try:
        comp = service.select_candidate(project_id, candidate_id)
        return comp
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@discovery_router.post("/projects/{project_id}/discovery-candidates/{candidate_id}/reject", response_model=DiscoveryCandidateResponse)
def reject_candidate(project_id: str, candidate_id: str, service: DiscoveryService = Depends(get_discovery_service)):
    try:
        cand = service.reject_candidate(project_id, candidate_id)
        return cand
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@discovery_router.post("/projects/{project_id}/competitors/direct", response_model=CompetitorResponse)
def add_direct_competitor(project_id: str, payload: DirectCompetitorCreate, service: DiscoveryService = Depends(get_discovery_service)):
    try:
        comp = service.add_direct_competitor(project_id, payload)
        return comp
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@discovery_router.post("/projects/{project_id}/discovery-runs/{run_id}/resume", response_model=DiscoveryRunResponse)
async def resume_discovery(project_id: str, run_id: str, service: DiscoveryService = Depends(get_discovery_service)):
    try:
        run = service.resume_discovery(project_id, run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    try:
        pool = await get_redis_pool()
        await pool.enqueue_job("discovery_job", run.id)
        await pool.close()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to enqueue discovery job")
        
    return run
