from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str
    REDIS_URL: str
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    
    # Scraper config
    SCRAPER_MAX_RETRIES: int = 3
    SCRAPER_DELAY_MIN: int = 2
    SCRAPER_DELAY_MAX: int = 5
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_MAX_CONCURRENT: int = 1
    SCRAPER_COOLDOWN: int = 60
    SCRAPER_HEADLESS: bool = True
    SCRAPER_PROFILE_DIR: str = "./.scraper_profiles"

    # AI Config
    AI_PROVIDER: str = "fake"
    GEMINI_API_KEY: str = ""
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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
