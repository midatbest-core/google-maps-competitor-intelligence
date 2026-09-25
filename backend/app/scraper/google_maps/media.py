from bs4 import BeautifulSoup
from typing import List

class MediaExtractor:
    @staticmethod
    def extract(container: BeautifulSoup) -> List[str]:
        """
        Extracts media references (image URLs, video URLs) from a post container.
        Prioritizes metadata and stable references over dynamic blob URLs.
        """
        urls = []
        
        # Look for image tags
        images = container.find_all('img')
        for img in images:
            src = img.get('src') or img.get('data-src')
            if src and src.startswith('http') and not src.startswith('data:image'):
                # Basic filter to avoid tracking pixels or small icons if necessary,
                # but we'll collect all valid external http images for now
                if src not in urls:
                    urls.append(src)
                    
        # Look for background images in divs (common in Google Maps)
        divs = container.find_all('div', style=lambda v: v and 'background-image' in v)
        for div in divs:
            style = div.get('style')
            # Extract URL from background-image: url("...")
            import re
            match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', style)
            if match:
                src = match.group(1)
                if src.startswith('http') and src not in urls:
                    urls.append(src)
                    
        return urls
