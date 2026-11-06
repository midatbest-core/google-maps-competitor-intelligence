from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import logging

from app.schemas.generation import GenerationRequest, RegenerateRequest, GeneratedContentResponse
from app.services.generation_service import GenerationService
from app.core.arq import get_redis_pool
from app.api.dependencies import get_generation_service

generation_router = APIRouter(tags=["generation"])
logger = logging.getLogger(__name__)


async def _enqueue_generation_jobs(contents, service: GenerationService) -> None:
    pool = None
    enqueued_ids = set()
    try:
        pool = await get_redis_pool()
        for content in contents:
            await pool.enqueue_job("generate_content_job", content.id)
            enqueued_ids.add(content.id)
    except Exception as exc:
        failed_ids = [
            content.id for content in contents if content.id not in enqueued_ids
        ]
        service.mark_enqueue_failed(failed_ids)
        logger.error(
            "Failed to enqueue %d generation job(s)",
            len(failed_ids),
        )
        raise HTTPException(
            status_code=503,
            detail="Generation queue is unavailable",
        ) from exc
    finally:
        if pool is not None:
            try:
                await pool.close()
            except Exception:
                logger.warning("Failed to close Redis pool after generation enqueue")

@generation_router.post("/projects/{project_id}/content/generate", response_model=List[GeneratedContentResponse], status_code=status.HTTP_201_CREATED)
async def start_generation(project_id: str, payload: GenerationRequest, service: GenerationService = Depends(get_generation_service)):
    try:
        contents = service.request_generation(project_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    await _enqueue_generation_jobs(contents, service)
        
    return contents

@generation_router.post("/projects/{project_id}/content/{content_id}/regenerate", response_model=GeneratedContentResponse, status_code=status.HTTP_201_CREATED)
async def regenerate_content(project_id: str, content_id: str, payload: RegenerateRequest, service: GenerationService = Depends(get_generation_service)):
    try:
        gc = service.request_regeneration(project_id, content_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    await _enqueue_generation_jobs([gc], service)
        
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
