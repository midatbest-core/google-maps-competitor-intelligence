from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional, List, Dict, Tuple
import logging
from pydantic import BaseModel
from datetime import datetime, timezone
import hashlib

from app.models.post import Post, PostMedia
from app.models.scrape import ScrapeRunCompetitor, ScrapeObservation
from app.scraper.schemas import NormalizedPost
from app.core.storage import StorageProvider

logger = logging.getLogger(__name__)

class IngestionResult(BaseModel):
    post_id: str
    status: str  # NEW_POST, EXISTING_POST, UPDATED_POST, FAILED
    observation_created: bool
    media_saved: int = 0
    media_failed: int = 0

class MediaDownloader:
    """Interface for downloading media."""
    async def download(self, url: str) -> Optional[bytes]:
        raise NotImplementedError

class IngestionService:
    def __init__(self, db: Session, storage_provider: StorageProvider, media_downloader: MediaDownloader = None):
        self.db = db
        self.storage = storage_provider
        self.media_downloader = media_downloader

    def _find_canonical_post(self, business_id: str, post_data: NormalizedPost) -> Optional[Post]:
        # Priority 1: source_id
        if post_data.source_id:
            post = self.db.query(Post).filter(
                Post.business_id == business_id,
                Post.source_identifier == post_data.source_id
            ).first()
            if post:
                return post

        # Priority 2: source_url
        if post_data.source_url:
            post = self.db.query(Post).filter(
                Post.business_id == business_id,
                Post.source_url == post_data.source_url
            ).first()
            if post:
                return post

        # Priority 3/4: fingerprint
        if post_data.fingerprint:
            post = self.db.query(Post).filter(
                Post.business_id == business_id,
                Post.fingerprint == post_data.fingerprint
            ).first()
            if post:
                return post

        return None

    def _update_mutable_fields(self, post: Post, post_data: NormalizedPost) -> bool:
        updated = False
        if post_data.text_content and post.text_content != post_data.text_content:
            post.text_content = post_data.text_content
            updated = True
            
        if post_data.published_date and post.published_date != post_data.published_date:
            post.published_date = post_data.published_date
            updated = True
            
        if post_data.cta_url and post.cta_link != post_data.cta_url:
            post.cta_link = post_data.cta_url
            updated = True
            
        # Do not update immutable identity fields (source_id, source_url)
        # Fingerprint might change if content changes, but let's keep it stable 
        # unless it's necessary to update. We'll update fingerprint if content changed.
        if updated and post_data.fingerprint:
            post.fingerprint = post_data.fingerprint

        return updated

    async def ingest_post(
        self, 
        project_id: str, 
        business_id: str, 
        competitor_run_id: str, 
        post_data: NormalizedPost
    ) -> IngestionResult:
        try:
            return await self._ingest_post_impl(project_id, business_id, competitor_run_id, post_data)
        except IntegrityError:
            # If concurrent ingestion creates a duplicate, rollback and retry once
            self.db.rollback()
            try:
                return await self._ingest_post_impl(project_id, business_id, competitor_run_id, post_data)
            except Exception as e:
                self.db.rollback()
                logger.error(f"Ingestion failed for post {post_data.source_id or post_data.fingerprint}: {e}")
                return IngestionResult(post_id="", status="FAILED", observation_created=False)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ingestion failed for post {post_data.source_id or post_data.fingerprint}: {e}")
            return IngestionResult(post_id="", status="FAILED", observation_created=False)

    async def _ingest_post_impl(
        self, 
        project_id: str, 
        business_id: str, 
        competitor_run_id: str, 
        post_data: NormalizedPost
    ) -> IngestionResult:
        
        status = "NEW_POST"
        
        # 1. Identity Resolution
        post = self._find_canonical_post(business_id, post_data)
        
        if post:
            # 2. Update existing post
            updated = self._update_mutable_fields(post, post_data)
            status = "UPDATED_POST" if updated else "EXISTING_POST"
        else:
            # 3. Create new canonical Post
            post = Post(
                business_id=business_id,
                source_identifier=post_data.source_id,
                source_url=post_data.source_url,
                fingerprint=post_data.fingerprint,
                text_content=post_data.text_content,
                published_date=post_data.published_date,
                cta_link=post_data.cta_url
            )
            self.db.add(post)
            self.db.flush() # get post.id

        # 4. Scrape Observation uniqueness
        obs_created = False
        existing_obs = self.db.query(ScrapeObservation).filter(
            ScrapeObservation.scrape_run_competitor_id == competitor_run_id,
            ScrapeObservation.post_id == post.id
        ).first()

        if not existing_obs:
            is_new = (status == "NEW_POST")
            obs = ScrapeObservation(
                scrape_run_competitor_id=competitor_run_id,
                post_id=post.id,
                is_new=is_new
            )
            self.db.add(obs)
            obs_created = True
            
        # Commit DB transaction so we have a persistent Post before dealing with media
        self.db.commit()

        # 5. Media processing (Idempotent)
        media_saved = 0
        media_failed = 0
        
        if post_data.media_urls and self.media_downloader:
            for idx, url in enumerate(post_data.media_urls):
                # Simple deterministic key for media id: hash of URL
                media_id = hashlib.sha256(url.encode()).hexdigest()
                storage_key = f"media/projects/{project_id}/businesses/{business_id}/posts/{post.id}/{media_id}"
                
                # Check if this media is already linked to the post
                existing_media = self.db.query(PostMedia).filter(
                    PostMedia.post_id == post.id,
                    PostMedia.media_url == url
                ).first()
                
                if existing_media and existing_media.download_status == "SUCCESS":
                    continue # Already saved
                
                if not existing_media:
                    existing_media = PostMedia(
                        post_id=post.id,
                        media_url=url,
                        download_status="PENDING",
                        storage_key=storage_key
                    )
                    self.db.add(existing_media)
                    self.db.commit()

                # Try to download and store
                try:
                    content = await self.media_downloader.download(url)
                    if content:
                        self.storage.save(content, storage_key)
                        existing_media.download_status = "SUCCESS"
                        existing_media.file_size = len(content)
                        media_saved += 1
                    else:
                        existing_media.download_status = "FAILED"
                        existing_media.error_message = "Empty content"
                        media_failed += 1
                except Exception as e:
                    logger.error(f"Failed to download media {url}: {e}")
                    existing_media.download_status = "FAILED"
                    existing_media.error_message = str(e)
                    media_failed += 1
                    
                self.db.commit()

        return IngestionResult(
            post_id=post.id,
            status=status,
            observation_created=obs_created,
            media_saved=media_saved,
            media_failed=media_failed
        )
