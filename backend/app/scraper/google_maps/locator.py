from bs4 import BeautifulSoup
from typing import List
import logging

logger = logging.getLogger(__name__)


class PostLocator:
    @staticmethod
    def locate(soup: BeautifulSoup) -> List[BeautifulSoup]:
        """
        Locates update/post containers within the parsed HTML.

        Uses a layered extraction strategy. Strategies are tried in priority
        order; the first one that yields results is returned so callers always
        receive the most-specific match available.

        Current Google Maps DOM (2026) uses class names such as
        ``localPostExpanded`` and ``TrG26d`` instead of ``data-post-id``
        attributes. Both old and new patterns are supported.
        """

        # ------------------------------------------------------------------ #
        # Strategy 1 – stable data attributes (older DOM / some regions)      #
        # ------------------------------------------------------------------ #
        items = soup.find_all(
            lambda tag: tag.has_attr("data-post-id") or tag.has_attr("data-update-id")
        )
        if items:
            logger.debug(f"Strategy 1 (data-post-id / data-update-id) found {len(items)} items")
            return items

        # ------------------------------------------------------------------ #
        # Strategy 2 – ``localPostExpanded`` class (current Google Maps DOM)  #
        # ------------------------------------------------------------------ #
        items = soup.find_all(class_=lambda c: c and "localPostExpanded" in c)
        if items:
            logger.debug(f"Strategy 2 (localPostExpanded) found {len(items)} items")
            return items

        # ------------------------------------------------------------------ #
        # Strategy 3 – ``data-sharing-url`` with lpsid (stable post id)       #
        # ------------------------------------------------------------------ #
        items = soup.find_all(attrs={"data-sharing-url": True})
        if items:
            logger.debug(f"Strategy 3 (data-sharing-url) found {len(items)} items")
            return items

        # ------------------------------------------------------------------ #
        # Strategy 4 – "From the owner" section (current Google Maps DOM)     #
        # ------------------------------------------------------------------ #
        owner_header = soup.find(string=lambda t: t and "From the owner" in t)
        if owner_header:
            # Walk up to find the container
            container = owner_header.parent
            for _ in range(5):
                if container and container.find(class_=lambda c: c and ("waIsr" in c or "SBD2Rc" in c)):
                    break
                container = container.parent if container else None
            
            if container:
                items = container.find_all("div", class_=lambda c: c and ("SBD2Rc" in c or "waIsr" in c))
                if items:
                    logger.debug(f"Strategy 4 (From the owner) found {len(items)} items")
                    return items

        # ------------------------------------------------------------------ #
        # Strategy 5 – ARIA label "update from" / "post from"                 #
        # ------------------------------------------------------------------ #
        items = soup.find_all(
            "div",
            attrs={
                "aria-label": lambda v: v and (
                    "update from" in v.lower() or "post from" in v.lower()
                )
            },
        )
        if items:
            logger.debug(f"Strategy 5 (aria-label update/post from) found {len(items)} items")
            return items

        # ------------------------------------------------------------------ #
        # Strategy 5 – ``TrG26d`` post-body class: grab the closest ancestor  #
        # that is likely a post container (walk up to a reasonable wrapper)   #
        # ------------------------------------------------------------------ #
        body_els = soup.find_all(class_=lambda c: c and "TrG26d" in c)
        if body_els:
            # Deduplicate by walking up to the first parent that seems like a
            # post card (has a meaningful set of child elements).
            containers = []
            seen_ids = set()
            for el in body_els:
                # Walk up at most 5 levels to find a suitable container
                candidate = el
                for _ in range(5):
                    parent = candidate.parent
                    if parent is None or parent.name in ("html", "body", "[document]"):
                        break
                    candidate = parent
                uid = id(candidate)
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    containers.append(candidate)
            if containers:
                logger.debug(f"Strategy 5 (TrG26d ancestor) found {len(containers)} items")
                return containers

        # ------------------------------------------------------------------ #
        # Strategy 6 – role="feed" structural fallback                        #
        # ------------------------------------------------------------------ #
        feed = soup.find("div", role="feed")
        if feed:
            children = feed.find_all("div", recursive=False)
            if children:
                logger.debug(f"Strategy 6 (role=feed children) found {len(children)} items")
                return children

        # ------------------------------------------------------------------ #
        # Strategy 7 – legacy ``ODSEW-BN9H-post`` class name                 #
        # ------------------------------------------------------------------ #
        items = soup.find_all("div", class_=lambda c: c and "ODSEW-BN9H-post" in c)
        if items:
            logger.debug(f"Strategy 7 (ODSEW-BN9H-post) found {len(items)} items")
            return items

        return []
