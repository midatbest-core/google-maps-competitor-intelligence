from fastapi.testclient import TestClient
import pytest
import re

from app.api.dependencies import get_current_user, get_current_workspace
from app.core.database import engine
from app.main import app
from app.models.base import Base


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_auth_app():
    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_workspace, None)
    Base.metadata.create_all(bind=engine)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved_overrides)
    Base.metadata.drop_all(bind=engine)


def test_register_login_and_current_user_flow():
    credentials = {
        "email": "release-test@example.com",
        "password": "safe-test-password",
        "full_name": "Release Test",
    }

    register = client.post("/auth/register", json=credentials)
    assert register.status_code == 200
    assert register.json()["workspace_id"]

    login = client.post(
        "/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == credentials["email"]
    assert me.json()["workspace_id"] == register.json()["workspace_id"]


def test_auth_rejects_bad_credentials_and_short_passwords():
    short = client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )
    assert short.status_code == 422

    invalid = client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )
    assert invalid.status_code == 401


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/projects"),
        ("post", "/projects/example/scrape"),
        ("get", "/projects/example/review-intelligence"),
        ("get", "/projects/example/content"),
        ("get", "/projects/example/discovery-runs"),
        ("get", "/scrape-runs/example"),
    ],
)
def test_representative_protected_endpoints_require_authentication(method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401


def test_every_non_public_api_operation_requires_authentication():
    public_operations = {
        ("GET", "/"),
        ("GET", "/health"),
        ("GET", "/ready"),
        ("POST", "/auth/register"),
        ("POST", "/auth/login"),
        ("POST", "/auth/logout"),
        ("GET", "/openapi.json"),
        ("GET", "/docs"),
        ("GET", "/docs/oauth2-redirect"),
        ("GET", "/redoc"),
    }

    checked = []
    for route_path, operations in app.openapi()["paths"].items():
        path = re.sub(r"\{[^}]+\}", "missing", route_path)
        for method_name in operations:
            method = method_name.upper()
            if method in {"HEAD", "OPTIONS"} or (method, route_path) in public_operations:
                continue
            response = client.request(method, path, json={})
            assert response.status_code == 401, (
                f"{method} {route_path} returned {response.status_code} without auth"
            )
            checked.append((method, route_path))

    assert len(checked) >= 30
