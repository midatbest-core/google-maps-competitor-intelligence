from datetime import datetime, timezone
import logging
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)

async def startup(ctx):
    logger.info("Worker starting up...")

async def shutdown(ctx):
    logger.info("Worker shutting down...")

async def mock_scrape_job(ctx, run_id: str):
    logger.info(f"Starting mock scrape job for run {run_id}")
    
    # We use a context manager or explicit close for db
    db = SessionLocal()
    try:
        run = db.query(ScrapeRun).filter(ScrapeRun.id == run_id).first()
        if not run:
            logger.error(f"Run {run_id} not found")
            return
            
        run.status = "RUNNING"
        run.start_time = datetime.now(timezone.utc)
        db.commit()
        
        competitor_runs = db.query(ScrapeRunCompetitor).filter(ScrapeRunCompetitor.scrape_run_id == run_id).all()
        
        for c in competitor_runs:
            if c.status in ("SUCCESS", "NO_DATA"):
                continue

            c.status = "RUNNING"
            db.commit()
            
            # Deterministic mock based on business name
            business_name = c.business.business_name.lower()
            if "fail" in business_name or "error" in business_name:
                c.status = "FAILED"
                c.error_message = "Mocked network error"
            elif "verify" in business_name or "captcha" in business_name:
                c.status = "VERIFICATION_REQUIRED"
                c.error_message = "Mocked CAPTCHA hit"
            elif "no_data" in business_name:
                c.status = "SUCCESS"
                c.posts_discovered = 0
            else:
                c.status = "SUCCESS"
                c.posts_discovered = 5
                c.new_posts = 5
                
            db.commit()
            
        # Determine final status and counters
        run.competitors_succeeded = sum(1 for c in competitor_runs if c.status in ("SUCCESS", "NO_DATA"))
        run.competitors_failed = sum(1 for c in competitor_runs if c.status == "FAILED")
        
        final_status = "SUCCESS"
        if any(c.status == "VERIFICATION_REQUIRED" for c in competitor_runs):
            final_status = "PAUSED_MANUAL_INTERVENTION"
        elif any(c.status == "FAILED" for c in competitor_runs):
            if run.competitors_succeeded > 0:
                final_status = "PARTIAL_SUCCESS"
            else:
                final_status = "FAILED"
                
        run.status = final_status
        run.end_time = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Finished mock scrape job for run {run_id} with status {final_status}")
    except Exception as e:
        logger.exception("Error in worker job")
        db.rollback()
    finally:
        db.close()


def get_redis_settings():
    import urllib.parse
    parsed = urllib.parse.urlparse(settings.REDIS_URL)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    database = int(parsed.path.strip("/")) if parsed.path and parsed.path.strip("/") else 0
    password = parsed.password
    return RedisSettings(host=host, port=port, database=database, password=password)

class WorkerSettings:
    functions = [mock_scrape_job]
    redis_settings = get_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
