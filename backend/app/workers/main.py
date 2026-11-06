from datetime import datetime, timezone
import logging
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.scrape import ScrapeRun, ScrapeRunCompetitor, ScrapeObservation
from app.models.post import Post
from app.models.discovery import DiscoveryRun
from app.scraper.google_maps.adapter import GoogleMapsAdapter
from app.core.arq import redis_settings_from_url
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

                    if res.status != "FAILED":
                        if ctx and 'redis' in ctx:
                            try:
                                await ctx['redis'].enqueue_job('intelligence_job', res.post_id)
                            except Exception as e:
                                logger.error(f"Failed to enqueue intelligence job for {res.post_id}: {e}")
                        else:
                            # Run synchronously or in background if no ARQ
                            import asyncio
                            asyncio.create_task(intelligence_job(None, res.post_id))

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
        logger.exception(f"Error in worker job for run {run_id}: {e}")
        db.rollback()
        # Persist FAILED status to avoid stale QUEUED runs
        try:
            failed_run = db.query(ScrapeRun).filter(ScrapeRun.id == run_id).first()
            if failed_run:
                failed_run.status = "FAILED"
                failed_run.end_time = datetime.now(timezone.utc)
                db.commit()
        except Exception as inner_e:
            logger.error(f"Failed to persist FAILED status for run {run_id}: {inner_e}")
    finally:
        if not ctx:
            try:
                import asyncio
                asyncio.create_task(adapter.close())
            except Exception:
                pass
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
        try:
            failed_run = db.query(DiscoveryRun).filter_by(id=run_id).first()
            if failed_run:
                failed_run.status = "FAILED"
                failed_run.completed_at = datetime.now(timezone.utc)
                failed_run.error_message = "Discovery worker failed before completion"
                db.commit()
        except Exception:
            logger.exception("Failed to persist discovery worker failure")
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

def get_redis_settings():
    return redis_settings_from_url(
        settings.REDIS_URL,
        conn_timeout=1,
        conn_retries=5,
    )

class WorkerSettings:
    functions = [scrape_job, intelligence_job, discovery_job, generate_content_job]
    redis_settings = get_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
