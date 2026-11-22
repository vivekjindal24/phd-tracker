"""The gates a thesis clears before it moves on (thesis_gates.py): minimum duration and
publications at the scholar's submit, the plagiarism limit at the Library's approval."""

from datetime import date

import pytest

from app.models import Scholar
from tests.conftest import auth
from tests.test_naac import _publication
from tests.test_thesis import act, documents_on, new_thesis, ready_file  # noqa: F401

API = "/api/v1"
pytestmark = pytest.mark.usefixtures("documents_on")


async def settings(client, world, **body):
    res = await client.patch(f"{API}/settings", headers=auth(world.root_admin.id), json=body)
    assert res.status_code == 200, res.text


async def gates(client, world):
    res = await client.get(f"{API}/theses/gates/mine", headers=auth(world.scholar_a1.id))
    assert res.status_code == 200, res.text
    return res.json()


async def submittable(client, session, world) -> str:
    tid = await new_thesis(client, session, world)
    await ready_file(session, world.scholar_a1, "thesis_submissions", tid)
    return tid


async def test_not_before_the_minimum_duration(client, session, world):
    scholar = await session.get(Scholar, world.s_a1.id)
    scholar.admission_date = date.today().replace(year=date.today().year - 1, day=1)
    await session.commit()
    tid = await submittable(client, session, world)
    assert [g["met"] for g in await gates(client, world)] == [False]
    res = await act(client, world.scholar_a1, tid, "submit")
    assert res.status_code == 409 and res.json()["error"]["code"] == "thesis_gate"
    assert "can be submitted from" in res.json()["error"]["message"]

    await settings(client, world, min_duration_years=0)  # the university's own rule: none
    assert await gates(client, world) == []
    assert (await act(client, world.scholar_a1, tid, "submit")).status_code == 200


async def test_enough_approved_publications(client, session, world):
    await settings(client, world, min_publications=2, publications_indexed_only=True)
    session.add_all(
        [
            _publication(world, "Indexed, published"),
            _publication(world, "Not indexed", indexing=[]),
            _publication(world, "Only submitted", pub_status="submitted"),
            _publication(world, "A draft", state="draft"),
        ]
    )
    await session.commit()
    tid = await submittable(client, session, world)
    gate = (await gates(client, world))[-1]
    assert not gate["met"] and gate["detail"].startswith("1 approved")
    res = await act(client, world.scholar_a1, tid, "submit")
    assert res.status_code == 409 and "Scopus" in res.json()["error"]["message"]

    await settings(client, world, publications_indexed_only=False)  # any approved paper counts
    assert (await act(client, world.scholar_a1, tid, "submit")).status_code == 200


async def test_the_library_cannot_approve_above_the_plagiarism_limit(client, session, world):
    tid = await submittable(client, session, world)
    for user in (world.scholar_a1, world.meera, world.admin_a1):
        action = "submit" if user is world.scholar_a1 else "approve"
        assert (await act(client, user, tid, action)).status_code == 200

    async def score(value):
        res = await client.put(
            f"{API}/theses/{tid}/plagiarism",
            headers=auth(world.library.id),
            json={"plagiarism_tool": "Turnitin", "plagiarism_score": value},
        )
        assert res.status_code == 200, res.text

    await score(12.5)
    res = await act(client, world.library, tid, "approve")
    assert res.status_code == 422 and "above the university's limit of 10%" in res.text
    await score(10)  # at the limit is within it
    assert (await act(client, world.library, tid, "approve")).status_code == 200
