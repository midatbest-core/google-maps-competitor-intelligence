import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, delete, update

from app.models.outbox import OutboxMessage
from app.models.scrape import ScrapeRun
from app.core.arq import get_redis_pool

logger = logging.getLogger(__name__)


def create_outbox_message(db: Session, event_type: str, payload: dict) -> OutboxMessage:
    """Creates an OutboxMessage in the given database session without committing."""
    msg = OutboxMessage(
        event_type=event_type,
        payload=payload,
        status="PENDING",
        attempts=0,
        max_attempts=5,
    )
    db.add(msg)
    return msg


def cleanup_dispatched_outbox_messages(db: Session, older_than_days: int = 30) -> int:
    """
    Safely purges historical outbox messages that have already been DISPATCHED
    and are older than older_than_days.
    CRITICAL: Never deletes PENDING, CLAIMED, or FAILED records.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    stmt = (
        delete(OutboxMessage)
        .where(
            OutboxMessage.status == "DISPATCHED",
            OutboxMessage.dispatched_at <= cutoff
        )
        .execution_options(synchronize_session=False)
    )
    result = db.execute(stmt)
    deleted_count = result.rowcount
    db.commit()
    return deleted_count


class OutboxDispatcher:
    def __init__(self, pool=None):
        self._pool = pool

    async def _get_pool(self):
        if self._pool:
            return self._pool
        return await get_redis_pool()

    def claim_batch(self, db: Session, limit: int = 50, lease_seconds: int = 60) -> List[OutboxMessage]:
        """
        Atomically claims a batch of pending or expired-claim outbox messages.
        Commits the batch lease immediately so concurrent dispatchers skip these rows.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(OutboxMessage)
            .where(
                or_(
                    (
                        (OutboxMessage.status == "PENDING") &
                        (
                            OutboxMessage.next_attempt_at.is_(None) |
                            (OutboxMessage.next_attempt_at <= now)
                        )
                    ),
                    (
                        (OutboxMessage.status == "CLAIMED") &
                        (OutboxMessage.claimed_until <= now)
                    )
                )
            )
            .order_by(OutboxMessage.created_at.asc())
            .limit(limit)
        )

        try:
            stmt = stmt.with_for_update(skip_locked=True)
            messages = list(db.scalars(stmt))
        except Exception:
            messages = list(db.scalars(stmt))

        if not messages:
            return []

        for msg in messages:
            msg.status = "CLAIMED"
            msg.claimed_at = now
            msg.claimed_until = now + timedelta(seconds=lease_seconds)
            msg.claim_token = uuid4().hex
        db.commit()
        return messages

    def claim_next_message(self, db: Session, lease_seconds: int = 60) -> Optional[OutboxMessage]:
        """Claims a single outbox message using claim_batch(limit=1)."""
        claimed = self.claim_batch(db, limit=1, lease_seconds=lease_seconds)
        return claimed[0] if claimed else None

    async def dispatch_message(self, db: Session, message: OutboxMessage, pool=None) -> bool:
        """
        Dispatches a single outbox message to ARQ.
        Claims the message if not already claimed, then delegates to dispatch_claimed_message.
        """
        if message.status != "CLAIMED":
            now = datetime.now(timezone.utc)
            claim_token = uuid4().hex
            message.status = "CLAIMED"
            message.claimed_at = now
            message.claimed_until = now + timedelta(seconds=60)
            message.claim_token = claim_token
            try:
                db.commit()
            except Exception as e:
                return self._handle_failure(db, message, e, now, claim_token=claim_token)

        return await self.dispatch_claimed_message(db, message, pool=pool)

    async def dispatch_claimed_message(self, db: Session, message: OutboxMessage, pool=None) -> bool:
        """Dispatches an already claimed outbox message to the ARQ Redis worker."""
        now = datetime.now(timezone.utc)
        message.attempts += 1
        message.last_attempt_at = now
        claim_token = message.claim_token

        close_pool_after = False
        if pool is None:
            try:
                pool = await self._get_pool()
                close_pool_after = (self._pool is None)
            except Exception as e:
                return self._handle_failure(db, message, e, now, claim_token=claim_token)

        try:
            if message.event_type == "SCRAPE_RUN_DISPATCH":
                run_id = message.payload.get("run_id")
                if not run_id:
                    raise ValueError("Payload missing run_id")

                job = await pool.enqueue_job("scrape_job", run_id, _job_id=f"scrape_{run_id}")
                if job is None:
                    logger.info(f"[Outbox] Job scrape_{run_id} is already queued in ARQ.")
                else:
                    logger.info(f"[Outbox] Successfully enqueued job {job.job_id} for run {run_id}.")

            # Atomically transition to DISPATCHED guarded by claim_token and CLAIMED status
            where_conditions = [
                OutboxMessage.id == message.id,
                OutboxMessage.status == "CLAIMED",
            ]
            if claim_token is not None:
                where_conditions.append(OutboxMessage.claim_token == claim_token)
            else:
                where_conditions.append(OutboxMessage.claim_token.is_(None))

            stmt = (
                update(OutboxMessage)
                .where(*where_conditions)
                .values(
                    status="DISPATCHED",
                    dispatched_at=now,
                    claimed_until=None,
                    claim_token=None,
                    error_message=None,
                )
                .execution_options(synchronize_session=False)
            )
            result = db.execute(stmt)
            rowcount = result.rowcount
            db.commit()

            if rowcount == 0:
                logger.warning(
                    f"[Outbox] Message {message.id} claim lost (claim_token: {claim_token}). "
                    f"Zero rows updated when transitioning to DISPATCHED."
                )
                return False

            message.status = "DISPATCHED"
            message.dispatched_at = now
            message.claimed_until = None
            message.claim_token = None
            message.error_message = None
            return True

        except Exception as e:
            if not db.is_active:
                try:
                    db.rollback()
                except Exception:
                    pass
            return self._handle_failure(db, message, e, now, claim_token=claim_token, is_dispatch_commit_failure=True)
        finally:
            if close_pool_after and pool:
                try:
                    await pool.close()
                except Exception:
                    pass

    def _handle_failure(
        self,
        db: Session,
        message: OutboxMessage,
        exc: Exception,
        now: datetime,
        claim_token: Optional[str] = None,
        is_dispatch_commit_failure: bool = False
    ) -> bool:
        """
        Handles dispatch retry backoff or terminal failure with claim ownership fencing.
        Atomically updates the outbox row only if the claim token matches and status is CLAIMED.
        Ensures a stale dispatcher whose lease expired cannot overwrite a newer dispatcher's result,
        and guarantees that a DISPATCHED message can NEVER regress to PENDING or FAILED.
        """
        logger.warning(f"[Outbox] Dispatch attempt {message.attempts}/{message.max_attempts} failed: {exc}")

        try:
            if not db.is_active:
                db.rollback()
        except Exception:
            pass

        try:
            token = claim_token or getattr(message, "claim_token", None)
            new_attempts = message.attempts if message.attempts > 0 else 1
            max_attempts = getattr(message, "max_attempts", 5) or 5
            is_terminal = (new_attempts >= max_attempts)
            status = "FAILED" if is_terminal else "PENDING"
            backoff_secs = min(300, 2 ** new_attempts)
            next_attempt_at = None if is_terminal else (now + timedelta(seconds=backoff_secs))

            if is_dispatch_commit_failure:
                # The commit for DISPATCHED failed in the current session after a successful atomic claim check
                where_conditions = [
                    OutboxMessage.id == message.id,
                    OutboxMessage.status.in_(["CLAIMED", "DISPATCHED"]),
                ]
            else:
                where_conditions = [
                    OutboxMessage.id == message.id,
                    OutboxMessage.status == "CLAIMED",
                ]
                if token is not None:
                    where_conditions.append(OutboxMessage.claim_token == token)
                else:
                    where_conditions.append(OutboxMessage.claim_token.is_(None))

            stmt = (
                update(OutboxMessage)
                .where(*where_conditions)
                .values(
                    attempts=new_attempts,
                    error_message=str(exc),
                    last_attempt_at=now,
                    claimed_until=None,
                    claim_token=None,
                    status=status,
                    next_attempt_at=next_attempt_at,
                )
                .execution_options(synchronize_session=False)
            )
            res = db.execute(stmt)
            rowcount = res.rowcount

            if rowcount == 0:
                logger.warning(
                    f"[Outbox] Stale dispatcher failure update rejected for message {message.id} "
                    f"(token: {token}). 0 rows updated; claim was lost or message already finalized."
                )
                return False

            if is_terminal:
                if message.event_type == "SCRAPE_RUN_DISPATCH":
                    run_id = message.payload.get("run_id") if message.payload else None
                    if run_id:
                        db.execute(
                            update(ScrapeRun)
                            .where(
                                ScrapeRun.id == run_id,
                                ScrapeRun.status.in_(["QUEUED", "PENDING"])
                            )
                            .values(
                                status="FAILED",
                                error_logs=[f"Outbox dispatch terminal failure: Max retries ({max_attempts}) reached: {exc}"]
                            )
                            .execution_options(synchronize_session=False)
                        )

            db.commit()

            message.attempts = new_attempts
            message.status = status
            message.error_message = str(exc)
            message.last_attempt_at = now
            message.claimed_until = None
            message.claim_token = None
            message.next_attempt_at = next_attempt_at
            return False

        except Exception as recovery_err:
            logger.error(f"[Outbox] Failed to commit failure backoff state: {recovery_err}")
            try:
                db.rollback()
            except Exception:
                pass
            return False

    async def dispatch_pending(self, db: Session, limit: int = 50) -> int:
        """
        Dispatches pending outbox records using batch lease/claiming to prevent
        lock-release race conditions across concurrent dispatchers.
        """
        messages = self.claim_batch(db, limit=limit, lease_seconds=60)
        if not messages:
            return 0

        pool = None
        try:
            pool = await self._get_pool()
        except Exception as e:
            logger.error(f"[Outbox] Cannot acquire Redis pool for batch dispatch: {e}")
            for msg in messages:
                self._handle_failure(db, msg, e, datetime.now(timezone.utc), claim_token=msg.claim_token)
            return 0

        dispatched_count = 0
        try:
            for msg in messages:
                success = await self.dispatch_claimed_message(db, msg, pool=pool)
                if success:
                    dispatched_count += 1
        finally:
            if self._pool is None and pool:
                try:
                    await pool.close()
                except Exception:
                    pass

        return dispatched_count
