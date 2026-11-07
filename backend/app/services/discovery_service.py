from urllib.parse import urlparse, parse_qs
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
        if not url:
            return ""
        url = url.strip()
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            # If Google Maps CID is present, retain it as canonical identifier
            if "cid" in qs and qs["cid"]:
                return f"https://maps.google.com/?cid={qs['cid'][0]}"
            # If place_id is in query
            if "q" in qs and any("place_id:" in q for q in qs["q"]):
                q_val = [q for q in qs["q"] if "place_id:" in q][0]
                return f"https://www.google.com/maps/place/?q={q_val}"
            clean_path = parsed.path.rstrip("/")
            if clean_path:
                return f"{parsed.scheme}://{parsed.netloc}{clean_path}"
            return url.split("?")[0].rstrip("/")
        except Exception:
            return url.rstrip("/")

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

        radius_km = payload.radius if (payload.radius and payload.radius > 0) else 10

        run = DiscoveryRun(
            project_id=project_id,
            query=payload.query,
            location=payload.location,
            latitude=payload.latitude,
            longitude=payload.longitude,
            radius=radius_km,
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
        
        # Get active competitor businesses for this project to accurately synchronize status
        pcs = self.db.query(ProjectCompetitor).filter_by(project_id=project_id, is_active=True).all()
        active_business_ids = {pc.business_id for pc in pcs}
        
        active_source_ids = set()
        active_cids = set()
        if active_business_ids:
            bps = self.db.query(BusinessProfile).filter(BusinessProfile.id.in_(active_business_ids)).all()
            for bp in bps:
                if bp.canonical_source_id:
                    active_source_ids.add(bp.canonical_source_id)
                if bp.google_maps_url and "cid=" in bp.google_maps_url:
                    cid = bp.google_maps_url.split("cid=")[-1].split("&")[0]
                    active_cids.add(cid)

        candidates = self.db.query(DiscoveryCandidate).join(DiscoveryRun).filter(
            DiscoveryRun.project_id == project_id
        ).order_by(DiscoveryCandidate.relevance_score.desc().nulls_last(), DiscoveryCandidate.created_at.desc()).offset(skip).limit(limit).all()

        # Synchronize status: if candidate was falsely marked ALREADY_COMPETITOR or SELECTED but
        # is not in actual active ProjectCompetitors, restore it to NEW so user can select it
        needs_commit = False
        for cand in candidates:
            is_comp = False
            if cand.source_identifier and cand.source_identifier in active_source_ids:
                is_comp = True
            elif cand.source_url and "cid=" in cand.source_url:
                c_cid = cand.source_url.split("cid=")[-1].split("&")[0]
                if c_cid in active_cids:
                    is_comp = True

            if is_comp:
                if cand.status not in ("SELECTED", "ALREADY_COMPETITOR"):
                    cand.status = "ALREADY_COMPETITOR"
                    needs_commit = True
            elif cand.status in ("ALREADY_COMPETITOR", "SELECTED"):
                # Candidate was not actually imported as an active competitor
                cand.status = "NEW"
                needs_commit = True

        if needs_commit:
            self.db.commit()

        return candidates

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

            # If run had no center coordinates but candidates have them, save center coords to run
            if (run.latitude is None or run.longitude is None) and candidates_data:
                valid_coords = [(c.latitude, c.longitude) for c in candidates_data if c.latitude is not None and c.longitude is not None]
                if valid_coords:
                    run.latitude = valid_coords[0][0]
                    run.longitude = valid_coords[0][1]
            
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
                    
                # Calculate distance-based relevance score (haversine)
                score = 1.0
                if run.latitude and run.longitude and c_data.latitude and c_data.longitude:
                    dist = haversine_distance(run.latitude, run.longitude, c_data.latitude, c_data.longitude)
                    radius_km = float(run.radius or 10)
                    score = max(0.01, 1.0 - (dist / max(radius_km * 1.5, 1.0)))
                
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
        
        # 1. By Source ID (Google place_id or canonical identifier)
        if source_id:
            bp = self.db.query(BusinessProfile).filter_by(canonical_source_id=source_id).first()
            if bp:
                return bp
            
        # 2. By Google Maps URL (only specific canonical matches, never generic domain prefixes)
        if norm_url:
            # Exact match on normalized url
            bp = self.db.query(BusinessProfile).filter_by(google_maps_url=norm_url).first()
            if bp:
                return bp
            # If URL contains a CID, match by CID parameter
            if "cid=" in norm_url:
                cid = norm_url.split("cid=")[-1].split("&")[0]
                bp = self.db.query(BusinessProfile).filter(BusinessProfile.google_maps_url.contains(f"cid={cid}")).first()
                if bp:
                    return bp
            elif "/place/" in norm_url and len(norm_url) > 35:
                bp = self.db.query(BusinessProfile).filter(BusinessProfile.google_maps_url.startswith(norm_url)).first()
                if bp:
                    return bp
            
        # Create new
        bp = BusinessProfile(
            business_name=name,
            google_maps_url=norm_url or source_url,
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
            
        pc = ProjectCompetitor(project_id=project_id, business_id=bp.id, is_active=True)
        self.db.add(pc)
        cand.status = "SELECTED"
        self.db.commit()
        return pc

    def bulk_select_candidates(self, project_id: str, candidate_ids: List[str]) -> List[ProjectCompetitor]:
        self._verify_project(project_id)
        results = []
        for cid in candidate_ids:
            try:
                comp = self.select_candidate(project_id, cid)
                results.append(comp)
            except Exception as e:
                logger.warning(f"Failed to select candidate {cid}: {e}")
        return results

    def bulk_reject_candidates(self, project_id: str, candidate_ids: List[str]) -> List[DiscoveryCandidate]:
        self._verify_project(project_id)
        results = []
        for cid in candidate_ids:
            try:
                cand = self.reject_candidate(project_id, cid)
                results.append(cand)
            except Exception as e:
                logger.warning(f"Failed to reject candidate {cid}: {e}")
        return results

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
