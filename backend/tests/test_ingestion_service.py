import pytest
import os
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor, ScrapeObservation
from app.models.post import Post, PostMedia
from app.scraper.schemas import NormalizedPost
from app.services.ingestion_service import IngestionService, MediaDownloader
from app.core.storage import LocalStorageProvider

class FakeMediaDownloader(MediaDownloader):
    async def download(self, url: str) -> bytes | None:
        if "fail" in url:
            return None
        return b"fake_media_content"

@pytest.fixture
def base_dir(tmp_path):
    return tmp_path / "media_storage"

@pytest.fixture
def storage(base_dir):
    return LocalStorageProvider(base_dir=str(base_dir))

@pytest.fixture
def downloader():
    return FakeMediaDownloader()

@pytest.fixture
def ingestion_service(db: Session, storage, downloader):
    return IngestionService(db, storage, downloader)

@pytest.fixture
def setup_data(db: Session):
    business = BusinessProfile(business_name="Test Business")
    project = Project(name="Test Project", own_business_id=business.id)
    db.add_all([business, project])
    db.commit()

    run = ScrapeRun(project_id=project.id)
    db.add(run)
    db.commit()

    run_comp = ScrapeRunCompetitor(scrape_run_id=run.id, business_id=business.id)
    db.add(run_comp)
    db.commit()

    return {
        "project_id": project.id,
        "business_id": business.id,
        "run_id": run.id,
        "run_comp_id": run_comp.id
    }

@pytest.mark.asyncio
async def test_first_ingestion(db: Session, ingestion_service, setup_data):
    post_data = NormalizedPost(
        source_id="post-1",
        fingerprint="fp-1",
        text_content="Hello"
    )
    
    res = await ingestion_service.ingest_post(
        setup_data["project_id"],
        setup_data["business_id"],
        setup_data["run_comp_id"],
        post_data
    )
    
    assert res.status == "NEW_POST"
    assert res.observation_created is True
    
    post = db.query(Post).filter_by(id=res.post_id).first()
    assert post is not None
    assert post.source_identifier == "post-1"
    
    obs = db.query(ScrapeObservation).filter_by(post_id=post.id).all()
    assert len(obs) == 1

@pytest.mark.asyncio
async def test_repeated_same_scrape_idempotent(db: Session, ingestion_service, setup_data):
    post_data = NormalizedPost(
        source_id="post-2",
        fingerprint="fp-2",
        text_content="World"
    )
    
    # First ingest
    res1 = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], setup_data["run_comp_id"], post_data
    )
    assert res1.status == "NEW_POST"
    assert res1.observation_created is True
    
    # Second ingest
    res2 = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], setup_data["run_comp_id"], post_data
    )
    assert res2.status == "EXISTING_POST"
    assert res2.observation_created is False
    assert res2.post_id == res1.post_id

@pytest.mark.asyncio
async def test_same_post_different_run(db: Session, ingestion_service, setup_data):
    post_data = NormalizedPost(
        source_id="post-3",
        fingerprint="fp-3",
        text_content="Foo"
    )
    
    res1 = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], setup_data["run_comp_id"], post_data
    )
    
    # New run
    run2 = ScrapeRun(project_id=setup_data["project_id"])
    db.add(run2)
    db.commit()
    run_comp2 = ScrapeRunCompetitor(scrape_run_id=run2.id, business_id=setup_data["business_id"])
    db.add(run_comp2)
    db.commit()

    res2 = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], run_comp2.id, post_data
    )
    
    assert res2.status == "EXISTING_POST"
    assert res2.observation_created is True
    assert res2.post_id == res1.post_id
    
    obs = db.query(ScrapeObservation).filter_by(post_id=res1.post_id).all()
    assert len(obs) == 2

@pytest.mark.asyncio
async def test_strong_identity_update(db: Session, ingestion_service, setup_data):
    # E. Strong source identity: Same source ID but changed content -> same Post.
    post_data1 = NormalizedPost(source_id="post-4", fingerprint="post-4", text_content="Old")
    res1 = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], setup_data["run_comp_id"], post_data1
    )
    
    post_data2 = NormalizedPost(source_id="post-4", fingerprint="post-4", text_content="New content")
    res2 = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], setup_data["run_comp_id"], post_data2
    )
    
    assert res2.status == "UPDATED_POST"
    assert res2.post_id == res1.post_id
    post = db.query(Post).filter_by(id=res1.post_id).first()
    assert post.text_content == "New content"

@pytest.mark.asyncio
async def test_fingerprint_fallback(db: Session, ingestion_service, setup_data):
    # G. Fingerprint fallback
    post_data = NormalizedPost(source_id=None, fingerprint="fallback-hash", text_content="Fallback")
    res1 = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], setup_data["run_comp_id"], post_data
    )
    
    # Same fingerprint, different text shouldn't happen natively, but if it does, it matches via fingerprint
    res2 = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], setup_data["run_comp_id"], post_data
    )
    assert res2.status == "EXISTING_POST"
    assert res2.post_id == res1.post_id

@pytest.mark.asyncio
async def test_media_success(db: Session, ingestion_service, setup_data, storage):
    post_data = NormalizedPost(
        source_id="post-media", fingerprint="fp-media", text_content="Media",
        media_urls=["http://example.com/ok.jpg"]
    )
    res = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], setup_data["run_comp_id"], post_data
    )
    
    assert res.media_saved == 1
    assert res.media_failed == 0
    media = db.query(PostMedia).filter_by(post_id=res.post_id).first()
    assert media.download_status == "SUCCESS"
    assert storage.exists(media.storage_key)

@pytest.mark.asyncio
async def test_media_failure(db: Session, ingestion_service, setup_data):
    # K. Media failure does not fail post
    post_data = NormalizedPost(
        source_id="post-fail", fingerprint="fp-fail", text_content="Fail",
        media_urls=["http://example.com/fail.jpg"]
    )
    res = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], setup_data["run_comp_id"], post_data
    )
    
    assert res.status == "NEW_POST"
    assert res.media_saved == 0
    assert res.media_failed == 1
    media = db.query(PostMedia).filter_by(post_id=res.post_id).first()
    assert media.download_status == "FAILED"

@pytest.mark.asyncio
async def test_media_duplicate(db: Session, ingestion_service, setup_data):
    # J. Media duplicate
    post_data = NormalizedPost(
        source_id="post-dup", fingerprint="fp-dup", text_content="Dup",
        media_urls=["http://example.com/ok.jpg"]
    )
    res1 = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], setup_data["run_comp_id"], post_data
    )
    
    res2 = await ingestion_service.ingest_post(
        setup_data["project_id"], setup_data["business_id"], setup_data["run_comp_id"], post_data
    )
    assert res2.media_saved == 0 # skipped because it already succeeded
    
    media_count = db.query(PostMedia).filter_by(post_id=res1.post_id).count()
    assert media_count == 1
