from sqlalchemy.orm import Session
from app.repositories.scrape_repo import ScrapeRunRepository, ScrapeRunCompetitorRepository
from app.repositories.project_repo import ProjectRepository
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class ScrapeService:
    def __init__(self, db: Session):
        self.db = db
        self.scrape_run_repo = ScrapeRunRepository(db)
        self.run_comp_repo = ScrapeRunCompetitorRepository(db)
        self.project_repo = ProjectRepository(db)

    def create_scrape_run(self, project_id: str) -> ScrapeRun:
        logger.info(f"Creating scrape run for project {project_id}")
        
        # 1. Create Run
        run = self.scrape_run_repo.create({
            "project_id": project_id,
            "status": "QUEUED"
        })

        # 2. Add Competitors
        competitors = self.project_repo.get_competitors(project_id)
        for comp in competitors:
            self.run_comp_repo.create({
                "scrape_run_id": run.id,
                "business_id": comp.business_id,
                "status": "PENDING"
            })
        
        # Update run stats
        self.scrape_run_repo.update(run, {"competitors_attempted": len(competitors)})
        return run

    def get_run(self, run_id: str) -> ScrapeRun | None:
        return self.scrape_run_repo.get(run_id)

    def get_runs_for_project(self, project_id: str) -> list[ScrapeRun]:
        return self.scrape_run_repo.get_runs_for_project(project_id)

    def resume_run(self, run_id: str) -> ScrapeRun | None:
        run = self.scrape_run_repo.get(run_id)
        if not run:
            return None
        
        # In a real system, you'd enqueue only PAUSED_MANUAL_INTERVENTION or FAILED competitors
        self.scrape_run_repo.update(run, {"status": "QUEUED"})
        return run

