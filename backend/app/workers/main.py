from datetime import datetime, timezone
import logging
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor, ScrapeObservation
from app.models.post import Post
from app.scraper.google_maps.adapter import GoogleMapsAdapter
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)

async def startup(ctx):
    logger.info("Worker starting up...")
    ctx['scraper_adapter'] = GoogleMapsAdapter()

async def shutdown(ctx):
    logger.info("Worker shutting down...")
    adapter = ctx.get('scraper_adapter')
    if adapter:
        await adapter.close()

async def scrape_job(ctx, run_id: str):
    logger.info(f"Starting scrape job for run {run_id}")

    # Allow adapter to be mocked or retrieved from context
    adapter = ctx.get('scraper_adapter') if ctx else None
    if not adapter:
        adapter = GoogleMapsAdapter()

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

            # Use real scraper logic
            target_url = c.business.google_maps_url
            if not target_url:
                c.status = "FAILED"
                c.error_message = "No Google Maps URL provided for business"
                db.commit()
                continue

            result = await adapter.scrape(target_url)

            c.status = result.status
            c.error_message = result.error_message

            if result.status == "SUCCESS":
                c.posts_discovered = len(result.posts)
                c.new_posts = 0

                # Persist posts and observations
                for post_data in result.posts:
                    # Identity check
                    existing_post = None
                    if post_data.source_id:
                        existing_post = db.query(Post).filter(
                            Post.business_id == c.business_id,
                            Post.source_identifier == post_data.source_id
                        ).first()
                    else:
                        existing_post = db.query(Post).filter(
                            Post.business_id == c.business_id,
                            Post.fingerprint == post_data.fingerprint
                        ).first()

                    if not existing_post:
                        c.new_posts += 1
                        existing_post = Post(
                            business_id=c.business_id,
                            source_identifier=post_data.source_id,
                            fingerprint=post_data.fingerprint,
                            text_content=post_data.text_content,
                            published_date=post_data.published_date,
                            cta_link=post_data.cta_url,
                            source_url=post_data.source_url
                        )
                        db.add(existing_post)
                        db.commit() # Commit to get ID for observation

                    # Create observation
                    obs = ScrapeObservation(
                        scrape_run_competitor_id=c.id,
                        post_id=existing_post.id,
                        is_new=(existing_post.created_at == existing_post.updated_at)
                    )
                    db.add(obs)
                db.commit()
            elif result.status == "NO_DATA":
                c.posts_discovered = 0

            db.commit()

        # Determine final status and counters
        run.competitors_succeeded = sum(1 for c in competitor_runs if c.status in ("SUCCESS", "NO_DATA"))
        run.competitors_failed = sum(1 for c in competitor_runs if c.status in ("FAILED", "ERROR"))

        final_status = "SUCCESS"
        if any(c.status == "VERIFICATION_REQUIRED" for c in competitor_runs):
            final_status = "PAUSED_MANUAL_INTERVENTION"
        elif any(c.status in ("FAILED", "ERROR") for c in competitor_runs):
            if run.competitors_succeeded > 0:
                final_status = "PARTIAL_SUCCESS"
            else:
                final_status = "FAILED"

        run.status = final_status
        run.end_time = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Finished scrape job for run {run_id} with status {final_status}")
    except Exception as e:
        logger.exception("Error in worker job")
        db.rollback()
    finally:
        if not ctx:
            await adapter.close() # cleanup if created locally
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
    functions = [scrape_job]
    redis_settings = get_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
