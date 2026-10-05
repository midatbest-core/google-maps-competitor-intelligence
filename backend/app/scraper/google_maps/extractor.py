import re
from bs4 import BeautifulSoup
from typing import Optional
from datetime import datetime

import dateparser

from app.scraper.google_maps.media import MediaExtractor
from app.scraper.schemas import NormalizedPost


class PostExtractor:
    """
    Extracts structured post data from a BeautifulSoup post container element.

    Each ``_extract_*`` method tries multiple CSS class / attribute patterns in
    priority order so that the extractor stays robust across Google Maps DOM
    versions.  New patterns are added at the **top** of each method; legacy
    patterns are kept as fallbacks at the bottom.
    """

    # ----------------------------------------------------------------------- #
    # Source / reference ID                                                    #
    # ----------------------------------------------------------------------- #

    @staticmethod
    def _extract_source_id(container: BeautifulSoup) -> Optional[str]:
        """
        Extracts a stable, per-post identifier.

        Priority:
        1. ``data-post-id`` / ``data-update-id`` direct attribute.
        2. ``lpsid`` query parameter extracted from ``data-sharing-url``.
        3. ``lpsid`` query parameter extracted from any ``<a>`` href.
        """
        # 1 – direct attributes (legacy / some regions)
        for attr in ("data-post-id", "data-update-id"):
            val = container.get(attr)
            if val:
                return val

        # 2 – data-sharing-url (current DOM: present on post wrapper)
        sharing_url = container.get("data-sharing-url", "")
        lpsid = PostExtractor._extract_lpsid(sharing_url)
        if lpsid:
            return lpsid

        # Walk children for data-sharing-url
        for el in container.find_all(attrs={"data-sharing-url": True}):
            lpsid = PostExtractor._extract_lpsid(el.get("data-sharing-url", ""))
            if lpsid:
                return lpsid

        # 3 – lpsid in any href
        for a in container.find_all("a", href=True):
            lpsid = PostExtractor._extract_lpsid(a["href"])
            if lpsid:
                return lpsid

        return None

    @staticmethod
    def _extract_lpsid(url: str) -> Optional[str]:
        """Extracts the ``lpsid`` query parameter from a URL string."""
        if not url:
            return None
        match = re.search(r"lpsid=([^&\"']+)", url)
        return match.group(1) if match else None

    # ----------------------------------------------------------------------- #
    # Date                                                                     #
    # ----------------------------------------------------------------------- #

    @staticmethod
    def _extract_date(container: BeautifulSoup) -> Optional[datetime]:
        """
        Extracts and parses the post date.

        Priority:
        1. Element with class ``TW2TI`` (current Google Maps DOM).
        2. Element with class ``lqMB`` (From the owner structure).
        3. Span with any class matching ``date`` (heuristic).
        4. Any span whose text parses as a valid date (legacy fallback).
        """
        # 1 – TW2TI class (current DOM)
        el = container.find(class_=lambda c: c and "TW2TI" in c)
        if el:
            text = el.get_text(strip=True)
            parsed = dateparser.parse(text)
            if parsed and parsed.year > 2000:
                return parsed

        # 2 - lqMB class (From the owner)
        el = container.find(class_=lambda c: c and "lqMB" in c)
        if el:
            text = el.get_text(strip=True)
            parsed = dateparser.parse(text)
            if parsed and parsed.year > 2000:
                return parsed

        # 3 – class name heuristic
        for el in container.find_all(class_=re.compile(r"date", re.I)):
            text = el.get_text(strip=True)
            parsed = dateparser.parse(text)
            if parsed and parsed.year > 2000:
                return parsed

        # 4 – any span with date-like text (legacy)
        for span in container.find_all("span"):
            text = span.get_text(strip=True)
            if "ago" in text.lower() or len(text.split()) <= 4:
                parsed = dateparser.parse(text)
                if parsed and parsed.year > 2000:
                    return parsed

        return None

    # ----------------------------------------------------------------------- #
    # Text content                                                              #
    # ----------------------------------------------------------------------- #

    @staticmethod
    def _extract_text(container: BeautifulSoup) -> Optional[str]:
        """
        Extracts the main post body text.

        Priority:
        1. Element with class ``TrG26d`` (current Google Maps DOM).
        2. Element with class ``taHin`` or ``VpMB0`` (From the owner).
        3. Longest text block heuristic (legacy fallback).
        """
        # 1 – TrG26d class (current DOM)
        el = container.find(class_=lambda c: c and "TrG26d" in c)
        if el:
            text = el.get_text(separator=" ", strip=True)
            if text and len(text) > 10:
                return text

        # 2 - taHin / VpMB0 / LC9kbb (From the owner)
        el = container.find(class_=lambda c: c and any(x in c for x in ("taHin", "VpMB0", "jQnbnc")))
        if el:
            # If we grab a wrapper like jQnbnc, strip out the date/cta first in memory
            import copy
            el_copy = copy.copy(el)
            for child in el_copy.find_all(class_=lambda c: c and any(x in c for x in ("lqMB", "dsrqad"))):
                child.decompose()
            text = el_copy.get_text(separator=" ", strip=True)
            if text and len(text) > 5:
                return text

        # 3 – longest block heuristic (legacy)
        texts = [
            p.get_text(strip=True)
            for p in container.find_all(["div", "p", "span"])
            if p.get_text(strip=True)
            and len(p.get_text(strip=True)) > 20
            and not p.find("button")
            and not p.find("a")
        ]
        if texts:
            texts.sort(key=len, reverse=True)
            return texts[0]

        return None

    # ----------------------------------------------------------------------- #
    # Call-to-action                                                            #
    # ----------------------------------------------------------------------- #

    @staticmethod
    def _extract_cta(container: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
        """
        Extracts the call-to-action button text and URL.

        Priority:
        1. Element with class ``ABZ6xb`` (current Google Maps DOM).
        2. Element with class ``dsrqad`` (From the owner).
        3. Any ``<a>`` with short link text (legacy fallback).
        """
        # 1 – ABZ6xb class (current DOM)
        el = container.find(class_=lambda c: c and "ABZ6xb" in c)
        if el:
            text = el.get_text(strip=True)
            href = el.get("href") or (el.find("a") and el.find("a").get("href"))
            if text:
                return text, href

        # 2 - dsrqad class (From the owner)
        el = container.find(class_=lambda c: c and "dsrqad" in c)
        if el and el.find("a"):
            a = el.find("a")
            text = a.get_text(strip=True)
            if text:
                return text, a.get("href")

        # 3 – short <a> link text (legacy)
        for a in container.find_all("a", href=True):
            text = a.get_text(strip=True)
            if text and len(text) < 30:
                return text, a["href"]

        return None, None

    # ----------------------------------------------------------------------- #
    # Media                                                                    #
    # ----------------------------------------------------------------------- #

    @staticmethod
    def _extract_media(container: BeautifulSoup) -> list[str]:
        """
        Extracts media URLs from the post container.

        Priority:
        1. ``<img>`` with class ``tTCrvf`` (current Google Maps DOM).
        2. Delegates to ``MediaExtractor`` for general image/background
           extraction (handles all other cases including legacy patterns).
        """
        urls: list[str] = []

        # 1 – tTCrvf class (current DOM — typically the post image)
        for img in container.find_all("img", class_=lambda c: c and "tTCrvf" in c):
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("http") and src not in urls:
                urls.append(src)

        # 2 – general extractor (covers remaining images / backgrounds)
        for url in MediaExtractor.extract(container):
            if url not in urls:
                urls.append(url)

        return urls

    # ----------------------------------------------------------------------- #
    # Public entry point                                                       #
    # ----------------------------------------------------------------------- #

    @staticmethod
    def extract(container: BeautifulSoup) -> NormalizedPost:
        """
        Extracts all available fields from a post container element and returns
        a ``NormalizedPost``.  Normalization (whitespace, dedup) is handled by
        ``Normalizer`` in a subsequent step.
        """
        source_id = PostExtractor._extract_source_id(container)
        published_date = PostExtractor._extract_date(container)
        text_content = PostExtractor._extract_text(container)
        cta_text, cta_url = PostExtractor._extract_cta(container)
        media_urls = PostExtractor._extract_media(container)

        return NormalizedPost(
            source_id=source_id,
            text_content=text_content,
            published_date=published_date,
            cta_text=cta_text,
            cta_url=cta_url,
            media_urls=media_urls,
        )
