from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.schemas.generation import GenerationRequest, RegenerateRequest, GeneratedContentResponse
from app.services.generation_service import GenerationService
from app.core.arq import get_redis_pool
from app.api.dependencies import get_generation_service

generation_router = APIRouter(tags=["generation"])

@generation_router.post("/projects/{project_id}/content/generate", response_model=List[GeneratedContentResponse], status_code=status.HTTP_201_CREATED)
async def start_generation(project_id: str, payload: GenerationRequest, service: GenerationService = Depends(get_generation_service)):
    try:
        contents = service.request_generation(project_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    try:
        pool = await get_redis_pool()
        for gc in contents:
            await pool.enqueue_job("generate_content_job", gc.id)
        await pool.close()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to enqueue generation job")
        
    return contents

@generation_router.post("/projects/{project_id}/content/{content_id}/regenerate", response_model=GeneratedContentResponse, status_code=status.HTTP_201_CREATED)
async def regenerate_content(project_id: str, content_id: str, payload: RegenerateRequest, service: GenerationService = Depends(get_generation_service)):
    try:
        gc = service.request_regeneration(project_id, content_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
        
    try:
        pool = await get_redis_pool()
        await pool.enqueue_job("generate_content_job", gc.id)
        await pool.close()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to enqueue generation job")
        
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
