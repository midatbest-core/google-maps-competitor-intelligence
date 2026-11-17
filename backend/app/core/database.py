from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Engine configuration
from sqlalchemy.pool import StaticPool
engine_kwargs = {}
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
else:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    if ":memory:" in settings.DATABASE_URL:
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    **engine_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from urllib.parse import urlsplit

KNOWN_DEPLOYED_NEON_HOSTS = {
    "ep-autumn-breeze-bdn4qlsa-pooler.c-8.us-east-2.aws.neon.tech",
}

def is_deployed_neon_database(session_or_url=None) -> bool:
    """
    Checks if a database session, engine, or URL string targets the known deployed Neon database.
    Performs purely lexical URL host inspection without establishing any network connection or query.
    """
    hosts = set()
    if session_or_url is not None:
        if isinstance(session_or_url, str):
            parsed = urlsplit(session_or_url)
            if parsed.hostname:
                hosts.add(parsed.hostname.lower())
        else:
            try:
                bind = getattr(session_or_url, "bind", None)
                if not bind and hasattr(session_or_url, "get_bind"):
                    bind = session_or_url.get_bind()
                if bind and hasattr(bind, "url") and bind.url and bind.url.host:
                    hosts.add(bind.url.host.lower())
            except Exception:
                pass

    if not hosts and getattr(settings, "DATABASE_URL", None):
        try:
            parsed = urlsplit(settings.DATABASE_URL)
            if parsed.hostname:
                hosts.add(parsed.hostname.lower())
        except Exception:
            pass

    for host in hosts:
        if host in KNOWN_DEPLOYED_NEON_HOSTS or host.endswith(".neon.tech"):
            return True
    return False

def assert_ai_write_safety(provider_or_name, session=None):
    """
    Safety guard: Prevents FakeAIProvider or synthetic analysis providers from writing
    records when connected to the known deployed Neon database.
    """
    provider_name = ""
    if isinstance(provider_or_name, str):
        provider_name = provider_or_name.lower()
    elif provider_or_name is not None:
        provider_name = getattr(provider_or_name, "provider_name", "").lower()
        if not provider_name:
            provider_name = type(provider_or_name).__name__.lower()

    is_synthetic = provider_name in ("fake_provider", "fake", "fakeaiprovider")
    if is_synthetic and is_deployed_neon_database(session):
        raise RuntimeError(
            "Database Safety Guard: FakeAIProvider is strictly prohibited from writing synthetic "
            "records to the deployed Neon PostgreSQL database. Switch to a legitimate AI provider "
            "(e.g. Gemini) or connect to a local/in-memory test database."
        )
