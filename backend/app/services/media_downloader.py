import urllib.request
import asyncio
from typing import Optional
import logging
from app.services.ingestion_service import MediaDownloader

logger = logging.getLogger(__name__)

class SimpleMediaDownloader(MediaDownloader):
    async def download(self, url: str) -> Optional[bytes]:
        try:
            return await asyncio.to_thread(self._download_sync, url)
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return None

    def _download_sync(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                return response.read()
            raise ValueError(f"HTTP {response.status}")
