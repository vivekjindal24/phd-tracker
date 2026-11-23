"""Filling a publication from its DOI through Crossref (doi.py), against a fake Crossref."""

import httpx
import pytest

from app import doi
from tests.conftest import auth
from tests.test_naac import _publication
from tests.test_publications import modules_on  # noqa: F401

pytestmark = pytest.mark.usefixtures("modules_on")
URL = "/api/v1/publications/doi"
WORK = {
    "type": "journal-article",
    "title": ["Graph <i>neural</i> networks &amp; edges"],
    "author": [
        {"given": "Arun", "family": "Bhatt"},
        {"given": "Meera", "family": "Krishnan"},
        {"name": "The CSE Consortium"},
    ],
    "container-title": ["Journal of Graphs"],
    "ISSN": ["1234-5678"],
    "published-print": {"date-parts": [[2025, 3]]},
}


@pytest.fixture
def crossref(monkeypatch):
    asked = []

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.path)
        if request.url.path.endswith("/10.5555/missing"):
            return httpx.Response(404)
        if request.url.path.endswith("/10.5555/down"):
            return httpx.Response(503)
        return httpx.Response(200, json={"message": WORK})

    monkeypatch.setattr(doi, "TRANSPORT", httpx.MockTransport(answer))
    return asked


async def look_up(client, user, q):
    return await client.get(URL, params={"q": q}, headers=auth(user.id))


async def test_a_doi_fills_the_publication(client, world, crossref):
    res = await look_up(client, world.scholar_a1, "https://doi.org/10.5555/Graphs.2025.1")
    assert res.status_code == 200, res.text
    body = res.json()
    assert crossref == ["/works/10.5555/Graphs.2025.1"]  # only the DOI goes out
    assert body["doi"] == "10.5555/Graphs.2025.1"
    assert body["title"] == "Graph neural networks & edges"
    assert body["authors"] == "Arun Bhatt, Meera Krishnan, The CSE Consortium"
    assert (body["pub_type"], body["venue"], body["issn_isbn"]) == (
        "journal",
        "Journal of Graphs",
        "1234-5678",
    )
    assert body["pub_year"] == 2025 and body["already_recorded"] is False


async def test_a_doi_already_recorded_is_flagged(client, session, world, crossref):
    session.add(_publication(world, "Mine", doi="10.5555/graphs.2025.1"))
    await session.commit()
    res = await look_up(client, world.scholar_a1, "doi:10.5555/GRAPHS.2025.1")
    assert res.json()["already_recorded"] is True


async def test_what_crossref_cannot_answer(client, world, crossref):
    bad = await look_up(client, world.scholar_a1, "not a doi")
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "doi_invalid"
    assert crossref == []
    missing = await look_up(client, world.scholar_a1, "10.5555/missing")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "doi_not_found"
    down = await look_up(client, world.scholar_a1, "10.5555/down")
    assert down.status_code == 502 and down.json()["error"]["code"] == "doi_lookup_failed"


async def test_only_scholars_look_up(client, world, crossref):
    assert (await look_up(client, world.meera, "10.5555/x")).status_code == 403
