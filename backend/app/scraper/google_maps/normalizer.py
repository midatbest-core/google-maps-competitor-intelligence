import re
from app.scraper.schemas import NormalizedPost

class Normalizer:
    @staticmethod
    def normalize(post: NormalizedPost) -> NormalizedPost:
        """
        Normalizes the extracted post content for deterministic storage and fingerprinting.
        - Trims whitespace
        - Unifies line endings
        - Strips query params from media URLs
        """
        
        # Normalize text content
        if post.text_content:
            # Replace multiple whitespace with single space, unify newlines
            text = post.text_content
            text = text.replace('\r\n', '\n')
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\n+', '\n', text)
            text = text.strip()
            post.text_content = text if text else None
            
        # Normalize CTA
        if post.cta_text:
            post.cta_text = post.cta_text.strip()
        if post.cta_url:
            post.cta_url = post.cta_url.strip()
            
        # Normalize Media URLs
        if post.media_urls:
            normalized_urls = []
            for url in post.media_urls:
                # Basic normalization: strip query params if they don't seem critical
                # But Google Maps often uses query params for sizing (e.g. =w400-h300)
                # Let's keep them as-is but strip whitespace.
                url = url.strip()
                if url not in normalized_urls:
                    normalized_urls.append(url)
            post.media_urls = normalized_urls
            
        return post
