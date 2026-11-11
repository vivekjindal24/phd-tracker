"""The search box and department filter shared by every list of scholars' records
(scope.narrow_to_scholars): they narrow what the caller already sees, never widen it."""

import pytest

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
