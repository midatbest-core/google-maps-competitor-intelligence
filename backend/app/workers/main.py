from datetime import datetime, timezone
import logging
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor, ScrapeObservation
from app.models.post import Post
from app.scraper.google_maps.adapter import GoogleMapsAdapter
from arq.connections import RedisSettings
from app.services.ingestion_service import IngestionService
from app.services.media_downloader import SimpleMediaDownloader
from app.core.storage import LocalStorageProvider

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

                # Initialize services
                storage_provider = LocalStorageProvider(base_dir=settings.LOCAL_STORAGE_DIR)
                media_downloader = SimpleMediaDownloader()
                ingestion_service = IngestionService(db, storage_provider, media_downloader)

                # Persist posts and observations
                for post_data in result.posts:
                    res = await ingestion_service.ingest_post(
                        project_id=run.project_id,
                        business_id=c.business_id,
                        competitor_run_id=c.id,
                        post_data=post_data
                    )
                    if res.status == "NEW_POST":
                        c.new_posts += 1

                    if res.status != "FAILED" and ctx and 'redis' in ctx:
                        try:
                            await ctx['redis'].enqueue_job('intelligence_job', res.post_id)
                        except Exception as e:
                            logger.error(f"Failed to enqueue intelligence job for {res.post_id}: {e}")

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


async def intelligence_job(ctx, post_id: str):
    logger.info(f"Starting intelligence job for post {post_id}")
    db = SessionLocal()
    try:
        from app.services.analysis_service import AnalysisService
        from app.providers.ai.factory import get_ai_provider
        from app.providers.embedding.factory import get_embedding_provider

        service = AnalysisService(db, get_ai_provider(), get_embedding_provider())

        # We don't fail scraping if this fails, they are decoupled.
        analysis = await service.analyze_post(post_id)
        if analysis:
            await service.embed_post(post_id)

        logger.info(f"Finished intelligence job for post {post_id}")
    except Exception as e:
        logger.exception(f"Error in intelligence job for post {post_id}")
        db.rollback()
    finally:
        db.close()


async def discovery_job(ctx, run_id: str):
    logger.info(f"Starting discovery job for run {run_id}")
    db = SessionLocal()
    try:
        from app.services.discovery_service import DiscoveryService
        from app.providers.discovery.factory import get_discovery_provider

        provider = get_discovery_provider()
        service = DiscoveryService(db, provider)
        await service.execute_discovery(run_id)

    except Exception as e:
        logger.exception(f"Error in discovery job for run {run_id}")
        db.rollback()
    finally:
        db.close()


async def generate_content_job(ctx, content_id: str):
    logger.info(f"Starting generation job for content {content_id}")
    db = SessionLocal()
    try:
        from app.services.generation_service import GenerationService
        from app.providers.ai.factory import get_ai_provider
        from app.providers.embedding.factory import get_embedding_provider

        ai_provider = get_ai_provider()
        emb_provider = get_embedding_provider()
        service = GenerationService(db, ai_provider, emb_provider)
        await service.execute_generation(content_id)

    except Exception as e:
        logger.exception(f"Error in generation job for content {content_id}")
        db.rollback()
    finally:
        db.close()

async def scheduler_tick(ctx):
    logger.info("Running scheduler tick")
    db = SessionLocal()
    try:
        from app.services.scrape_service import ScrapeService
        from sqlalchemy import select
        from app.models.scrape import ScrapeSchedule, ScrapeRun

        now = datetime.now(timezone.utc)

        schedules = db.scalars(
            select(ScrapeSchedule)
            .where(ScrapeSchedule.enabled == True)
            .where(ScrapeSchedule.next_run_at <= now)
        ).all()

        service = ScrapeService(db)

        for schedule in schedules:
            new_next_run_at = service.calculate_next_run(schedule.time_of_day, schedule.timezone, now=now)

            # Atomic claim
            from sqlalchemy import update
            stmt = (
                update(ScrapeSchedule)
                .where(ScrapeSchedule.id == schedule.id)
                .where(ScrapeSchedule.next_run_at == schedule.next_run_at)
                .values(
                    last_run_at=now,
                    next_run_at=new_next_run_at
                )
            )
            result = db.execute(stmt)

            if result.rowcount == 0:
                logger.info(f"Schedule for project {schedule.project_id} already claimed by another worker")
                db.rollback() # Release any locks
                continue

            db.commit() # Commit the claim immediately so other workers see it

            # Check for active run
            active_run = db.scalar(
                select(ScrapeRun)
                .where(ScrapeRun.project_id == schedule.project_id)
                .where(ScrapeRun.status.in_(["QUEUED", "RUNNING", "RETRYING", "PAUSED_MANUAL_INTERVENTION"]))
                .limit(1)
            )

            if not active_run:
                logger.info(f"scheduled_scrape_started: Project {schedule.project_id}")
                try:
                    run = service.create_scrape_run(schedule.project_id)
                    if ctx and 'redis' in ctx:
                        await ctx['redis'].enqueue_job('scrape_job', run.id)
                except Exception as e:
                    logger.error(f"scheduled_scrape_failed: Project {schedule.project_id}: {e}")
            else:
                logger.info(f"scheduled_scrape_skipped_active_run: Project {schedule.project_id}")

    except Exception as e:
        logger.exception("Error in scheduler_tick")
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
    functions = [scrape_job, intelligence_job, discovery_job, generate_content_job]
    from arq.cron import cron
    cron_jobs = [cron(scheduler_tick, minute=set(range(60)))]
    redis_settings = get_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
