"""The search box and department filter shared by every list of scholars' records
(scope.narrow_to_scholars): they narrow what the caller already sees, never widen it."""

import pytest

from app.main import app
from tests.conftest import auth
from tests.test_publications import enable

LISTS = [
    "scholars",
    "reports",
    "meetings",
    "milestones",
    "publications",
    "conferences",
    "fellowships",
    "theses",
]

PAGED = [
    *LISTS,
    "faculty",
    "seminars",
    "projects",
    "admissions",
    "documents",
    "audit-log",
]


@pytest.fixture
async def meeting(client, session, world):
    await enable(session, "publications", "conferences", "fellowships", "documents")
    res = await client.post(
        "/api/v1/meetings",
        headers=auth(world.meera.id),
        json={"scholar_id": str(world.s_a1.id), "meeting_date": "2026-01-05", "agenda": "Plan"},
    )
    assert res.status_code == 201, res.text


async def _count(client, user, path: str, **params) -> int:
    res = await client.get(f"/api/v1/{path}", headers=auth(user.id), params=params)
    assert res.status_code == 200, f"{path} {params}: {res.text}"
    return len(res.json())


async def test_meetings_are_found_by_name_roll_number_and_unit(client, world, meeting):
    office = world.research_office
    assert await _count(client, office, "meetings", q="phd-a1-001") == 1
    assert await _count(client, office, "meetings", q=world.scholar_a1.full_name[:6]) == 1
    assert await _count(client, office, "meetings", q="PHD-B1") == 0
    assert await _count(client, office, "meetings", q="%") == 0
    assert await _count(client, office, "meetings", unit_id=str(world.school_a.id)) == 1  # subtree
    assert await _count(client, office, "meetings", unit_id=str(world.b1.id)) == 0


@pytest.mark.parametrize("path", LISTS)
async def test_every_list_takes_the_two_filters(client, world, meeting, path):
    office = world.research_office
    everything = await _count(client, office, path)
    assert await _count(client, office, path, q="no-such-scholar-zzz") == 0
    in_a = await _count(client, office, path, unit_id=str(world.school_a.id))
    in_b = await _count(client, office, path, unit_id=str(world.school_b.id))
    assert in_a + in_b == everything


async def test_a_filter_never_widens_scope(client, world, meeting):
    # The head of B1 asks for School A's meetings: the filter cannot show what scope hides.
    assert await _count(client, world.hod_b1, "meetings", unit_id=str(world.school_a.id)) == 0
    assert await _count(client, world.hod_b1, "meetings", q="phd-a1-001") == 0


def test_every_list_the_web_pages_through_takes_an_offset():
    """The web reads these a page at a time (usePagedFetch); a list that ignored `offset`
    would repeat its first page under "Show more"."""
    paths = app.openapi()["paths"]
    for name in PAGED:
        params = {p["name"] for p in paths[f"/api/v1/{name}"]["get"]["parameters"]}
        assert {"limit", "offset"} <= params, name


async def test_mine_keeps_only_the_callers_own_scholars(client, world):
    """The meeting form's picker: a supervisor's scholars, never an admin's whole unit."""
    mine = await client.get("/api/v1/scholars?mine=true", headers=auth(world.meera.id))
    assert mine.status_code == 200, mine.text
    assert str(world.s_a1.id) in {s["id"] for s in mine.json()}
    admin = await client.get("/api/v1/scholars?mine=true", headers=auth(world.admin_a1.id))
    assert admin.json() == []
    own = await client.get("/api/v1/scholars?mine=true", headers=auth(world.scholar_a1.id))
    assert [s["id"] for s in own.json()] == [str(world.s_a1.id)]
