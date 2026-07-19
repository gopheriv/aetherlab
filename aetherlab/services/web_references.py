"""Web reference providers — references from beyond the local library.

Currently a Wikipedia provider that fetches relevant article intros through the
public MediaWiki API. Pure stdlib (urllib), short-timeout, and *never raises*:
any failure (offline, rate-limited, malformed) returns an empty list so the
pipeline degrades to local-library-only references.

Results are returned as RagHit objects with origin="web" and a source_label
(the article title); source_path is the article URL, which the reference card
opens in the browser.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

from aetherlab.core.models import RagHit

log = logging.getLogger(__name__)

_UA = {"User-Agent": "AetherLab/1.0 (physics workbench; educational; +https://openstax.org)"}
_WIKI_API = "https://en.wikipedia.org/w/api.php"

# Bias the query toward the physical sciences so keyword collisions ("field",
# "spring", "current") resolve to the physics article rather than a disambig.
_DOMAIN_HINT = "physics"


def _http_get_json(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class WikipediaReferenceProvider:
    """Fetch encyclopedic references for a set of solver keywords."""

    def __init__(self, timeout: float = 8.0, lang: str = "en") -> None:
        self.timeout = timeout
        self.api = f"https://{lang}.wikipedia.org/w/api.php"

    def search(self, keywords: list[str], limit: int = 3) -> list[RagHit]:
        """Return up to `limit` Wikipedia references. Never raises."""
        terms = [k.strip() for k in keywords if k.strip()]
        if not terms:
            return []
        query = " ".join(terms[:4])
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f"{query} {_DOMAIN_HINT}",
            "gsrlimit": limit,
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "inprop": "url",
            "exchars": 460,
            "redirects": 1,
        }
        url = f"{self.api}?{urllib.parse.urlencode(params)}"
        try:
            data = _http_get_json(url, self.timeout)
        except Exception as exc:  # noqa: BLE001 — web refs must never break a run
            log.info("Wikipedia reference fetch failed: %s", exc)
            return []

        if not isinstance(data, dict):
            return []
        query_data = data.get("query")
        if not isinstance(query_data, dict):
            return []
        pages = query_data.get("pages")
        if not isinstance(pages, dict):
            return []
        # MediaWiki returns pages keyed by id; 'index' preserves search rank.
        ordered = sorted(
            (page for page in pages.values() if isinstance(page, dict)),
            key=_page_rank,
        )
        hits: list[RagHit] = []
        for i, page in enumerate(ordered[:limit]):
            title = str(page.get("title", "")).strip()
            extract = str(page.get("extract", "")).strip()
            page_url = page.get("fullurl") or (
                "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
            )
            if not title or not extract:
                continue
            # Rank → score in (0, 1]; the top hit reads ~0.9, tapering down.
            score = round(0.9 - 0.12 * i, 3)
            hits.append(
                RagHit(
                    source_path=str(page_url),
                    page_number=None,
                    score=max(score, 0.3),
                    excerpt=_trim(extract),
                    source_label=title,
                    origin="web",
                )
            )
        return hits


def _page_rank(page: dict) -> float:
    try:
        return float(page.get("index", 1_000))
    except (TypeError, ValueError):
        return 1_000.0


def fetch_web_references(keywords: list[str], settings, limit: int = 3) -> list[RagHit]:
    """Convenience entry: honor the settings toggle, return [] when disabled."""
    if not getattr(settings, "web_references", True):
        return []
    provider = WikipediaReferenceProvider(
        timeout=float(getattr(settings, "web_ref_timeout", 8.0))
    )
    return provider.search(keywords, limit=limit)


def _trim(text: str, limit: int = 420) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
