from sqlalchemy.orm import Session
from app.repositories.scrape_repo import ScrapeRunRepository, ScrapeRunCompetitorRepository
from app.repositories.project_repo import ProjectRepository
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor
from datetime import datetime, timezone
from app.models.auth import Workspace
import logging

logger = logging.getLogger(__name__)

class ScrapeService:
    def __init__(self, db: Session, workspace: Workspace = None):
        self.db = db
        self.workspace = workspace
        self.scrape_run_repo = ScrapeRunRepository(db)
        self.run_comp_repo = ScrapeRunCompetitorRepository(db)
        self.project_repo = ProjectRepository(db)

    def _verify_project(self, project_id: str):
        if not self.workspace:
            return
        project = self.project_repo.get(project_id)
        if not project or project.workspace_id != self.workspace.id:
            raise ValueError("Not authorized to access this project")

    def _verify_run(self, run: ScrapeRun):
        if not run:
            return
        self._verify_project(run.project_id)

    def create_scrape_run(self, project_id: str) -> ScrapeRun:
        self._verify_project(project_id)
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
        run = self.scrape_run_repo.get(run_id)
        self._verify_run(run)
        return run

    def get_runs_for_project(self, project_id: str) -> list[ScrapeRun]:
        self._verify_project(project_id)
        return self.scrape_run_repo.get_runs_for_project(project_id)

    def resume_run(self, run_id: str) -> ScrapeRun | None:
        run = self.scrape_run_repo.get(run_id)
        if not run:
            return None
        self._verify_run(run)

        # In a real system, you'd enqueue only PAUSED_MANUAL_INTERVENTION or FAILED competitors
        self.scrape_run_repo.update(run, {"status": "QUEUED"})
        return run

    def get_schedule(self, project_id: str):
        self._verify_project(project_id)
        from app.repositories.scrape_repo import ScrapeScheduleRepository
        repo = ScrapeScheduleRepository(self.db)
        return repo.get_by_project(project_id)

    def update_schedule(self, project_id: str, schedule_in) -> dict:
        self._verify_project(project_id)
        from app.repositories.scrape_repo import ScrapeScheduleRepository
        repo = ScrapeScheduleRepository(self.db)

        # Validation
        import re
        if not re.match(r"^([01][0-9]|2[0-3]):[0-5][0-9]$", schedule_in.time_of_day):
            raise ValueError("Invalid time_of_day format, must be HH:MM")

        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(schedule_in.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError(f"Invalid timezone: {schedule_in.timezone}")

        if schedule_in.frequency != "DAILY":
            raise ValueError("Unsupported frequency, only DAILY is supported")

        schedule = repo.get_by_project(project_id)
        data = schedule_in.model_dump()

        if data["enabled"]:
            data["next_run_at"] = self.calculate_next_run(data["time_of_day"], data["timezone"])
        else:
            data["next_run_at"] = None

        if schedule:
            return repo.update(schedule, data)
        else:
            data["project_id"] = project_id
            return repo.create(data)

    def calculate_next_run(self, time_of_day: str, tz_name: str, now: datetime = None) -> datetime:
        from zoneinfo import ZoneInfo
        from datetime import timedelta
        tz = ZoneInfo(tz_name)
        now = now or datetime.now(timezone.utc)
        now_local = now.astimezone(tz)

        hour, minute = map(int, time_of_day.split(':'))
        next_run_local = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if next_run_local <= now_local:
            next_run_local += timedelta(days=1)

        return next_run_local.astimezone(timezone.utc)

