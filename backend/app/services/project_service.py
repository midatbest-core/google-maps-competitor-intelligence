from sqlalchemy.orm import Session
from app.repositories.project_repo import ProjectRepository
from app.repositories.business_repo import BusinessProfileRepository
from app.schemas.project import ProjectCreate
from app.schemas.competitor import CompetitorCreate
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.models.competitor import ProjectCompetitor
import logging

logger = logging.getLogger(__name__)

class ProjectService:
    def __init__(self, db: Session):
        self.db = db
        self.project_repo = ProjectRepository(db)
        self.business_repo = BusinessProfileRepository(db)

    def create_project(self, project_in: ProjectCreate) -> Project:
        logger.info(f"Creating project {project_in.name}")
        return self.project_repo.create(project_in.model_dump())

    def get_project(self, project_id: str) -> Project | None:
        return self.project_repo.get(project_id)

    def get_projects(self, skip: int = 0, limit: int = 100) -> list[Project]:
        return self.project_repo.get_all(skip=skip, limit=limit)

    def add_competitor(self, project_id: str, competitor_in: CompetitorCreate) -> ProjectCompetitor:
        # Check if business already exists
        business = self.business_repo.get_by_name(competitor_in.business_name)
        if not business:
            business = self.business_repo.create(competitor_in.model_dump())
        
        return self.project_repo.add_competitor(project_id, business.id)

    def get_competitors(self, project_id: str) -> list[ProjectCompetitor]:
        return self.project_repo.get_competitors(project_id)
