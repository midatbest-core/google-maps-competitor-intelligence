from bs4 import BeautifulSoup
from typing import List
import logging

logger = logging.getLogger(__name__)

class PostLocator:
    @staticmethod
    def locate(soup: BeautifulSoup) -> List[BeautifulSoup]:
        """
        Locates update/post containers within the parsed HTML.
        Uses a layered extraction strategy based on multiple possible DOM structures.
        """
        candidates = []
        
        # Strategy 1: Data attributes (usually the most stable if present)
        # Often Google Maps posts have a specific data-post-id or similar
        items = soup.find_all(lambda tag: tag.has_attr('data-post-id') or tag.has_attr('data-update-id'))
        if items:
            logger.debug(f"Strategy 1 found {len(items)} items")
            return items
            
        # Strategy 2: Common class names for posts (can be brittle)
        # The class names like ODSEW-BN9H-post might change, but typically there's a distinct container
        # We can look for divs containing a specific ARIA structure like "Update from" or similar.
        items = soup.find_all('div', attrs={"aria-label": lambda v: v and ("update from" in v.lower() or "post from" in v.lower())})
        if items:
            logger.debug(f"Strategy 2 found {len(items)} items")
            return items
            
        # Strategy 3: Structural fallback. 
        # Look for the feed container and grab its immediate children.
        feed = soup.find('div', role='feed')
        if feed:
            children = feed.find_all('div', recursive=False)
            if children:
                logger.debug(f"Strategy 3 found {len(children)} items")
                return children
                
        return candidates
