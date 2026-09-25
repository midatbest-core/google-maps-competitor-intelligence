from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
from datetime import datetime
import dateparser
from app.scraper.google_maps.media import MediaExtractor
from app.scraper.schemas import NormalizedPost

class PostExtractor:
    @staticmethod
    def _extract_date(container: BeautifulSoup) -> Optional[datetime]:
        """
        Extracts and parses the date string to a datetime object.
        """
        # Google maps usually puts dates in a span like "3 days ago" or "Oct 21, 2023"
        # We can look for common date container classes or aria labels.
        # Often it's a span with class 'ylH6lf' or similar, but class names change.
        # Fallback to looking at all small spans or text matching date patterns.
        
        # Strategy 1: Looking for explicit date classes if known
        # Strategy 2: Look for 'ago' or standard date formats
        for span in container.find_all('span'):
            text = span.get_text(strip=True)
            if "ago" in text.lower() or len(text.split()) <= 4:
                # Try parsing it
                parsed = dateparser.parse(text)
                if parsed and parsed.year > 2000: # Sanity check
                    return parsed
        return None

    @staticmethod
    def _extract_text(container: BeautifulSoup) -> Optional[str]:
        # Often text is inside a div with specific data attributes or just paragraph tags
        # Sometimes there's a "Read more" button we need to ignore or expand
        # In a parsed HTML we might just get the snippet if it wasn't expanded,
        # but playwright could have expanded it.
        # Find the main text block. Typically it's a block with multiple lines.
        # For a robust fallback, just get all text that is not a button or link or date.
        
        # We'll try to find the longest continuous text node
        texts = [p.get_text(strip=True) for p in container.find_all(['div', 'p', 'span']) 
                 if p.get_text(strip=True) and len(p.get_text(strip=True)) > 20
                 and not p.find('button') and not p.find('a')]
        
        if texts:
            # Sort by length, assume longest block is the main post body
            texts.sort(key=len, reverse=True)
            return texts[0]
            
        return None

    @staticmethod
    def _extract_cta(container: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
        # Call to action buttons usually have an 'a' tag or 'button' tag with an external link
        # or specific text like "Learn more", "Sign up"
        for a in container.find_all('a', href=True):
            text = a.get_text(strip=True)
            if text and len(text) < 30: # CTAs are usually short
                return text, a['href']
                
        return None, None

    @staticmethod
    def extract(container: BeautifulSoup) -> NormalizedPost:
        """
        Attempts to extract fields from a post container.
        Returns a NormalizedPost schema with raw unnormalized data (normalization happens later).
        """
        source_id = container.get('data-post-id') or container.get('data-update-id')
        
        published_date = PostExtractor._extract_date(container)
        text_content = PostExtractor._extract_text(container)
        cta_text, cta_url = PostExtractor._extract_cta(container)
        media_urls = MediaExtractor.extract(container)
        
        return NormalizedPost(
            source_id=source_id,
            text_content=text_content,
            published_date=published_date,
            cta_text=cta_text,
            cta_url=cta_url,
            media_urls=media_urls
        )
