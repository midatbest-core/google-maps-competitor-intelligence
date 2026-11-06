import importlib
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app
from app.models import Base, ReviewIntelligence


def _load_review_migration():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "f4c2a8d91e73_add_review_intelligence.py"
    )
    spec = importlib.util.spec_from_file_location("review_intelligence_migration", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_reconciliation_migration():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "b8a91d6f3c42_reconcile_legacy_schema.py"
    )
    spec = importlib.util.spec_from_file_location("reconciliation_migration", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_representative_legacy_schema(metadata, migration):
    for table_name in migration.LEGACY_TIMESTAMP_TABLES:
        columns = [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        ]
        if table_name == "ai_analyses":
            columns.insert(1, sa.Column("post_id", sa.String(), nullable=False))
        sa.Table(table_name, metadata, *columns)


def _assert_all_legacy_timestamps_nullable(connection, migration, expected):
    inspector = sa.inspect(connection)
    for table_name in migration.LEGACY_TIMESTAMP_TABLES:
        columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        assert columns["created_at"]["nullable"] is expected
        assert columns["updated_at"]["nullable"] is expected


def test_review_intelligence_registered_in_metadata():
    table = Base.metadata.tables[ReviewIntelligence.__tablename__]

    assert table.name == "review_intelligence"
    assert {fk.target_fullname for fk in table.foreign_keys} == {
        "business_profiles.id",
        "projects.id",
    }
    assert {index.name for index in table.indexes} == {
        "ix_review_intelligence_business_id",
        "ix_review_intelligence_project_id",
    }


def test_review_intelligence_migration_upgrade_and_downgrade(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table("business_profiles", metadata, sa.Column("id", sa.String(), primary_key=True))
    sa.Table("projects", metadata, sa.Column("id", sa.String(), primary_key=True))
    metadata.create_all(engine)

    migration = _load_review_migration()
    assert migration.down_revision == "2521849cc98a"

    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)

        migration.upgrade()
        inspector = sa.inspect(connection)
        assert "review_intelligence" in inspector.get_table_names()
        assert {column["name"] for column in inspector.get_columns("review_intelligence")} == {
            "analysis_provider",
            "analyzed_at",
            "average_rating",
            "business_id",
            "business_opportunities",
            "complaint_themes",
            "created_at",
            "customer_needs",
            "frequently_mentioned_services",
            "id",
            "model_version",
            "negative_percentage",
            "neutral_percentage",
            "overall_sentiment",
            "pain_points",
            "positive_percentage",
            "praise_themes",
            "project_id",
            "recommended_actions",
            "reviews_analyzed_count",
            "strengths",
            "updated_at",
            "weaknesses",
        }
        assert {index["name"] for index in inspector.get_indexes("review_intelligence")} == {
            "ix_review_intelligence_business_id",
            "ix_review_intelligence_project_id",
        }
        assert {
            constrained
            for foreign_key in inspector.get_foreign_keys("review_intelligence")
            for constrained in foreign_key["constrained_columns"]
        } == {"business_id", "project_id"}

        migration.downgrade()
        assert "review_intelligence" not in sa.inspect(connection).get_table_names()


def test_reconciliation_migration_upgrade_and_downgrade(monkeypatch):
    migration = _load_reconciliation_migration()
    assert migration.down_revision == "f4c2a8d91e73"

    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    _create_representative_legacy_schema(metadata, migration)
    metadata.create_all(engine)

    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        for table_name in migration.LEGACY_TIMESTAMP_TABLES:
            values = {"id": 1, "created_at": now, "updated_at": now}
            if table_name == "ai_analyses":
                values["post_id"] = "post-1"
            connection.execute(metadata.tables[table_name].insert().values(**values))

        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)

        migration.upgrade()

        _assert_all_legacy_timestamps_nullable(connection, migration, expected=False)
        indexes = {
            index["name"]: index for index in sa.inspect(connection).get_indexes("ai_analyses")
        }
        assert indexes["ix_ai_analyses_post_id"]["column_names"] == ["post_id"]
        assert not indexes["ix_ai_analyses_post_id"]["unique"]

        migration.downgrade()

        _assert_all_legacy_timestamps_nullable(connection, migration, expected=True)
        assert "ix_ai_analyses_post_id" not in {
            index["name"] for index in sa.inspect(connection).get_indexes("ai_analyses")
        }


def test_reconciliation_migration_rejects_null_timestamps(monkeypatch):
    migration = _load_reconciliation_migration()

    assert migration.down_revision == "f4c2a8d91e73"

    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    _create_representative_legacy_schema(metadata, migration)
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            metadata.tables["business_profiles"].insert().values(
                id=1,
                created_at=None,
                updated_at=None,
            )
        )
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)

        with pytest.raises(RuntimeError, match=r"business_profiles \(1 rows\)"):
            migration.upgrade()

        _assert_all_legacy_timestamps_nullable(connection, migration, expected=True)
        assert "ix_ai_analyses_post_id" not in {
            index["name"] for index in sa.inspect(connection).get_indexes("ai_analyses")
        }


def test_google_places_api_key_loads_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-places-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    settings = Settings(_env_file=None)

    assert settings.GOOGLE_PLACES_API_KEY == "test-places-key"
    assert settings.GEMINI_API_KEY == "test-gemini-key"


def test_google_places_api_key_is_optional(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.GOOGLE_PLACES_API_KEY is None


def test_database_url_remains_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None)


def test_application_imports():
    module = importlib.import_module("app.main")

    assert module.app is app


def test_health_endpoint():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_docker_startup_uses_migrations_and_render_port():
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(encoding="utf-8")
    command = dockerfile.split("CMD", maxsplit=1)[1]

    assert command.index("alembic upgrade head") < command.index("uvicorn app.main:app")
    assert "--host 0.0.0.0" in command
    assert "--port ${PORT:-8000}" in command
    assert "playwright install chromium" in dockerfile
    assert "playwright install-deps chromium" in dockerfile
