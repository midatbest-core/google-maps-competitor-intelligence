from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


ROOT = Path(__file__).parents[2]


def _production_settings(**overrides):
    values = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://user:password@database.example/app",
        "REDIS_URL": "rediss://default:password@redis.example:6380/0",
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-gemini-key",
        "GOOGLE_PLACES_API_KEY": "test-places-key",
        "CORS_ORIGINS": ["https://frontend.example"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_settings_accept_postgres_rediss_and_https_cors():
    settings = _production_settings()

    assert settings.APP_ENV == "production"
    assert settings.GEMINI_MODEL == "gemini-3.5-flash-lite"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"DATABASE_URL": "sqlite:///local.db"}, "PostgreSQL"),
        ({"REDIS_URL": "https://redis.example"}, "redis:// or rediss://"),
        ({"CORS_ORIGINS": ["http://localhost:5173"]}, "deployed HTTPS"),
        ({"GEMINI_API_KEY": ""}, "GEMINI_API_KEY"),
        ({"GOOGLE_PLACES_API_KEY": None}, "GOOGLE_PLACES_API_KEY"),
    ],
)
def test_invalid_production_configuration_fails_fast(overrides, message):
    with pytest.raises(ValidationError, match=message):
        _production_settings(**overrides)


def test_docker_compose_uses_repository_context_for_backend_dockerfile():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert compose.count("context: .") == 2
    assert compose.count("dockerfile: backend/Dockerfile") == 2
    api_section, worker_section = compose.split("  worker:", maxsplit=1)
    assert api_section.count("alembic upgrade head") == 1
    assert "exec uvicorn app.main:app" in api_section
    assert "alembic upgrade head" not in worker_section
    assert compose.count("AI_PROVIDER=${AI_PROVIDER:-gemini}") == 2


def test_deployment_guide_documents_upstash_tls_url():
    guide = (ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")

    assert "Upstash must use its TLS rediss:// connection URL" in guide


def test_render_blueprint_defines_web_worker_and_environment_parity():
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "type: web" in blueprint
    assert "type: worker" in blueprint
    assert "healthCheckPath: /health" in blueprint
    assert "dockerContext: ." in blueprint
    assert "arq app.workers.main.WorkerSettings" in blueprint
    for variable in (
        "DATABASE_URL",
        "REDIS_URL",
        "AI_PROVIDER",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_TIMEOUT_SECONDS",
        "GOOGLE_PLACES_API_KEY",
        "GOOGLE_PLACES_TIMEOUT_SECONDS",
        "GOOGLE_PLACES_MAX_SEARCH_PAGES",
        "CORS_ORIGINS",
    ):
        assert f"key: {variable}" in blueprint
