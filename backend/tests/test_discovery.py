import pytest
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.discovery import DiscoveryRun, DiscoveryCandidate
from app.models.competitor import ProjectCompetitor
from app.models.profile import BusinessProfile
from app.services.discovery_service import DiscoveryService, haversine_distance
from app.providers.discovery.fake import FakeDiscoveryProvider
from app.schemas.discovery import DiscoveryRunCreate, DirectCompetitorCreate, DiscoveryCandidateSchema

@pytest.fixture
def fake_provider():
    return FakeDiscoveryProvider()

@pytest.fixture
def discovery_service(db, fake_provider):
    return DiscoveryService(db, fake_provider)

def test_haversine_distance():
    # Test San Francisco to Los Angeles (approx 559 km)
    sf_lat, sf_lon = 37.7749, -122.4194
    la_lat, la_lon = 34.0522, -118.2437
    dist = haversine_distance(sf_lat, sf_lon, la_lat, la_lon)
    assert 500 < dist < 600

@pytest.mark.asyncio
async def test_discovery_run_lifecycle_and_deduplication(db: Session, discovery_service):
    p = Project(name="Test Proj")
    db.add(p)
    db.commit()

    run = discovery_service.create_discovery_run(p.id, DiscoveryRunCreate(query="cafes", radius=10))
    assert run.status == "QUEUED"
    
    await discovery_service.execute_discovery(run.id)
    
    db.refresh(run)
    assert run.status == "SUCCESS"
    assert run.total_candidates == 2
    
    candidates = discovery_service.get_candidates(p.id)
    assert len(candidates) == 2
    
    # Run again to test deduplication
    run2 = discovery_service.create_discovery_run(p.id, DiscoveryRunCreate(query="cafes", radius=10))
    await discovery_service.execute_discovery(run2.id)
    
    db.refresh(run2)
    assert run2.status == "SUCCESS"
    assert run2.total_candidates == 0
    assert run2.duplicates_skipped == 2

@pytest.mark.asyncio
async def test_candidate_selection_and_identity(db: Session, discovery_service):
    p = Project(name="Test Proj")
    db.add(p)
    db.commit()

    run = discovery_service.create_discovery_run(p.id, DiscoveryRunCreate(query="cafes"))
    await discovery_service.execute_discovery(run.id)
    
    cands = discovery_service.get_candidates(p.id)
    c1 = cands[0]
    
    # Select candidate
    comp = discovery_service.select_candidate(p.id, c1.id)
    assert comp is not None
    assert comp.business.canonical_source_id == c1.source_identifier
    
    # Verify candidate status updated
    db.refresh(c1)
    assert c1.status == "SELECTED"
    
    # Selecting again should just return the existing comp and update status to ALREADY_COMPETITOR
    comp2 = discovery_service.select_candidate(p.id, c1.id)
    assert comp2.id == comp.id
    db.refresh(c1)
    assert c1.status == "ALREADY_COMPETITOR"

def test_direct_competitor_addition(db: Session, discovery_service):
    p = Project(name="Test Proj")
    db.add(p)
    db.commit()
    
    comp1 = discovery_service.add_direct_competitor(p.id, DirectCompetitorCreate(
        business_name="Direct Biz",
        source_url="https://maps.google.com/direct"
    ))
    
    assert comp1 is not None
    assert comp1.business.business_name == "Direct Biz"
    
    # Add again with same URL to test profile reuse
    comp2 = discovery_service.add_direct_competitor(p.id, DirectCompetitorCreate(
        business_name="Direct Biz Changed Name",
        source_url="https://maps.google.com/direct"
    ))
    
    assert comp1.id == comp2.id
    assert db.query(BusinessProfile).count() == 1

@pytest.mark.asyncio
async def test_candidate_rejection(db: Session, discovery_service):
    p = Project(name="Test Proj")
    db.add(p)
    db.commit()

    run = discovery_service.create_discovery_run(p.id, DiscoveryRunCreate(query="cafes"))
    await discovery_service.execute_discovery(run.id)
    cands = discovery_service.get_candidates(p.id)
    c1 = cands[0]
    
    discovery_service.reject_candidate(p.id, c1.id)
    db.refresh(c1)
    assert c1.status == "REJECTED"

@pytest.mark.asyncio
async def test_discovery_provider_failure(db: Session):
    failing_provider = FakeDiscoveryProvider(should_fail=True)
    svc = DiscoveryService(db, failing_provider)
    
    p = Project(name="Test Proj")
    db.add(p)
    db.commit()

    run = svc.create_discovery_run(p.id, DiscoveryRunCreate(query="cafes"))
    await svc.execute_discovery(run.id)
    
    db.refresh(run)
    assert run.status == "FAILED"
    assert run.error_message == "Fake discovery provider failure"
    
    # Resume should flip to QUEUED (using Project ID now)
    resumed = svc.resume_discovery(p.id, run.id)
    assert resumed.status == "QUEUED"

@pytest.mark.asyncio
async def test_resume_discovery_ownership(db: Session, discovery_service):
    pA = Project(name="Project A")
    pB = Project(name="Project B")
    db.add_all([pA, pB])
    db.commit()

    runA = discovery_service.create_discovery_run(pA.id, DiscoveryRunCreate(query="cafes"))
    runA.status = "FAILED"
    db.commit()

    # Project B attempts to resume Run A -> rejected
    with pytest.raises(ValueError, match="Run cannot be resumed or does not belong to project"):
        discovery_service.resume_discovery(pB.id, runA.id)

    db.refresh(runA)
    assert runA.status == "FAILED" # state did not change

    # Project A attempts to resume Run A -> allowed
    resumed = discovery_service.resume_discovery(pA.id, runA.id)
    assert resumed.status == "QUEUED"

def test_resume_nonexistent_run(db: Session, discovery_service):
    p = Project(name="Project A")
    db.add(p)
    db.commit()

    with pytest.raises(ValueError, match="Run cannot be resumed or does not belong to project"):
        discovery_service.resume_discovery(p.id, "fake-run-id")

def test_resume_paused_manual_intervention(db: Session, discovery_service):
    p = Project(name="Project A")
    db.add(p)
    db.commit()

    run = discovery_service.create_discovery_run(p.id, DiscoveryRunCreate(query="cafes"))
    run.status = "PAUSED_MANUAL_INTERVENTION"
    db.commit()

    resumed = discovery_service.resume_discovery(p.id, run.id)
    assert resumed.status == "QUEUED"

