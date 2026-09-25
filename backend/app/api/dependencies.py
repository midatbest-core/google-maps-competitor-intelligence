from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.project_service import ProjectService
from app.services.scrape_service import ScrapeService

def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)

def get_scrape_service(db: Session = Depends(get_db)) -> ScrapeService:
    return ScrapeService(db)
