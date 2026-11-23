"""Bringing a scholar's works in from their public ORCID record (orcid.py): listed from ORCID,
filled from Crossref by DOI, saved as drafts. Both services are faked."""

import httpx
import pytest
from sqlalchemy import select

from app import doi, orcid
from app.models import Publication
from tests.conftest import auth
from tests.test_naac import _publication
from tests.test_publications import modules_on  # noqa: F401

pytestmark = pytest.mark.usefixtures("modules_on")
API = "/api/v1/publications"
ID = "0000-0002-1825-0097"  # ORCID's own test researcher


def summary(code, title, kind="journal-article", year="2024", doi_value=None):
    ids = (
        [
            {
                "external-id-type": "doi",
                "external-id-value": doi_value,
                "external-id-relationship": "self",
            }
        ]
        if doi_value
        else []
    )
    return {
        "work-summary": [
            {
                "put-code": code,
                "type": kind,
                "title": {"title": {"value": title}},
                "publication-date": {"year": {"value": year}},
                "external-ids": {"external-id": ids},
            }
        ]
    }


GROUPS = [
    summary(1, "On graphs", doi_value="10.5555/graphs"),
    summary(2, "Recorded already", doi_value="10.5555/MINE"),
    summary(3, "A poster without a DOI", kind="conference-poster"),
]


def crossref_work(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/10.5555/unknown"):
        return httpx.Response(404)
    if request.url.path.endswith("/10.5555/noauthors"):
        return httpx.Response(200, json={"message": {"title": ["T"], "container-title": ["J"]}})
    return httpx.Response(
        200,
        json={
            "message": {
                "type": "journal-article",
                "title": ["On graphs"],
                "author": [{"given": "Priya", "family": "Sharma"}],
                "container-title": ["J. Graphs"],
                "issued": {"date-parts": [[2024]]},
            }
        },
    )


@pytest.fixture
def services(monkeypatch):
    def orcid_answer(request: httpx.Request) -> httpx.Response:
        if ID not in request.url.path:
            return httpx.Response(404)
        return httpx.Response(200, json={"group": GROUPS})

    monkeypatch.setattr(orcid, "TRANSPORT", httpx.MockTransport(orcid_answer))
    monkeypatch.setattr(doi, "TRANSPORT", httpx.MockTransport(crossref_work))


async def test_works_are_listed_with_what_is_already_recorded(client, session, world, services):
    session.add(_publication(world, "Mine", doi="10.5555/mine"))
    await session.commit()
    res = await client.get(
        f"{API}/orcid", params={"q": f"https://orcid.org/{ID}"}, headers=auth(world.scholar_a1.id)
    )
    assert res.status_code == 200, res.text
    assert [(w["title"], w["doi"], w["already_recorded"]) for w in res.json()] == [
        ("On graphs", "10.5555/graphs", False),
        ("Recorded already", "10.5555/MINE", True),
        ("A poster without a DOI", None, False),
    ]


async def test_an_orcid_id_is_checked_before_asking(client, world, services):
    for bad in ("0000-0002-1825-0098", "not an id"):  # wrong check digit; no iD at all
        res = await client.get(f"{API}/orcid", params={"q": bad}, headers=auth(world.scholar_a1.id))
        assert res.status_code == 422 and res.json()["error"]["code"] == "orcid_invalid"
    gone = await client.get(
        f"{API}/orcid", params={"q": "0000-0001-5109-3700"}, headers=auth(world.scholar_a1.id)
    )
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "orcid_not_found"


async def test_chosen_dois_become_drafts(client, session, world, services):
    session.add(_publication(world, "Mine", doi="10.5555/mine"))
    await session.commit()
    res = await client.post(
        f"{API}/import",
        headers=auth(world.scholar_a1.id),
        json={
            "dois": [
                "10.5555/graphs",
                "10.5555/GRAPHS",  # the same DOI twice
                "10.5555/MINE",
                "10.5555/unknown",
                "10.5555/noauthors",
            ]
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert [c["title"] for c in body["created"]] == ["On graphs"]
    reasons = {s["doi"]: s["reason"] for s in body["skipped"]}
    assert reasons["10.5555/MINE"] == "Already recorded"
    assert "no record" in reasons["10.5555/unknown"]
    assert "authors" in reasons["10.5555/noauthors"]
    pub = await session.scalar(select(Publication).where(Publication.doi == "10.5555/graphs"))
    assert pub.state == "draft" and pub.authors == "Priya Sharma" and pub.indexing == []


async def test_only_scholars_import(client, world, services):
    res = await client.post(
        f"{API}/import", headers=auth(world.meera.id), json={"dois": ["10.5555/graphs"]}
    )
    assert res.status_code == 403
