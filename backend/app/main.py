from fastapi import FastAPI
from app.api.routes import health_router, project_router, scrape_router
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title="Google Maps Competitor Update Intelligence API")

app.include_router(health_router)
app.include_router(project_router)
app.include_router(scrape_router)
