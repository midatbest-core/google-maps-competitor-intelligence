import pytest
from datetime import timedelta
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.dependencies import get_current_user
from app.models.auth import User, Workspace
from app.models.project import Project
from app.models.profile import BusinessProfile
from app.providers.ai.fake import FakeAIProvider
from app.services.review_service import ReviewService
from app.core.security import SecuritySettings, create_access_token


def test_missing_token_is_unauthorized_and_creates_no_anonymous_owner(db):
    before = db.query(User).filter_by(email="anonymous@local").count()

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(None, db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}
    assert db.query(User).filter_by(email="anonymous@local").count() == before


def test_invalid_token_is_unauthorized(db):
    with pytest.raises(HTTPException) as exc_info:
        get_current_user("not-a-valid-token", db)

    assert exc_info.value.status_code == 401


def test_expired_token_is_unauthorized(db):
    token = create_access_token("missing-user", expires_delta=timedelta(minutes=-1))

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token, db)

    assert exc_info.value.status_code == 401


def test_security_algorithm_cannot_enable_vulnerable_asymmetric_path():
    with pytest.raises(ValidationError):
        SecuritySettings(_env_file=None, ALGORITHM="RS256")


@pytest.mark.asyncio
async def test_review_analysis_rejects_project_from_another_workspace(db):
    owner_workspace = Workspace(name="Owner Workspace")
    foreign_workspace = Workspace(name="Foreign Workspace")
    business = BusinessProfile(business_name="Private Business")
    project = Project(
        name="Private Project",
        workspace=owner_workspace,
        own_business=business,
    )
    db.add_all([project, foreign_workspace])
    db.commit()

    service = ReviewService(
        db,
        FakeAIProvider(),
        workspace=foreign_workspace,
    )

    with pytest.raises(ValueError, match="Project not found"):
        await service.analyze_project_reviews(project.id)
