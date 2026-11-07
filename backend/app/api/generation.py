from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List
import logging

from app.schemas.generation import GenerationRequest, RegenerateRequest, GeneratedContentResponse
from app.services.generation_service import GenerationService
from app.core.arq import get_redis_pool
from app.api.dependencies import get_generation_service
from app.workers.main import generate_content_job

generation_router = APIRouter(tags=["generation"])
logger = logging.getLogger(__name__)


async def _enqueue_generation_jobs(contents, service: GenerationService, background_tasks: BackgroundTasks = None) -> None:
    try:
        pool = await get_redis_pool()
        for gc in contents:
            await pool.enqueue_job("generate_content_job", gc.id)
        await pool.close()
    except Exception as exc:
        if background_tasks is None:
            for gc in contents:
                gc.status = "FAILED"
                gc.error_message = "Failed to enqueue generation job"
            service.db.commit()
            raise HTTPException(status_code=503, detail="Generation queue is unavailable")
        logger.debug(f"Redis unavailable, falling back to background tasks: {exc}")

    if background_tasks is not None:
        for content in contents:
            background_tasks.add_task(generate_content_job, None, content.id)

@generation_router.post("/projects/{project_id}/content/generate", response_model=List[GeneratedContentResponse], status_code=status.HTTP_201_CREATED)
async def start_generation(
    project_id: str,
    payload: GenerationRequest,
    background_tasks: BackgroundTasks = None,
    service: GenerationService = Depends(get_generation_service)
):
    if isinstance(background_tasks, GenerationService):
        service = background_tasks
        background_tasks = None

    try:
        contents = service.request_generation(project_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    await _enqueue_generation_jobs(contents, service, background_tasks)
        
    return contents

@generation_router.post("/projects/{project_id}/content/{content_id}/regenerate", response_model=GeneratedContentResponse, status_code=status.HTTP_201_CREATED)
async def regenerate_content(
    project_id: str,
    content_id: str,
    payload: RegenerateRequest,
    background_tasks: BackgroundTasks = None,
    service: GenerationService = Depends(get_generation_service)
):
    if isinstance(background_tasks, GenerationService):
        service = background_tasks
        background_tasks = None

    try:
        gc = service.request_regeneration(project_id, content_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    await _enqueue_generation_jobs([gc], service, background_tasks)
        
    return gc

@generation_router.get("/projects/{project_id}/content", response_model=List[GeneratedContentResponse])
def list_content(project_id: str, skip: int = 0, limit: int = 50, service: GenerationService = Depends(get_generation_service)):
    if limit > 100:
        limit = 100
    return service.list_generated_content(project_id, skip=skip, limit=limit)

@generation_router.get("/projects/{project_id}/content/{content_id}", response_model=GeneratedContentResponse)
def get_content(project_id: str, content_id: str, service: GenerationService = Depends(get_generation_service)):
    try:
        return service.get_generated_content(project_id, content_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
