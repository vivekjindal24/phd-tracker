"""Publications through their chain (PRD M1, UX Flow 7) and conferences (PRD M2)."""

from datetime import date

import pytest
from sqlalchemy import update

from app.models import Module
from tests.conftest import auth

PUB = {
    "title": "Graph learning for crop yield",
    "authors": "A. Scholar, M. Iyer",
    "pub_type": "journal",
    "venue": "Journal of Things",
    "issn_isbn": "1234-5678",
    "indexing": ["scopus"],
    "doi": "10.1234/jot.2025.17",
    "pub_year": 2025,
    "pub_status": "published",
}


async def enable(session, *keys: str) -> None:
    await session.execute(update(Module).where(Module.key.in_(keys)).values(enabled=True))
    await session.commit()


@pytest.fixture
async def modules_on(session, world):
    await enable(session, "publications", "conferences")


async def _create(client, world, **over):
    res = await client.post(
        "/api/v1/publications", headers=auth(world.scholar_a1.id), json=PUB | over
    )
    assert res.status_code == 201, res.text
    return res.json()


async def _act(client, user, pub_id, action, body=None):
    return await client.post(
        f"/api/v1/items/publication/{pub_id}/{action}", headers=auth(user.id), json=body or {}
    )


async def test_disabled_module_is_404_everywhere(client, world):
    res = await client.get("/api/v1/publications", headers=auth(world.scholar_a1.id))
    assert res.status_code == 404 and res.json()["error"]["code"] == "module_disabled"
    res = await client.get("/api/v1/conferences", headers=auth(world.scholar_a1.id))
    assert res.status_code == 404


async def test_full_chain_with_library_verification(client, world, modules_on):
    pub = await _create(client, world)
    assert pub["state"] == "draft" and [s["kind"] for s in pub["chain"]] == [
        "supervisor",
        "library",
        "research_office",
    ]
    assert (await _act(client, world.scholar_a1, pub["id"], "submit")).status_code == 200
    # Library may not verify before its step.
    early = await client.put(
        f"/api/v1/publications/{pub['id']}/verification",
        headers=auth(world.library.id),
        json={"indexing": ["wos"], "doi": None},
    )
    assert early.status_code == 422
    assert (await _act(client, world.meera, pub["id"], "approve")).status_code == 200
    verified = await client.put(
        f"/api/v1/publications/{pub['id']}/verification",
        headers=auth(world.library.id),
        json={"indexing": ["scopus", "ugc_care"], "doi": "10.1234/jot.2025.17"},
    )
    assert verified.status_code == 200
    assert verified.json()["content"]["indexing"] == ["scopus", "ugc_care"]
    assert (await _act(client, world.library, pub["id"], "approve")).status_code == 200
    done = await _act(client, world.research_office, pub["id"], "approve")
    assert done.json()["state"] == "approved"
    # Approved is immutable, for the author too.
    res = await client.patch(
        f"/api/v1/publications/{pub['id']}",
        headers=auth(world.scholar_a1.id),
        json={"title": "Changed"},
    )
    assert res.status_code == 422


async def test_library_queue_shows_publications(client, world, modules_on):
    pub = await _create(client, world)
    await _act(client, world.scholar_a1, pub["id"], "submit")
    await _act(client, world.meera, pub["id"], "approve")
    queue = (await client.get("/api/v1/queue", headers=auth(world.library.id))).json()
    assert [(q["item_type"], q["step"]) for q in queue] == [("publication", "Library")]


async def test_scope_negatives(client, world, modules_on):
    pub = await _create(client, world)
    for user in (world.scholar_a2, world.hod_a2, world.hod_b1, world.exam_office):
        res = await client.get(f"/api/v1/items/publication/{pub['id']}", headers=auth(user.id))
        assert res.status_code == 403, user.email
    for user in (world.meera, world.dean_a, world.library, world.research_office):
        res = await client.get(f"/api/v1/items/publication/{pub['id']}", headers=auth(user.id))
        assert res.status_code == 200, user.email
    listed = await client.get("/api/v1/publications", headers=auth(world.hod_b1.id))
    assert listed.json() == []


async def test_only_scholars_create_and_bad_doi_is_rejected(client, world, modules_on):
    res = await client.post("/api/v1/publications", headers=auth(world.meera.id), json=PUB)
    assert res.status_code == 403
    res = await client.post(
        "/api/v1/publications", headers=auth(world.scholar_a1.id), json=PUB | {"doi": "nope"}
    )
    assert res.status_code == 422


async def test_files_attach_only_while_editable(client, world, modules_on):
    pub = await _create(client, world)
    upload = {
        "table_name": "publications",
        "record_id": pub["id"],
        "file_name": "paper.pdf",
        "content_type": "application/pdf",
        "size_bytes": 1000,
    }
    other = await client.post("/api/v1/files/uploads", headers=auth(world.meera.id), json=upload)
    assert other.status_code == 422  # not the author
    ok = await client.post("/api/v1/files/uploads", headers=auth(world.scholar_a1.id), json=upload)
    assert ok.status_code == 201
    await _act(client, world.scholar_a1, pub["id"], "submit")
    late = await client.post(
        "/api/v1/files/uploads", headers=auth(world.scholar_a1.id), json=upload
    )
    assert late.status_code == 422


async def test_comments_timeline_search_dashboard(client, world, modules_on):
    pub = await _create(client, world)
    res = await client.post(
        "/api/v1/comments",
        headers=auth(world.meera.id),
        json={"table_name": "publications", "record_id": pub["id"], "body": "Cite the 2023 work."},
    )
    assert res.status_code == 201
    denied = await client.get(
        "/api/v1/comments",
        headers=auth(world.scholar_a2.id),
        params={"table_name": "publications", "record_id": pub["id"]},
    )
    assert denied.status_code == 403
    timeline = await client.get(
        f"/api/v1/scholars/{world.s_a1.id}/timeline", headers=auth(world.meera.id)
    )
    assert any(e["kind"] == "publication" for e in timeline.json())
    found = await client.get(
        "/api/v1/search", headers=auth(world.dean_a.id), params={"q": "crop yield"}
    )
    assert [p["title"] for p in found.json()["publications"]] == [PUB["title"]]
    nothing = await client.get(
        "/api/v1/search", headers=auth(world.hod_b1.id), params={"q": "crop yield"}
    )
    assert nothing.json()["publications"] == []
    home = await client.get("/api/v1/dashboard", headers=auth(world.scholar_a1.id))
    scholar = home.json()["scholar"]
    assert scholar["approved_publications"] == 0
    assert [i["item_type"] for i in scholar["in_progress"]] == ["publication"]


CONF = {
    "event_name": "ICML 2025",
    "event_type": "paper_presented",
    "event_date": "2025-07-14",
    "place": "Vancouver",
    "title": "Graph learning for crop yield",
}


async def test_conferences_owned_by_the_scholar(client, world, modules_on):
    res = await client.post("/api/v1/conferences", headers=auth(world.scholar_a1.id), json=CONF)
    assert res.status_code == 201 and res.json()["can_edit"] is True
    cid = res.json()["id"]
    seen = await client.get("/api/v1/conferences", headers=auth(world.meera.id))
    assert [(c["event_name"], c["can_edit"]) for c in seen.json()] == [("ICML 2025", False)]
    assert (await client.get("/api/v1/conferences", headers=auth(world.hod_b1.id))).json() == []
    for user in (world.meera, world.scholar_a2):
        res = await client.patch(
            f"/api/v1/conferences/{cid}", headers=auth(user.id), json={"place": "x"}
        )
        assert res.status_code == 403
    res = await client.patch(
        f"/api/v1/conferences/{cid}",
        headers=auth(world.scholar_a1.id),
        json={"event_date": "2025-07-15"},
    )
    assert res.json()["event_date"] == date(2025, 7, 15).isoformat()
    assert (
        await client.delete(f"/api/v1/conferences/{cid}", headers=auth(world.scholar_a1.id))
    ).status_code == 204
    assert (await client.get("/api/v1/conferences", headers=auth(world.meera.id))).json() == []
