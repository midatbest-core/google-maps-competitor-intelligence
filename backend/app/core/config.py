from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str
    REDIS_URL: str
    
    # Scraper config
    SCRAPER_MAX_RETRIES: int = 3
    SCRAPER_DELAY_MIN: int = 2
    SCRAPER_DELAY_MAX: int = 5
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_MAX_CONCURRENT: int = 1
    SCRAPER_COOLDOWN: int = 60
    SCRAPER_HEADLESS: bool = True
    SCRAPER_PROFILE_DIR: str = "./.scraper_profiles"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
