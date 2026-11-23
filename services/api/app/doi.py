"""Fill a publication from its DOI (owner, 2026-11-22; stakeholder input D): Crossref's public
API answers with the title, authors, venue, ISSN/ISBN, year and type; the scholar checks them and
saves as usual. Only the DOI leaves the server. Indexing (Scopus, WoS, UGC-CARE) is not in
Crossref: the scholar ticks it and the Library verifies it."""

import asyncio
import html
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.errors import ApiError

log = logging.getLogger("anveshan.doi")
CROSSREF = "https://api.crossref.org/works/"
TIMEOUT_S = 10
USER_AGENT = "Anveshan/1.0 (university research records; DOI lookup)"
TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests put a fake Crossref here
DOI_IN = re.compile(r"(10\.\d{4,9}/\S{1,200})")
TAG = re.compile(r"<[^>]+>")
PUB_TYPES = {
    "journal-article": "journal",
    "proceedings-article": "conference",
    "book-chapter": "book_chapter",
    "book-part": "book_chapter",
    "book-section": "book_chapter",
}
BUSY = 429  # Crossref's public pool sheds load; one wait-and-retry usually succeeds
MAX_RETRY_WAIT_S = 5.0
MAX_AUTHORS_CHARS = 2000
MAX_TITLE_CHARS = 500


def normalise(raw: str) -> str:
    """The bare DOI from what a scholar pastes: '10.x/y', 'doi:10.x/y' or a doi.org link."""
    found = DOI_IN.search(raw.strip())
    if found is None:
        raise ApiError(422, "doi_invalid", "That is not a DOI. A DOI looks like 10.1234/abcd.5678.")
    return found.group(1).rstrip(".,;")


def _text(value: str) -> str:
    return " ".join(html.unescape(TAG.sub("", value)).split())


def _first(work: dict[str, Any], key: str) -> str | None:
    values = work.get(key) or []
    return _text(values[0]) if values else None


def _year(work: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = (work.get(key) or {}).get("date-parts") or [[None]]
        if parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def _authors(work: dict[str, Any]) -> str:
    names = []
    for a in work.get("author") or []:
        name = " ".join(p for p in (a.get("given"), a.get("family")) if p) or a.get("name")
        if name:
            names.append(_text(name))
    return ", ".join(names)[:MAX_AUTHORS_CHARS]


def details(doi: str, work: dict[str, Any]) -> dict[str, Any]:
    """Crossref's record in the publication form's terms; what Crossref lacks stays empty."""
    pub_type = PUB_TYPES.get(work.get("type", ""), "journal")
    venue = _first(work, "container-title") or _text(work.get("publisher") or "")
    return {
        "doi": doi,
        "title": (_first(work, "title") or "")[:MAX_TITLE_CHARS],
        "authors": _authors(work),
        "pub_type": pub_type,
        "venue": venue[:MAX_TITLE_CHARS],
        "issn_isbn": _first(work, "ISSN") or _first(work, "ISBN"),
        "pub_year": _year(work),
        "pub_status": "published",
    }


async def lookup(raw: str) -> dict[str, Any]:
    doi = normalise(raw)
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_S, transport=TRANSPORT, headers={"User-Agent": USER_AGENT}
        ) as client:
            url = CROSSREF + quote(doi, safe="/")
            res = await client.get(url)
            if res.status_code == BUSY:
                wait = res.headers.get("Retry-After", "1")
                await asyncio.sleep(min(float(wait) if wait.isdigit() else 1.0, MAX_RETRY_WAIT_S))
                res = await client.get(url)
    except httpx.HTTPError as exc:
        log.warning("Crossref lookup of %s failed: %s", doi, exc)
        raise ApiError(
            502, "doi_lookup_failed", "Crossref did not answer. Fill in the details by hand."
        ) from exc
    if res.status_code == 404:
        raise ApiError(
            404, "doi_not_found", f"Crossref has no record of {doi}. Check it, or fill in by hand."
        )
    try:
        res.raise_for_status()
        work = res.json()["message"]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("Crossref lookup of %s: HTTP %s, %s", doi, res.status_code, exc)
        raise ApiError(
            502, "doi_lookup_failed", "Crossref did not answer. Fill in the details by hand."
        ) from exc
    return details(doi, work)
