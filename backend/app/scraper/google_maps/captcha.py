from bs4 import BeautifulSoup
import re

class CaptchaDetector:
    @staticmethod
    def detect(soup: BeautifulSoup) -> bool:
        """
        Detects if the page is currently showing a verification or CAPTCHA challenge.
        """
        text = soup.get_text().lower()
        
        # Checking for common google captcha or consent mechanisms that block navigation
        if "our systems have detected unusual traffic" in text:
            return True
            
        if soup.find('form', id='captcha-form'):
            return True
            
        if soup.find('div', class_='g-recaptcha'):
            return True
            
        # Detect before you continue consent overlay which can block scraping
        if "before you continue to google" in text and soup.find('button', attrs={"aria-label": re.compile(r"accept all", re.I)}):
            # This is consent, not necessarily captcha, but it blocks.
            # In a real implementation we might click it, but we can treat as verification required
            # if we can't bypass it. Let's just look for real captcha for now.
            pass
            
        return False
