import hashlib
from app.scraper.schemas import NormalizedPost

class IdentityGenerator:
    @staticmethod
    def generate_fingerprint(post: NormalizedPost) -> str:
        """
        Generates a deterministic fingerprint for a post when a stable source ID is missing.
        Uses date and text content.
        """
        if post.source_id:
            return post.source_id
            
        components = []
        if post.text_content:
            components.append(post.text_content[:200]) # First 200 chars
            
        if post.published_date:
            # Include date in ISO format, up to the day (Google Maps dates are fuzzy)
            components.append(post.published_date.strftime('%Y-%m-%d'))
            
        if not components:
            # Absolute fallback
            components.append("empty-post")
            
        raw = "|".join(components).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()
