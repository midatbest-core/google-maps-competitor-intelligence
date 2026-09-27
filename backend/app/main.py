from fastapi import FastAPI
from app.api.routes import health_router, project_router, scrape_router
from app.api.analytics import analytics_router, intelligence_router
from app.api.discovery import discovery_router
from app.api.generation import generation_router
from app.api.auth import auth_router
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title="Google Maps Competitor Update Intelligence API")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(project_router)
app.include_router(scrape_router)
app.include_router(analytics_router)
app.include_router(intelligence_router)
app.include_router(discovery_router)
app.include_router(generation_router)
