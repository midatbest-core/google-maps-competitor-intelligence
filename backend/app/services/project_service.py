from sqlalchemy.orm import Session
from app.repositories.project_repo import ProjectRepository
from app.repositories.business_repo import BusinessProfileRepository
from app.schemas.project import ProjectCreate
from app.schemas.competitor import CompetitorCreate
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.models.competitor import ProjectCompetitor
from app.models.auth import Workspace
from app.models.scrape import ScrapeRun
from app.models.discovery import DiscoveryRun
from app.models.analysis import GeneratedContent
from app.models.post import Post
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectSummaryResponse
from sqlalchemy import select, func, desc
import logging

logger = logging.getLogger(__name__)

class ProjectService:
    def __init__(self, db: Session, workspace: Workspace = None):
        self.db = db
        self.workspace = workspace
        self.project_repo = ProjectRepository(db)
        self.business_repo = BusinessProfileRepository(db)

    def _verify_project(self, project_id: str) -> Project:
        project = self.project_repo.get(project_id)
        if not project:
            raise ValueError("Project not found")
        if self.workspace and project.workspace_id != self.workspace.id:
            raise ValueError("Not authorized to access this project")
        return project

    def create_project(self, project_in: ProjectCreate) -> Project:
        logger.info(f"Creating project {project_in.name}")
        data = project_in.model_dump()
        if self.workspace:
            data["workspace_id"] = self.workspace.id
        return self.project_repo.create(data)

    def update_project(self, project_id: str, project_in: ProjectUpdate) -> Project:
        project = self._verify_project(project_id)
        data = project_in.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(project, key, value)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_project_summary(self, project_id: str) -> ProjectSummaryResponse:
        project = self._verify_project(project_id)

        # competitor count
        competitor_count = self.db.scalar(
            select(func.count(ProjectCompetitor.id)).where(ProjectCompetitor.project_id == project_id)
        ) or 0

        # business ids for post count
        business_ids = self.db.scalars(
            select(ProjectCompetitor.business_id).where(ProjectCompetitor.project_id == project_id)
        ).all()

        post_count = 0
        if business_ids:
            post_count = self.db.scalar(
                select(func.count(Post.id)).where(Post.business_id.in_(business_ids))
            ) or 0

        gc_count = self.db.scalar(
            select(func.count(GeneratedContent.id)).where(GeneratedContent.project_id == project_id)
        ) or 0

        latest_scrape = self.db.scalar(
            select(ScrapeRun).where(ScrapeRun.project_id == project_id).order_by(desc(ScrapeRun.created_at)).limit(1)
        )

        discovery_count = self.db.scalar(
            select(func.count(DiscoveryRun.id)).where(DiscoveryRun.project_id == project_id)
        ) or 0

        return ProjectSummaryResponse(
            project=project,
            competitor_count=competitor_count,
            post_count=post_count,
            generated_content_count=gc_count,
            latest_scrape=latest_scrape.id if latest_scrape else None,
            latest_scrape_status=latest_scrape.status if latest_scrape else None,
            discovery_count=discovery_count
        )

    def get_project(self, project_id: str) -> Project | None:
        return self._verify_project(project_id)

    def get_projects(self, skip: int = 0, limit: int = 100) -> list[Project]:
        if self.workspace:
            stmt = select(Project).where(Project.workspace_id == self.workspace.id).offset(skip).limit(limit)
            return list(self.db.scalars(stmt))
        return self.project_repo.get_all(skip=skip, limit=limit)

    def add_competitor(self, project_id: str, competitor_in: CompetitorCreate) -> ProjectCompetitor:
        self._verify_project(project_id)
        # Check if business already exists
        business = self.business_repo.get_by_name(competitor_in.business_name)
        if not business:
            business = self.business_repo.create(competitor_in.model_dump())

        return self.project_repo.add_competitor(project_id, business.id)

    def get_competitors(self, project_id: str) -> list[ProjectCompetitor]:
        self._verify_project(project_id)
        return self.project_repo.get_competitors(project_id)
