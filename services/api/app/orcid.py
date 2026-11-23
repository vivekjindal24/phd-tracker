"""List a researcher's works from their public ORCID record (owner, 2026-11-23), so a scholar can
bring in their papers at once. ORCID's summaries rarely carry authors or the venue, so each
chosen work is filled from Crossref through its DOI (doi.py); a work without a DOI is added by
hand. Only the ORCID iD leaves the server; no key is needed for public records."""

import asyncio
import logging
import re
import uuid
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import doi
from app.auth.principal import Principal
from app.crud import insert
from app.doi import USER_AGENT
from app.errors import ApiError
from app.models import Publication

log = logging.getLogger("anveshan.orcid")
ORCID = "https://pub.orcid.org/v3.0/"
TIMEOUT_S = 15
TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests put a fake ORCID here
ID_IN = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", re.IGNORECASE)


def _checksum_ok(orcid: str) -> bool:
    """ISO 7064 MOD 11-2, as ORCID defines its last character."""
    digits = orcid.replace("-", "")
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    check = (12 - total % 11) % 11
    return digits[-1].upper() == ("X" if check == 10 else str(check))


def normalise(raw: str) -> str:
    """The bare iD from '0000-0002-1825-0097' or its orcid.org link."""
    found = ID_IN.search(raw.strip())
    if found is None or not _checksum_ok(found.group(1)):
        raise ApiError(
            422,
            "orcid_invalid",
            "That is not an ORCID iD. It looks like 0000-0002-1825-0097.",
        )
    return found.group(1).upper()


def _doi(summary: dict[str, Any]) -> str | None:
    for ext in (summary.get("external-ids") or {}).get("external-id") or []:
        if ext.get("external-id-type") == "doi" and ext.get("external-id-relationship") == "self":
            value = (ext.get("external-id-normalized") or {}).get("value")
            return value or ext.get("external-id-value")
    return None


def _work(group: dict[str, Any]) -> dict[str, Any]:
    summary = group["work-summary"][0]  # ORCID lists the preferred source's version first
    year = ((summary.get("publication-date") or {}).get("year") or {}).get("value")
    title = ((summary.get("title") or {}).get("title") or {}).get("value") or "(untitled)"
    return {
        "put_code": summary["put-code"],
        "title": title,
        "year": int(year) if year else None,
        "kind": summary.get("type") or "other",
        "doi": _doi(summary),
    }


async def works(raw: str) -> list[dict[str, Any]]:
    orcid = normalise(raw)
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_S,
            transport=TRANSPORT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            res = await client.get(f"{ORCID}{orcid}/works")
    except httpx.HTTPError as exc:
        log.warning("ORCID works of %s failed: %s", orcid, exc)
        raise ApiError(
            502, "orcid_lookup_failed", "ORCID did not answer. Try again later."
        ) from exc
    if res.status_code == 404:
        raise ApiError(404, "orcid_not_found", f"ORCID has no public record for {orcid}.")
    try:
        res.raise_for_status()
        return [_work(g) for g in res.json().get("group") or []]
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        log.warning("ORCID works of %s: HTTP %s, %s", orcid, res.status_code, exc)
        raise ApiError(
            502, "orcid_lookup_failed", "ORCID did not answer. Try again later."
        ) from exc


# Crossref's public pool allows about one request at a time per client: ask it in turn.
CONCURRENT_LOOKUPS = 1


async def recorded_dois(session: AsyncSession, scholar_id: uuid.UUID) -> set[str]:
    rows = await session.scalars(
        select(func.lower(Publication.doi)).where(
            Publication.scholar_id == scholar_id,
            Publication.doi.is_not(None),
            Publication.deleted_at.is_(None),
        )
    )
    return set(rows)


def _incomplete(found: dict[str, Any]) -> str | None:
    missing = [k for k in ("title", "authors", "venue", "pub_year") if not found.get(k)]
    if missing:
        return f"Crossref lacks the {', '.join(m.replace('pub_', '') for m in missing)}"
    return None


async def import_dois(
    session: AsyncSession, principal: Principal, dois: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Each DOI, filled from Crossref, becomes the scholar's draft publication; a DOI already
    recorded, unknown to Crossref, or missing a required field is skipped with the reason."""
    assert principal.scholar_id is not None
    have = await recorded_dois(session, principal.scholar_id)
    unique: dict[str, str] = {}
    for d in dois:
        unique.setdefault(d.lower(), d)  # DOIs ignore case; keep the first spelling
    wanted = [d for key, d in unique.items() if key not in have]
    skipped = [{"doi": d, "reason": "Already recorded"} for key, d in unique.items() if key in have]
    gate = asyncio.Semaphore(CONCURRENT_LOOKUPS)

    async def fill(d: str) -> dict[str, Any] | ApiError:
        async with gate:
            try:
                return await doi.lookup(d)
            except ApiError as exc:
                return exc

    created = []
    for d, found in zip(wanted, await asyncio.gather(*(fill(d) for d in wanted)), strict=True):
        reason = found.message if isinstance(found, ApiError) else _incomplete(found)
        if reason:
            skipped.append({"doi": d, "reason": reason})
            continue
        assert isinstance(found, dict)
        pub = await insert(
            session, principal, Publication(scholar_id=principal.scholar_id, **found)
        )
        created.append({"id": pub.id, "title": pub.title})
    return {"created": created, "skipped": skipped}
