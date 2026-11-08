import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from app.api.routes import health_router, project_router, scrape_router
from app.api.analytics import analytics_router, intelligence_router
from app.api.discovery import discovery_router
from app.api.generation import generation_router
from app.api.auth import auth_router
from app.core.logging import setup_logging
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

setup_logging()

app = FastAPI(title="Google Maps Competitor Update Intelligence API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if hasattr(settings, 'CORS_ORIGINS') else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(project_router)
app.include_router(scrape_router)
app.include_router(analytics_router)
app.include_router(intelligence_router)
app.include_router(discovery_router)
app.include_router(generation_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Serve built frontend assets in production / single-service deployments
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")
if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Don't hijack API or docs routes
        if full_path.startswith(("api", "docs", "redoc", "openapi.json", "health")):
            return {"error": "Not Found"}
        target_file = os.path.join(frontend_dist, full_path)
        if os.path.isfile(target_file):
            return FileResponse(target_file)
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "running"}
else:
    @app.get("/")
    async def root():
        return {
            "name": "Google Maps Competitor Intelligence API",
            "status": "running",
            "docs": "/docs",
            "health": "/health"
        }
