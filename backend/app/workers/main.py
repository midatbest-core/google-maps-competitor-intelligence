import asyncio
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

PER_BUSINESS_TIMEOUT: float = 60.0  # Sensible timeout per business
MAX_RETRIES_PER_BUSINESS: int = 1   # Controlled retries for transient failures

async def startup(ctx):
    logger.info("Worker starting up...")
    ctx['scraper_adapter'] = GoogleMapsAdapter()

async def shutdown(ctx):
    logger.info("Worker shutting down...")
    adapter = ctx.get('scraper_adapter')
    if adapter:
        await adapter.close()

async def scrape_job(ctx, run_id: str):
    import sys
    import asyncio
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    # On Windows, Playwright requires a ProactorEventLoop to spawn browser processes.
    # If the current loop is not a ProactorEventLoop (e.g. Uvicorn with SelectorEventLoop),
    # execute in a thread with a ProactorEventLoop.
    if sys.platform == "win32" and current_loop and not isinstance(current_loop, getattr(asyncio, "ProactorEventLoop", ())):
        import concurrent.futures
        def _proactor_runner():
            proactor = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(proactor)
            try:
                return proactor.run_until_complete(_execute_scrape_job(ctx, run_id))
            finally:
                proactor.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return await current_loop.run_in_executor(executor, _proactor_runner)

    return await _execute_scrape_job(ctx, run_id)


async def _heartbeat_worker(run_id: str, stop_event: asyncio.Event, interval_seconds: int = 15):
    """
    Periodically updates ScrapeRun.heartbeat_at in a dedicated database session.
    Runs continuously in the background while the scrape job executes.
    """
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            break
        except asyncio.TimeoutError:
            pass

        hb_db = None
        try:
            hb_db = SessionLocal()
            now = datetime.now(timezone.utc)
            hb_db.query(ScrapeRun).filter(ScrapeRun.id == run_id).update(
                {"heartbeat_at": now},
                synchronize_session=False
            )
            hb_db.commit()
            logger.debug(f"[Heartbeat] Refreshed heartbeat for run {run_id} at {now}")
        except Exception as e:
            logger.warning(f"[Heartbeat] Error updating heartbeat for run {run_id}: {e}")
            if hb_db:
                try:
                    hb_db.rollback()
                except Exception:
                    pass
        finally:
            if hb_db:
                try:
                    hb_db.close()
                except Exception:
                    pass


async def _execute_scrape_job(ctx, run_id: str):
    logger.info(f"Starting scrape job for run {run_id}")

    # Allow adapter to be mocked or retrieved from context
    adapter = ctx.get('scraper_adapter') if ctx else None
    if not adapter:
        adapter = GoogleMapsAdapter()

    db = SessionLocal()
    heartbeat_stop = None
    heartbeat_task = None
    try:
        run = db.query(ScrapeRun).filter(ScrapeRun.id == run_id).first()
        if not run:
            logger.error(f"Run {run_id} not found")
            return

        competitor_runs = db.query(ScrapeRunCompetitor).filter(ScrapeRunCompetitor.scrape_run_id == run_id).all()
        has_incomplete = any(c.status not in ("SUCCESS", "NO_DATA") for c in competitor_runs)

        # GUARD: Completed runs must never be restarted by duplicate or expired ARQ jobs
        if run.status == "SUCCESS" or (run.status in ("FAILED", "PARTIAL_SUCCESS", "PAUSED_MANUAL_INTERVENTION") and not has_incomplete):
            logger.info(f"Run {run_id} is already in terminal state ({run.status}), ignoring duplicate ARQ execution.")
            return

        now = datetime.now(timezone.utc)
        run.status = "RUNNING"
        run.start_time = now
        run.heartbeat_at = now
        db.commit()

        # Start periodic background heartbeat task
        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(_heartbeat_worker(run_id, heartbeat_stop, interval_seconds=15))

        for c in competitor_runs:
            if c.status in ("SUCCESS", "NO_DATA"):
                continue

            c.status = "RUNNING"
            run.heartbeat_at = datetime.now(timezone.utc)
            db.commit()

            # Validate target URL
            target_url = c.business.google_maps_url
            if not target_url:
                c.status = "FAILED"
                c.error_message = "No Google Maps URL provided for business"
                db.commit()
                continue

            # Per-business execution with controlled retry and timeout
            result = None
            for attempt in range(MAX_RETRIES_PER_BUSINESS + 1):
                try:
                    result = await asyncio.wait_for(
                        adapter.scrape(target_url),
                        timeout=PER_BUSINESS_TIMEOUT
                    )
                    break
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout ({PER_BUSINESS_TIMEOUT}s) on attempt {attempt+1} for {c.business.business_name} ({target_url})")
                    if attempt < MAX_RETRIES_PER_BUSINESS:
                        await asyncio.sleep(2)
                        continue
                    from app.scraper.schemas import ScrapeResult
                    result = ScrapeResult(status="ERROR", error_message=f"Timeout: Exceeded {int(PER_BUSINESS_TIMEOUT)}s processing business")
                except Exception as scrape_err:
                    logger.warning(f"Error on attempt {attempt+1} for {c.business.business_name}: {scrape_err}")
                    if attempt < MAX_RETRIES_PER_BUSINESS:
                        await asyncio.sleep(2)
                        continue
                    from app.scraper.schemas import ScrapeResult
                    result = ScrapeResult(status="ERROR", error_message=str(scrape_err))

            # Isolated post-processing for this competitor
            try:
                c.status = result.status if result else "ERROR"
                c.error_message = result.error_message if result else "Unknown error during scrape"

                if result and result.status == "SUCCESS":
                    c.posts_discovered = len(result.posts)
                    c.new_posts = 0

                    storage_provider = LocalStorageProvider(base_dir=settings.LOCAL_STORAGE_DIR)
                    media_downloader = SimpleMediaDownloader()
                    ingestion_service = IngestionService(db, storage_provider, media_downloader)

                    for post_data in result.posts:
                        try:
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
                                    try:
                                        await intelligence_job(ctx, res.post_id)
                                    except Exception as e:
                                        logger.error(f"Failed to run intelligence job for {res.post_id}: {e}")
                        except Exception as post_err:
                            logger.error(f"Failed to ingest post for business {c.business_id}: {post_err}")

                elif result and result.status == "NO_DATA":
                    c.posts_discovered = 0

                run.heartbeat_at = datetime.now(timezone.utc)
                db.commit()
            except Exception as comp_err:
                logger.exception(f"Error persisting competitor run {c.id}: {comp_err}")
                db.rollback()
                try:
                    c.status = "ERROR"
                    c.error_message = f"Error persisting results: {comp_err}"
                    db.commit()
                except Exception:
                    db.rollback()

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
        if heartbeat_stop is not None:
            heartbeat_stop.set()
        if heartbeat_task is not None:
            try:
                await asyncio.wait_for(heartbeat_task, timeout=2.0)
            except Exception:
                pass
        if not ctx:
            try:
                await adapter.close()
            except Exception as close_err:
                logger.warning(f"Error closing scraper adapter: {close_err}")
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
    import sys
    import asyncio
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if sys.platform == "win32" and current_loop and not isinstance(current_loop, getattr(asyncio, "ProactorEventLoop", ())):
        import concurrent.futures
        def _proactor_runner():
            proactor = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(proactor)
            try:
                return proactor.run_until_complete(_execute_discovery_job(ctx, run_id))
            finally:
                proactor.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return await current_loop.run_in_executor(executor, _proactor_runner)

    return await _execute_discovery_job(ctx, run_id)


async def _execute_discovery_job(ctx, run_id: str):
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
        from app.models.analysis import GeneratedContent

        gc = db.query(GeneratedContent).filter_by(id=content_id).first()
        if not gc:
            logger.warning(f"Content {content_id} not found in database")
            return
        if gc.status == "SUCCESS":
            logger.info(f"Content {content_id} already SUCCESS, skipping execution")
            return

        try:
            ai_provider = get_ai_provider()
            emb_provider = get_embedding_provider()
        except Exception as prov_err:
            logger.error(f"Failed to initialize AI/Embedding provider for content {content_id}: {prov_err}")
            if gc and gc.status in ("QUEUED", "RUNNING"):
                gc.status = "FAILED"
                gc.error_message = f"AI Provider configuration error: {prov_err}"
                db.commit()
            return

        service = GenerationService(db, ai_provider, emb_provider)
        await service.execute_generation(content_id)

    except (Exception, asyncio.CancelledError) as e:
        logger.exception(f"Error in generation job for content {content_id}")
        try:
            db.rollback()
            from app.models.analysis import GeneratedContent
            gc = db.query(GeneratedContent).filter_by(id=content_id).first()
            if gc and gc.status != "SUCCESS":
                gc.status = "FAILED"
                gc.error_message = f"Worker generation failure: {str(e) or type(e).__name__}"
                db.commit()
        except Exception as recovery_err:
            logger.error(f"Failed to record failure status for content {content_id}: {recovery_err}")
        if isinstance(e, asyncio.CancelledError):
            raise
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

            # Check for active run and reconcile if heartbeat has expired (>300s / 5 mins)
            active_run = db.scalar(
                select(ScrapeRun)
                .where(ScrapeRun.project_id == schedule.project_id)
                .where(ScrapeRun.status.in_(["QUEUED", "RUNNING", "RETRYING", "PAUSED_MANUAL_INTERVENTION"]))
                .limit(1)
            )

            if active_run:
                # Use dedicated heartbeat_at, falling back to start_time or created_at for legacy runs
                last_alive = active_run.heartbeat_at or active_run.start_time or active_run.created_at
                if last_alive:
                    last_alive = last_alive.replace(tzinfo=timezone.utc) if last_alive.tzinfo is None else last_alive
                    if (now - last_alive).total_seconds() > 300:
                        all_comps = active_run.competitor_runs
                        if all_comps and all(cr.status in ("SUCCESS", "NO_DATA") for cr in all_comps):
                            active_run.status = "SUCCESS"
                            active_run.competitors_succeeded = len(all_comps)
                            active_run.competitors_failed = 0
                        else:
                            any_succeeded = any(cr.status in ("SUCCESS", "NO_DATA") for cr in (all_comps or []))
                            active_run.status = "PARTIAL_SUCCESS" if any_succeeded else "FAILED"
                            active_run.error_logs = ["Marked as FAILED due to heartbeat expiration (worker dead)"]
                            for cr in (all_comps or []):
                                if cr.status == "RUNNING":
                                    cr.status = "FAILED"
                                    cr.error_message = "Worker process interrupted"
                        active_run.end_time = now
                        db.commit()
                        active_run = None

            if not active_run:
                logger.info(f"scheduled_scrape_started: Project {schedule.project_id}")
                try:
                    # Exclusively dispatches via transactional outbox
                    service.create_scrape_run(schedule.project_id)
                except Exception as e:
                    logger.error(f"scheduled_scrape_failed: Project {schedule.project_id}: {e}")
            else:
                logger.info(f"scheduled_scrape_skipped_active_run: Project {schedule.project_id}")

        # Dispatch pending/retrying transactional outbox messages exclusively
        try:
            from app.services.outbox_service import OutboxDispatcher, cleanup_dispatched_outbox_messages
            redis_pool = ctx.get('redis') if ctx else None
            dispatcher = OutboxDispatcher(pool=redis_pool)
            dispatched = await dispatcher.dispatch_pending(db, limit=50)
            if dispatched > 0:
                logger.info(f"[SchedulerTick] Dispatched {dispatched} pending outbox messages")
            
            # Retention cleanup for dispatched outbox messages older than 30 days
            cleanup_dispatched_outbox_messages(db, older_than_days=30)
        except Exception as oe:
            logger.error(f"[SchedulerTick] Error processing outbox messages: {oe}")

        # Reconcile stale generation jobs safely (using separate execution vs queue wait checks)
        try:
            from app.services.generation_service import GenerationService
            reconciled_gens = GenerationService.reconcile_stale_generations(db)
            if reconciled_gens > 0:
                logger.info(f"[SchedulerTick] Reconciled {reconciled_gens} stale generation jobs to FAILED")
        except Exception as ge:
            logger.error(f"[SchedulerTick] Error reconciling stale generation jobs: {ge}")

    except Exception as e:
        logger.exception("Error in scheduler_tick")
    finally:
        db.close()

async def combined_intelligence_job(ctx, project_id: str):
    logger.info(f"Starting combined intelligence job for project {project_id}")
    db = SessionLocal()
    try:
        from app.services.combined_intelligence_service import CombinedIntelligenceService
        from app.providers.ai.factory import get_ai_provider

        ai_provider = get_ai_provider()
        service = CombinedIntelligenceService(db, ai_provider)
        report = await service.generate_report(project_id)
        logger.info(f"Finished combined intelligence job for project {project_id}, status: {getattr(report, 'status', 'SUCCESS')}")
        return report
    except Exception as e:
        logger.exception(f"Error in combined intelligence job for project {project_id}: {e}")
        db.rollback()
    finally:
        db.close()

def get_redis_settings():
    from app.core.arq import redis_settings_from_url
    return redis_settings_from_url(settings.REDIS_URL)

class WorkerSettings:
    functions = [scrape_job, intelligence_job, discovery_job, generate_content_job, combined_intelligence_job]
    from arq.cron import cron
    cron_jobs = [cron(scheduler_tick, minute=set(range(60)))]
    redis_settings = get_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = 1200  # 20 minutes job timeout (capped by per-business 60s timeouts)
    max_jobs = 1        # Strict single-worker concurrency to prevent OOM and browser state collisions
