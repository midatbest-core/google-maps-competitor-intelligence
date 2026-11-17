import pytest
from unittest.mock import patch
from uuid import uuid4
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.models.auth import User, Workspace, WorkspaceMember
from app.models.project import Project
from app.models.competitor import ProjectCompetitor
from app.models.profile import BusinessProfile
from app.models.post import Post
from app.models.analysis import AIAnalysis
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor
from app.repositories.project_repo import ProjectRepository
from app.services.analytics_service import AnalyticsService, is_synthetic_keyword, SYNTHETIC_EXCLUDED_KEYWORDS
from app.workers.main import PER_BUSINESS_TIMEOUT, WorkerSettings

client = TestClient(app)


def test_timeout_configurations():
    """Verify that per-business timeout defaults to 120s and ARQ job timeout to 7200s."""
    assert settings.SCRAPER_PER_BUSINESS_TIMEOUT == 120.0
    assert PER_BUSINESS_TIMEOUT == 120.0
    assert WorkerSettings.job_timeout >= 7200

    # Verify exact error message string matches 120s
    from app.scraper.schemas import ScrapeResult
    timeout_result = ScrapeResult(status="ERROR", error_message=f"Timeout: Exceeded {int(PER_BUSINESS_TIMEOUT)}s processing business")
    assert timeout_result.error_message == "Timeout: Exceeded 120s processing business"


def test_scrape_run_progress_and_eta_calculations(db):
    """Verify progress counters, sequence index, and estimated remaining time formulas."""
    ws = Workspace(id=str(uuid4()), name="ETA WS")
    project = Project(id=str(uuid4()), name="ETA Proj", workspace_id=ws.id)
    db.add_all([ws, project])
    db.commit()

    run = ScrapeRun(
        id=str(uuid4()),
        project_id=project.id,
        status="RUNNING",
        competitors_attempted=40,
        competitors_succeeded=10,
        competitors_failed=2,
    )
    db.add(run)
    db.commit()

    # Create 40 competitors: 10 SUCCESS, 2 FAILED, 1 RUNNING, 27 PENDING
    for i in range(1, 41):
        biz = BusinessProfile(id=str(uuid4()), business_name=f"Coffee Biz {i}")
        db.add(biz)
        db.flush()

        comp_status = "PENDING"
        if i <= 10:
            comp_status = "SUCCESS"
        elif i <= 12:
            comp_status = "FAILED"
        elif i == 13:
            comp_status = "RUNNING"

        cr = ScrapeRunCompetitor(
            id=str(uuid4()),
            scrape_run_id=run.id,
            business_id=biz.id,
            status=comp_status,
        )
        db.add(cr)
    db.commit()
    db.refresh(run)

    # 40 total, 12 completed, 28 remaining
    assert run.total_competitors == 40
    assert run.competitors_completed == 12
    assert run.competitors_remaining == 28
    assert run.currently_processing_index == 13
    assert run.currently_processing_name == "Coffee Biz 13"
    # Remaining * 60 seconds = 28 * 60 = 1680s
    assert run.estimated_remaining_seconds == 1680
    assert run.estimated_remaining_formatted == "~28 minutes remaining"

    # Terminal state calculations
    run.status = "SUCCESS"
    assert run.estimated_remaining_seconds == 0
    assert run.estimated_remaining_formatted == "Completed"

    run.status = "FAILED"
    assert run.estimated_remaining_seconds == 0
    assert run.estimated_remaining_formatted == "FAILED"


def test_estimated_remaining_time_under_sixty_seconds(db):
    """Verify that when remaining time is under 60 seconds or zero, display formats correctly."""
    run = ScrapeRun(
        id=str(uuid4()),
        project_id="proj-test",
        status="RUNNING",
        competitors_attempted=1,
        competitors_succeeded=1,
        competitors_failed=0,
    )
    assert run.competitors_remaining == 0
    assert run.estimated_remaining_formatted == "Completing..."


def test_deterministic_competitor_roster_ordering(db):
    """Verify that ProjectRepository.get_competitors returns deterministic sequential ordering (1..N)."""
    ws = Workspace(id=str(uuid4()), name="Order WS")
    project = Project(id=str(uuid4()), name="Order Proj", workspace_id=ws.id)
    db.add_all([ws, project])
    db.commit()

    repo = ProjectRepository(db)
    biz_names = ["Zeta Roasters", "Alpha Cafe", "Beta Beans", "Gamma Coffee"]
    for name in biz_names:
        biz = BusinessProfile(id=str(uuid4()), business_name=name)
        db.add(biz)
        db.flush()
        repo.add_competitor(project.id, biz.id)

    competitors = repo.get_competitors(project.id)
    assert len(competitors) == 4
    # Deterministic created_at order preserves insertion sequence (1..N)
    assert [c.business.business_name for c in competitors] == biz_names


def test_synthetic_keyword_filtering_in_analytics(db):
    """Verify that synthetic keywords ('fake', 'test', etc.) are excluded from analytics and gaps."""
    ws = Workspace(id=str(uuid4()), name="Clean WS")
    project = Project(id=str(uuid4()), name="Clean Proj", workspace_id=ws.id)
    db.add_all([ws, project])
    db.commit()

    own_biz = BusinessProfile(id=str(uuid4()), business_name="Own Roastery")
    comp_biz = BusinessProfile(id=str(uuid4()), business_name="Competitor Roastery")
    db.add_all([own_biz, comp_biz])
    db.commit()

    project.own_business_id = own_biz.id
    db.add(ProjectCompetitor(project_id=project.id, business_id=comp_biz.id, is_active=True))
    db.commit()

    # Add posts with synthetic keywords and legitimate domain keywords
    post1 = Post(id=str(uuid4()), business_id=comp_biz.id, fingerprint="fp1", text_content="Artisanal pour over")
    post2 = Post(id=str(uuid4()), business_id=comp_biz.id, fingerprint="fp2", text_content="Cold brew special")
    db.add_all([post1, post2])
    db.commit()

    # Contaminated with 'fake', 'test', 'dummy'
    a1 = AIAnalysis(
        post_id=post1.id,
        topic="Pour Over",
        keywords=["fake", "test", "pour over", "single origin"],
        provider="fake_provider",
        model_name="fake_model"
    )
    a2 = AIAnalysis(
        post_id=post2.id,
        topic="Cold Brew",
        keywords=["test", "cold brew", "summer drink", "dummy"],
        provider="fake_provider",
        model_name="fake_model"
    )
    db.add_all([a1, a2])
    db.commit()

    analytics = AnalyticsService(db, workspace=ws)

    # 1. Keyword frequency
    kws = analytics.get_keyword_frequency(project.id)
    kw_names = [k["keyword"] for k in kws]
    assert "fake" not in kw_names
    assert "test" not in kw_names
    assert "dummy" not in kw_names
    assert "pour over" in kw_names
    assert "cold brew" in kw_names

    # 2. Content gaps
    gaps = analytics.get_content_gaps(project.id)
    assert "fake" not in gaps["keyword_gaps"]
    assert "test" not in gaps["keyword_gaps"]
    assert "dummy" not in gaps["keyword_gaps"]
    assert "pour over" in gaps["keyword_gaps"]

    # 3. Detailed keyword gaps
    detailed_gaps = analytics.get_detailed_keyword_gaps(project.id)
    gap_kws = [g["keyword"] for g in detailed_gaps]
    assert "fake" not in gap_kws
    assert "test" not in gap_kws
    assert "dummy" not in gap_kws


def test_demo_login_disabled_by_default():
    """Verify that demo login is disabled by default and rejects demo login requests with 403."""
    with patch.object(settings, "ENABLE_DEMO_LOGIN", False), \
         patch.object(settings, "DEMO_ADMIN_PASSWORD", None):
        status_res = client.get("/auth/demo-status")
        assert status_res.status_code == 200
        assert status_res.json() == {"enabled": False, "email": None}

        login_res = client.post("/auth/demo-login")
        assert login_res.status_code == 403
        assert "disabled" in login_res.json()["detail"].lower()


def test_demo_login_missing_credentials_refuses_start_and_endpoint():
    """Verify that missing credentials cause Settings validation to fail and endpoint to refuse safely."""
    from app.core.config import Settings
    from pydantic import ValidationError

    # 1. Config refuses to start if ENABLE_DEMO_LOGIN=True without DEMO_ADMIN_PASSWORD
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DATABASE_URL="sqlite:///test.db",
            REDIS_URL="redis://localhost:6379",
            ENABLE_DEMO_LOGIN=True,
            DEMO_ADMIN_PASSWORD=None,
        )
    assert "DEMO_ADMIN_PASSWORD must be provided" in str(exc_info.value)

    # 2. Endpoint safely returns 503 if password was somehow empty at runtime
    with patch.object(settings, "ENABLE_DEMO_LOGIN", True), \
         patch.object(settings, "DEMO_ADMIN_PASSWORD", None):
        status_res = client.get("/auth/demo-status")
        assert status_res.status_code == 200
        assert status_res.json()["enabled"] is False

        login_res = client.post("/auth/demo-login")
        assert login_res.status_code == 503
        assert "missing" in login_res.json()["detail"].lower()


def test_demo_login_password_strength_validation():
    """Verify that DEMO_ADMIN_PASSWORD enforces complexity requirements when demo login is enabled."""
    from app.core.config import Settings
    from pydantic import ValidationError

    # Weak passwords should be rejected
    weak_passwords = [
        "short",                   # < 12 chars
        "onlylowercaseletters123", # no uppercase
        "ALLUPPERCASE123456!",    # no lowercase
        "NoDigitsOrSpecialLetters",# no digits or special
    ]

    for weak_pw in weak_passwords:
        with pytest.raises(ValidationError) as exc:
            Settings(
                DATABASE_URL="sqlite:///test.db",
                REDIS_URL="redis://localhost:6379",
                ENABLE_DEMO_LOGIN=True,
                DEMO_ADMIN_PASSWORD=weak_pw,
            )
        assert "DEMO_ADMIN_PASSWORD must be at least 12 characters" in str(exc.value)

    # Strong password accepted
    valid_settings = Settings(
        DATABASE_URL="sqlite:///test.db",
        REDIS_URL="redis://localhost:6379",
        ENABLE_DEMO_LOGIN=True,
        DEMO_ADMIN_PASSWORD="DemoSecure2026!Key",
    )
    assert valid_settings.DEMO_ADMIN_PASSWORD == "DemoSecure2026!Key"


def test_demo_login_authorized_and_workspace_isolated(db):
    """Verify authorized demo login returns token, preserves genuine memberships, and isolates workspaces."""
    from app.core.database import get_db
    from app.api.dependencies import get_current_user, get_current_workspace
    orig_user_override = app.dependency_overrides.pop(get_current_user, None)
    orig_ws_override = app.dependency_overrides.pop(get_current_workspace, None)
    app.dependency_overrides[get_db] = lambda: db

    test_demo_password = "EnvSuppliedSecurePassword999!"

    # Create a genuine client user and workspace first
    genuine_user = User(id=str(uuid4()), email="genuine.client@example.com", hashed_password="pw")
    genuine_ws = Workspace(id=str(uuid4()), name="Client Confidential Workspace")
    db.add_all([genuine_user, genuine_ws])
    db.commit()
    genuine_member = WorkspaceMember(workspace_id=genuine_ws.id, user_id=genuine_user.id, role="OWNER")
    db.add(genuine_member)
    db.commit()

    try:
        with patch.object(settings, "ENABLE_DEMO_LOGIN", True), \
             patch.object(settings, "DEMO_ADMIN_PASSWORD", test_demo_password):
            status_res = client.get("/auth/demo-status")
            assert status_res.status_code == 200
            assert status_res.json()["enabled"] is True
            assert status_res.json()["email"] == settings.DEMO_ADMIN_EMAIL
            # Never return credentials in status
            assert "password" not in status_res.text

            login_res = client.post("/auth/demo-login")
            assert login_res.status_code == 200
            body = login_res.json()
            token = body["access_token"]
            assert token is not None
            # Never leak password or secrets in login response
            assert "password" not in body
            assert test_demo_password not in login_res.text

            # Verify token authenticates /auth/me
            me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me_res.status_code == 200
            me_data = me_res.json()
            assert me_data["email"] == settings.DEMO_ADMIN_EMAIL
            assert me_data["workspace_id"] is not None

            # Verify isolated demo workspace exists
            demo_ws = db.query(Workspace).filter(Workspace.id == me_data["workspace_id"]).first()
            assert demo_ws is not None
            assert "demo" in demo_ws.name.lower()

            # Ensure genuine user's workspace and membership were completely untouched
            genuine_check = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == genuine_user.id).first()
            assert genuine_check is not None
            assert genuine_check.workspace_id == genuine_ws.id

            # Ensure demo user cannot access genuine client workspace
            demo_memberships = db.query(WorkspaceMember).filter(WorkspaceMember.user_id == me_data["id"]).all()
            ws_ids = {m.workspace_id for m in demo_memberships}
            assert genuine_ws.id not in ws_ids
    finally:
        app.dependency_overrides.pop(get_db, None)
        if orig_user_override:
            app.dependency_overrides[get_current_user] = orig_user_override
        if orig_ws_override:
            app.dependency_overrides[get_current_workspace] = orig_ws_override


def test_database_safety_guard_blocks_synthetic_neon_writes(db):
    """Verify that FakeAIProvider is strictly blocked from writing to deployed Neon PostgreSQL database."""
    from app.core.database import assert_ai_write_safety, is_deployed_neon_database
    from app.providers.ai.fake import FakeAIProvider
    from app.providers.embedding.fake import FakeEmbeddingProvider
    from app.services.analysis_service import AnalysisService
    from app.repositories.analysis_repo import AnalysisRepository

    neon_url = "postgresql://user:pass@ep-autumn-breeze-bdn4qlsa-pooler.c-8.us-east-2.aws.neon.tech/neondb"
    assert is_deployed_neon_database(neon_url) is True

    fake_ai = FakeAIProvider()

    # 1. Direct assertion guard check
    with pytest.raises(RuntimeError) as exc_info:
        assert_ai_write_safety(fake_ai, session=neon_url)
    assert "Database Safety Guard" in str(exc_info.value)
    assert "Neon PostgreSQL database" in str(exc_info.value)

    # 2. Guard in AnalysisService.analyze_post
    class MockNeonBind:
        class URL:
            host = "ep-autumn-breeze-bdn4qlsa-pooler.c-8.us-east-2.aws.neon.tech"
        url = URL()

    class MockNeonSession:
        bind = MockNeonBind()
        def get_bind(self): return self.bind
        def query(self, *args, **kwargs): raise AssertionError("No query should run when guard fails!")

    neon_session = MockNeonSession()
    service = AnalysisService(neon_session, fake_ai, FakeEmbeddingProvider())

    with pytest.raises(RuntimeError) as exc_service:
        import asyncio
        asyncio.run(service.analyze_post("any-post-id"))
    assert "Database Safety Guard" in str(exc_service.value)

    # 3. Guard in AnalysisRepository.create_analysis
    repo = AnalysisRepository(neon_session)
    mock_analysis = AIAnalysis(
        post_id="p1",
        provider="fake_provider",
        model_name="fake_model",
        analysis_version="v1"
    )
    with pytest.raises(RuntimeError) as exc_repo:
        repo.create_analysis(mock_analysis)
    assert "Database Safety Guard" in str(exc_repo.value)


def test_database_safety_guard_allows_safe_contexts(db):
    """Verify that the safety guard allows production AI providers on Neon and FakeAIProvider on local/test DBs."""
    from app.core.database import assert_ai_write_safety, is_deployed_neon_database
    from app.providers.ai.fake import FakeAIProvider

    neon_url = "postgresql://user:pass@ep-autumn-breeze-bdn4qlsa-pooler.c-8.us-east-2.aws.neon.tech/neondb"
    local_url = "postgresql://postgres:postgres@localhost:5432/mapsintel"
    sqlite_url = "sqlite:///:memory:"

    assert is_deployed_neon_database(local_url) is False
    assert is_deployed_neon_database(sqlite_url) is False

    # 1. Allowed: Real AI Provider (e.g. Gemini) against deployed Neon database
    class MockGeminiProvider:
        provider_name = "gemini"
        model_name = "gemini-3.5-flash-lite"

    assert_ai_write_safety(MockGeminiProvider(), session=neon_url)

    # 2. Allowed: FakeAIProvider against local PostgreSQL
    assert_ai_write_safety(FakeAIProvider(), session=local_url)

    # 3. Allowed: FakeAIProvider against SQLite in-memory test database
    assert_ai_write_safety(FakeAIProvider(), session=sqlite_url)
    assert_ai_write_safety(FakeAIProvider(), session=db)
