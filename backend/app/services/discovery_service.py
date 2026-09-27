import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional, List, Tuple
from datetime import datetime, timezone
import math

from app.models.discovery import DiscoveryRun, DiscoveryCandidate
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.models.competitor import ProjectCompetitor
from app.schemas.discovery import DiscoveryRunCreate, DiscoveryCandidateSchema, DirectCompetitorCreate
from app.providers.discovery.base import DiscoveryProvider

logger = logging.getLogger(__name__)

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0 # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

from app.models.auth import Workspace

class DiscoveryService:
    def __init__(self, db: Session, provider: Optional[DiscoveryProvider] = None, workspace: Workspace = None):
        self.db = db
        self.provider = provider
        self.workspace = workspace
        
    def _verify_project(self, project_id: str):
        if not self.workspace:
            return
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project or project.workspace_id != self.workspace.id:
            raise ValueError("Not authorized to access this project")

    def _normalize_url(self, url: str) -> str:
        if not url: return ""
        return url.split("?")[0].rstrip("/")

    def _generate_fallback_identity(self, name: str, address: str) -> str:
        n = (name or "").lower().strip()
        a = (address or "").lower().strip()
        return f"{n}::{a}"

    def create_discovery_run(self, project_id: str, payload: DiscoveryRunCreate) -> DiscoveryRun:
        self._verify_project(project_id)
        # Verify project exists
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project:
            raise ValueError("Project not found")

        run = DiscoveryRun(
            project_id=project_id,
            query=payload.query,
            location=payload.location,
            latitude=payload.latitude,
            longitude=payload.longitude,
            radius=payload.radius,
            category=payload.category,
            status="QUEUED"
        )
        self.db.add(run)
        self.db.commit()
        return run
        
    def get_run(self, run_id: str) -> Optional[DiscoveryRun]:
        run = self.db.query(DiscoveryRun).filter_by(id=run_id).first()
        if run:
            self._verify_project(run.project_id)
        return run

    def get_runs_for_project(self, project_id: str) -> List[DiscoveryRun]:
        self._verify_project(project_id)
        return self.db.query(DiscoveryRun).filter_by(project_id=project_id).order_by(DiscoveryRun.created_at.desc()).all()

    def get_candidates(self, project_id: str, skip: int = 0, limit: int = 50) -> List[DiscoveryCandidate]:
        self._verify_project(project_id)
        # Project scoping explicitly
        return self.db.query(DiscoveryCandidate).join(DiscoveryRun).filter(
            DiscoveryRun.project_id == project_id
        ).order_by(DiscoveryCandidate.relevance_score.desc().nulls_last(), DiscoveryCandidate.created_at.desc()).offset(skip).limit(limit).all()

    async def execute_discovery(self, run_id: str):
        if not self.provider:
            raise ValueError("Provider not configured")
            
        run = self.db.query(DiscoveryRun).filter_by(id=run_id).first()
        if not run: return
        
        run.status = "RUNNING"
        run.started_at = datetime.now(timezone.utc)
        self.db.commit()
        
        try:
            candidates_data = await self.provider.discover(
                query=run.query,
                location=run.location,
                latitude=run.latitude,
                longitude=run.longitude,
                radius=run.radius,
                category=run.category
            )
            
            for c_data in candidates_data:
                # Deduplication logic across same run
                ident = c_data.source_identifier
                if not ident:
                    ident = self._normalize_url(c_data.source_url)
                if not ident:
                    ident = self._generate_fallback_identity(c_data.business_name, c_data.address)
                    
                existing = self.db.query(DiscoveryCandidate).join(DiscoveryRun).filter(
                    DiscoveryRun.project_id == run.project_id,
                    DiscoveryCandidate.source_identifier == ident
                ).first()
                
                if existing:
                    run.duplicates_skipped += 1
                    continue
                    
                # Calculate simple relevance score based on distance if possible
                score = 1.0
                if run.latitude and run.longitude and c_data.latitude and c_data.longitude:
                    dist = haversine_distance(run.latitude, run.longitude, c_data.latitude, c_data.longitude)
                    score = max(0.0, 1.0 - (dist / max(run.radius or 50, 1)))
                
                cand = DiscoveryCandidate(
                    discovery_run_id=run.id,
                    source_identifier=ident,
                    source_url=c_data.source_url,
                    business_name=c_data.business_name,
                    category=c_data.category,
                    address=c_data.address,
                    locality=c_data.locality,
                    latitude=c_data.latitude,
                    longitude=c_data.longitude,
                    rating=c_data.rating,
                    review_count=c_data.review_count,
                    phone=c_data.phone,
                    website=c_data.website,
                    normalized_name=(c_data.business_name or "").lower(),
                    normalized_address=(c_data.address or "").lower(),
                    discovery_query=run.query,
                    relevance_score=score
                )
                self.db.add(cand)
                try:
                    self.db.commit()
                    run.total_candidates += 1
                except IntegrityError:
                    self.db.rollback()
                    run.duplicates_skipped += 1
                    
            run.status = "SUCCESS"
        except Exception as e:
            logger.exception("Discovery failed")
            run.status = "FAILED"
            run.error_message = str(e)
            
        run.completed_at = datetime.now(timezone.utc)
        self.db.commit()

    def _resolve_business_profile(self, source_id: Optional[str], source_url: Optional[str], name: str, address: Optional[str]) -> BusinessProfile:
        norm_url = self._normalize_url(source_url) if source_url else None
        
        # 1. By Source ID
        if source_id:
            bp = self.db.query(BusinessProfile).filter_by(canonical_source_id=source_id).first()
            if bp: return bp
            
        # 2. By Google Maps URL
        if norm_url:
            bp = self.db.query(BusinessProfile).filter(BusinessProfile.google_maps_url.like(f"{norm_url}%")).first()
            if bp: return bp
            
        # Create new
        bp = BusinessProfile(
            business_name=name,
            google_maps_url=source_url,
            canonical_source_id=source_id,
            address=address
        )
        self.db.add(bp)
        self.db.commit()
        return bp

    def select_candidate(self, project_id: str, candidate_id: str) -> ProjectCompetitor:
        self._verify_project(project_id)
        cand = self.db.query(DiscoveryCandidate).join(DiscoveryRun).filter(
            DiscoveryCandidate.id == candidate_id,
            DiscoveryRun.project_id == project_id
        ).first()
        
        if not cand:
            raise ValueError("Candidate not found or does not belong to project")
            
        bp = self._resolve_business_profile(
            source_id=cand.source_identifier,
            source_url=cand.source_url,
            name=cand.business_name,
            address=cand.address
        )
        
        # Check existing ProjectCompetitor
        pc = self.db.query(ProjectCompetitor).filter_by(project_id=project_id, business_id=bp.id).first()
        if pc:
            cand.status = "ALREADY_COMPETITOR"
            self.db.commit()
            return pc
            
        pc = ProjectCompetitor(project_id=project_id, business_id=bp.id)
        self.db.add(pc)
        cand.status = "SELECTED"
        self.db.commit()
        return pc

    def reject_candidate(self, project_id: str, candidate_id: str) -> DiscoveryCandidate:
        self._verify_project(project_id)
        cand = self.db.query(DiscoveryCandidate).join(DiscoveryRun).filter(
            DiscoveryCandidate.id == candidate_id,
            DiscoveryRun.project_id == project_id
        ).first()
        
        if not cand:
            raise ValueError("Candidate not found or does not belong to project")
            
        cand.status = "REJECTED"
        self.db.commit()
        return cand

    def add_direct_competitor(self, project_id: str, payload: DirectCompetitorCreate) -> ProjectCompetitor:
        self._verify_project(project_id)
        project = self.db.query(Project).filter_by(id=project_id).first()
        if not project:
            raise ValueError("Project not found")
            
        bp = self._resolve_business_profile(
            source_id=payload.source_identifier,
            source_url=payload.source_url,
            name=payload.business_name,
            address=payload.address
        )
        
        pc = self.db.query(ProjectCompetitor).filter_by(project_id=project_id, business_id=bp.id).first()
        if pc:
            return pc
            
        pc = ProjectCompetitor(project_id=project_id, business_id=bp.id)
        self.db.add(pc)
        self.db.commit()
        return pc
        
    def resume_discovery(self, project_id: str, run_id: str) -> DiscoveryRun:
        self._verify_project(project_id)
        run = self.db.query(DiscoveryRun).filter_by(id=run_id, project_id=project_id).first()
        if not run or run.status not in ("PAUSED_MANUAL_INTERVENTION", "FAILED", "PARTIAL_SUCCESS"):
            raise ValueError("Run cannot be resumed or does not belong to project")
            
        run.status = "QUEUED"
        self.db.commit()
        return run
