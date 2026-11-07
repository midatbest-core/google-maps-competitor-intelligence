import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import List, Optional
from app.scraper.schemas import ExtractedReview, ExtractionFailure, ReviewScrapeResult

logger = logging.getLogger(__name__)

class GosomScraperAdapter:
    """
    Adapter for gosom/google-maps-scraper (https://github.com/gosom/google-maps-scraper).
    Executes the binary or docker container if installed/configured, or reports availability.
    """
    def __init__(self, binary_path: Optional[str] = None):
        self.binary_path = binary_path or os.environ.get("GOSOM_BINARY_PATH") or shutil.which("google-maps-scraper")

    def is_available(self) -> bool:
        return bool(self.binary_path and os.path.exists(self.binary_path))

    async def scrape_reviews(self, target_url: str, depth: int = 1) -> ReviewScrapeResult:
        result = ReviewScrapeResult()

        if not self.is_available():
            logger.info("Gosom binary not found; skipping gosom runner")
            result.status = "NO_DATA"
            result.error_message = "gosom/google-maps-scraper binary is not installed in environment"
            return result

        temp_dir = tempfile.mkdtemp(prefix="gosom_")
        input_file = os.path.join(temp_dir, "queries.txt")
        output_file = os.path.join(temp_dir, "results.json")

        try:
            with open(input_file, "w", encoding="utf-8") as f:
                f.write(f"{target_url}\n")

            cmd = [
                self.binary_path,
                "-input", input_file,
                "-results", output_file,
                "-json",
                "-depth", str(depth),
                "-extra-reviews",
                "-exit-on-inactivity", "1m"
            ]

            logger.info(f"Executing gosom command: {' '.join(cmd)}")
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if proc.returncode != 0:
                logger.error(f"Gosom failed with code {proc.returncode}: {proc.stderr}")
                result.status = "ERROR"
                result.error_message = f"gosom exited with code {proc.returncode}"
                return result

            if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                result.status = "NO_DATA"
                return result

            with open(output_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Gosom outputs an array of place objects with user_reviews_extended and user_reviews
            entries = data if isinstance(data, list) else [data]
            for entry in entries:
                # Collect from both user_reviews_extended (from -extra-reviews) and user_reviews
                raw_reviews = []
                if isinstance(entry.get("user_reviews_extended"), list):
                    raw_reviews.extend(entry["user_reviews_extended"])
                if isinstance(entry.get("user_reviews"), list):
                    raw_reviews.extend(entry["user_reviews"])
                if isinstance(entry.get("reviews"), list):
                    raw_reviews.extend(entry["reviews"])

                for r in raw_reviews:
                    author = r.get("name") or r.get("author_name")
                    text = r.get("text") or r.get("review_text")
                    rating = r.get("rating")
                    if rating is not None:
                        try:
                            rating = float(rating)
                        except ValueError:
                            rating = None

                    relative_date = r.get("relative_date") or r.get("published_at_date")
                    response_text = r.get("response") or r.get("response_text")

                    raw_key = f"{author or 'unknown'}|{rating or 0}|{(text or '')[:100]}"
                    fp = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

                    result.reviews.append(ExtractedReview(
                        source_id=r.get("id"),
                        author_name=author,
                        rating=rating,
                        text=text,
                        relative_time_description=relative_date,
                        response_text=response_text,
                        source="gosom_scraper",
                        fingerprint=fp
                    ))

            result.status = "SUCCESS" if result.reviews else "NO_DATA"

        except subprocess.TimeoutExpired:
            result.status = "ERROR"
            result.error_message = "Gosom review scraping timed out"
        except Exception as e:
            logger.exception(f"Error executing gosom scraper: {e}")
            result.status = "ERROR"
            result.error_message = str(e)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return result

