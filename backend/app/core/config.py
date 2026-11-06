from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str
    REDIS_URL: str
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    
    # Storage
    LOCAL_STORAGE_DIR: str = "./data"

    # Scraper config
    SCRAPER_MAX_RETRIES: int = 3
    SCRAPER_DELAY_MIN: int = 2
    SCRAPER_DELAY_MAX: int = 5
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_MAX_CONCURRENT: int = 1
    SCRAPER_COOLDOWN: int = 60
    SCRAPER_HEADLESS: bool = True
    SCRAPER_PROFILE_DIR: str = "./.scraper_profiles"
    QUEUE_STALE_TIMEOUT_SECONDS: int = 60

    # AI Config
    AI_PROVIDER: str = "fake"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_TIMEOUT_SECONDS: float = 30.0
    GOOGLE_PLACES_API_KEY: str | None = None
    GOOGLE_PLACES_TIMEOUT_SECONDS: float = 20.0
    GOOGLE_PLACES_MAX_SEARCH_PAGES: int = 3
    DISCOVERY_PROVIDER: str = "google_places"
    OPENAI_API_KEY: str = ""
    EMBEDDING_PROVIDER: str = "fake"

    # Generation Config
    CONTENT_SIMILARITY_THRESHOLD: float = 0.90
    GENERATION_MAX_TOPICS: int = 10
    GENERATION_MAX_KEYWORDS: int = 20
    GENERATION_MAX_COMPETITOR_EXAMPLES: int = 5
    GENERATION_MAX_PROJECT_EXAMPLES: int = 5
    GENERATION_MAX_GAPS: int = 10
    GENERATION_MAX_GENERATED_HISTORY: int = 5

    @model_validator(mode="after")
    def validate_production_configuration(self):
        if self.APP_ENV.lower() != "production":
            return self

        database_scheme = urlsplit(self.DATABASE_URL).scheme
        if database_scheme not in {"postgresql", "postgresql+psycopg"}:
            raise ValueError("Production DATABASE_URL must use PostgreSQL")

        if urlsplit(self.REDIS_URL).scheme not in {"redis", "rediss"}:
            raise ValueError("Production REDIS_URL must use redis:// or rediss://")

        if self.AI_PROVIDER == "gemini" and not self.GEMINI_API_KEY.strip():
            raise ValueError("GEMINI_API_KEY is required when AI_PROVIDER=gemini")
        if not (self.GOOGLE_PLACES_API_KEY or "").strip():
            raise ValueError("GOOGLE_PLACES_API_KEY is required in production")

        if not self.CORS_ORIGINS or any(
            "localhost" in origin or "127.0.0.1" in origin
            for origin in self.CORS_ORIGINS
        ):
            raise ValueError(
                "Production CORS_ORIGINS must contain deployed HTTPS origins"
            )
        if any(not origin.startswith("https://") for origin in self.CORS_ORIGINS):
            raise ValueError("Production CORS_ORIGINS must use HTTPS")
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
