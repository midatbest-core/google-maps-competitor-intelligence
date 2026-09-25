import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.models.competitor import ProjectCompetitor
from app.models.post import Post, PostMedia
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor, ScrapeObservation
from app.models.analysis import AIAnalysis, GeneratedContent

def test_project_and_business_creation(db: Session):
    business = BusinessProfile(business_name="Main Business")
    db.add(business)
    db.commit()

    project = Project(name="Project A", own_business_id=business.id)
    db.add(project)
    db.commit()

    assert project.id is not None
    assert project.own_business.business_name == "Main Business"

def test_business_reused_across_projects(db: Session):
    business = BusinessProfile(business_name="Shared Competitor")
    db.add(business)
    db.commit()

    p1 = Project(name="Project 1")
    p2 = Project(name="Project 2")
    db.add_all([p1, p2])
    db.commit()

    comp1 = ProjectCompetitor(project_id=p1.id, business_id=business.id)
    comp2 = ProjectCompetitor(project_id=p2.id, business_id=business.id)
    db.add_all([comp1, comp2])
    db.commit()

    assert comp1.business_id == comp2.business_id

def test_duplicate_competitor_membership(db: Session):
    business = BusinessProfile(business_name="Competitor")
    project = Project(name="Project")
    db.add_all([business, project])
    db.commit()

    comp1 = ProjectCompetitor(project_id=project.id, business_id=business.id)
    db.add(comp1)
    db.commit()

    comp2 = ProjectCompetitor(project_id=project.id, business_id=business.id)
    db.add(comp2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_post_creation_and_duplicate_prevention(db: Session):
    business = BusinessProfile(business_name="Business")
    db.add(business)
    db.commit()

    post1 = Post(business_id=business.id, fingerprint="fp123")
    db.add(post1)
    db.commit()

    assert post1.id is not None

    post2 = Post(business_id=business.id, fingerprint="fp123")
    db.add(post2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_post_media_and_cascade(db: Session):
    business = BusinessProfile(business_name="Business")
    db.add(business)
    db.commit()

    post = Post(business_id=business.id, fingerprint="fp-media")
    db.add(post)
    db.commit()

    media = PostMedia(post_id=post.id, storage_key="key123")
    db.add(media)
    db.commit()

    assert media.id is not None

    # Test cascade
    db.delete(post)
    db.commit()

    assert db.query(PostMedia).filter_by(id=media.id).first() is None

def test_scrape_run_and_observation(db: Session):
    business = BusinessProfile(business_name="Business")
    project = Project(name="Project")
    db.add_all([business, project])
    db.commit()

    run = ScrapeRun(project_id=project.id)
    db.add(run)
    db.commit()

    run_comp = ScrapeRunCompetitor(scrape_run_id=run.id, business_id=business.id)
    db.add(run_comp)
    db.commit()

    post = Post(business_id=business.id, fingerprint="fp-obs")
    db.add(post)
    db.commit()

    obs = ScrapeObservation(scrape_run_competitor_id=run_comp.id, post_id=post.id, is_new=True)
    db.add(obs)
    db.commit()

    assert obs.id is not None

def test_ai_analysis_and_generated_content(db: Session):
    business = BusinessProfile(business_name="Business")
    project = Project(name="Project")
    db.add_all([business, project])
    db.commit()

    post = Post(business_id=business.id, fingerprint="fp-ai")
    db.add(post)
    db.commit()

    analysis = AIAnalysis(post_id=post.id, provider="gemini", model_name="gemini-1.5")
    db.add(analysis)
    db.commit()
    assert analysis.id is not None

    gen = GeneratedContent(project_id=project.id, topic="Test", generated_idea="Idea", provider="gemini", model_name="gemini-1.5", fingerprint="fp-gen")
    db.add(gen)
    db.commit()
    assert gen.id is not None
