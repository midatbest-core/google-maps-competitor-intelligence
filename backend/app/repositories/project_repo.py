from sqlalchemy.orm import Session
from sqlalchemy import select
from .base import BaseRepository
from app.models.project import Project
from app.models.competitor import ProjectCompetitor

class ProjectRepository(BaseRepository[Project]):
    def __init__(self, session: Session):
        super().__init__(Project, session)

    def get_with_competitors(self, project_id: str) -> Project | None:
        # Simplistic eager load implementation can go here if needed.
        return self.get(project_id)

    def add_competitor(self, project_id: str, business_id: str) -> ProjectCompetitor:
        db_obj = ProjectCompetitor(project_id=project_id, business_id=business_id)
        self.session.add(db_obj)
        self.session.commit()
        self.session.refresh(db_obj)
        return db_obj
