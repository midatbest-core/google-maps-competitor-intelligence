import hashlib
from app.scraper.schemas import NormalizedPost

class IdentityGenerator:
    @staticmethod
    def generate_fingerprint(post: NormalizedPost) -> str:
        """
        Generates a deterministic fingerprint for a post when a stable source ID is missing.
        Uses normalized text content to ensure idempotency across multiple scrapes regardless
        of fluctuating relative date strings ("1 day ago", "yesterday", etc.).
        """
        if post.source_id:
            return post.source_id

        if post.source_url:
            return hashlib.sha256(post.source_url.strip().encode('utf-8')).hexdigest()

        # Deterministic text-based fingerprint
        text = (post.text_content or "").strip()
        if text:
            # Normalize whitespace and lowercase
            norm_text = " ".join(text.lower().split())
            return hashlib.sha256(norm_text.encode('utf-8')).hexdigest()

        # For media-only posts without text, use media URLs if available
        if post.media_urls:
            raw_media = "|".join(sorted(post.media_urls))
            return hashlib.sha256(raw_media.encode('utf-8')).hexdigest()

        if post.published_date:
            return hashlib.sha256(post.published_date.strftime('%Y-%m-%d').encode('utf-8')).hexdigest()

        return hashlib.sha256(b"empty-post").hexdigest()
