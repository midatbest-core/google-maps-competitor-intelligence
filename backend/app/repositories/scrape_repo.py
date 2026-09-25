from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from .base import BaseRepository
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor, ScrapeObservation

class ScrapeRunRepository(BaseRepository[ScrapeRun]):
    def __init__(self, session: Session):
        super().__init__(ScrapeRun, session)

    def get_runs_for_project(self, project_id: str, skip: int = 0, limit: int = 100) -> List[ScrapeRun]:
        stmt = select(ScrapeRun).where(ScrapeRun.project_id == project_id).offset(skip).limit(limit)
        return list(self.session.scalars(stmt))

class ScrapeRunCompetitorRepository(BaseRepository[ScrapeRunCompetitor]):
    def __init__(self, session: Session):
        super().__init__(ScrapeRunCompetitor, session)

    def get_by_run_and_business(self, run_id: str, business_id: str) -> Optional[ScrapeRunCompetitor]:
        stmt = select(ScrapeRunCompetitor).where(
            ScrapeRunCompetitor.scrape_run_id == run_id,
            ScrapeRunCompetitor.business_id == business_id
        )
        return self.session.scalar(stmt)

class ScrapeObservationRepository(BaseRepository[ScrapeObservation]):
    def __init__(self, session: Session):
        super().__init__(ScrapeObservation, session)
