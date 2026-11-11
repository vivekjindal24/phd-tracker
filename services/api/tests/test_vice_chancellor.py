"""The Vice Chancellor (PRD §4, SECURITY.md §3): reads the whole university, writes nothing,
and decides only where a chain names the Vice Chancellor step."""

from sqlalchemy import select

from app.models import Scholar
from tests.conftest import auth
from tests.test_thesis import act, documents_on, new_thesis, ready_file  # noqa: F401

VC_CHAIN = ["supervisor", "department", "library", "exam_office", "vice_chancellor"]


async def test_reads_the_whole_university_and_writes_nothing(client, session, world):
    vc = auth(world.vice_chancellor.id)
    scholars = await client.get("/api/v1/scholars", headers=vc)
    assert len(scholars.json()) == 4
    assert (await client.get("/api/v1/leadership", headers=vc)).status_code == 200
    assert (await client.get("/api/v1/users", headers=vc)).status_code == 200
    scholar_id = await session.scalar(
        select(Scholar.id).where(Scholar.user_id == world.scholar_b1.id)
    )
    write = await client.post(
        "/api/v1/milestones",
        headers=vc,
        json={
            "scholar_id": str(scholar_id),
            "milestone_type": "rac_review",
            "status": "Approved",
            "approval_body": "RAC",
        },
    )
    assert write.status_code == 403
    settings = await client.patch("/api/v1/settings", headers=vc, json={"require_no_dues": True})
    assert settings.status_code == 403


async def test_home_shows_the_university(client, world):
    res = await client.get("/api/v1/dashboard", headers=auth(world.vice_chancellor.id))
    assert res.status_code == 200, res.text
    (unit,) = res.json()["units"]
    assert unit["roles"] == ["vice_chancellor"] and unit["total_scholars"] == 4


async def test_minutes_follow_the_unit_heads_tick(client, world):
    body = {
        "scholar_id": str(world.s_a1.id),
        "meeting_date": "2026-01-05",
        "agenda": "Plan",
        "minutes": "Secret minutes",
    }
    mid = (await client.post("/api/v1/meetings", headers=auth(world.meera.id), json=body)).json()[
        "id"
    ]
    vc = auth(world.vice_chancellor.id)
    assert (await client.get(f"/api/v1/meetings/{mid}", headers=vc)).json()["minutes"] is None
    shared = await client.patch(
        f"/api/v1/meetings/{mid}",
        headers=auth(world.meera.id),
        json={"shared_with": ["unit_heads"]},
    )
    assert shared.status_code == 200, shared.text
    seen = (await client.get(f"/api/v1/meetings/{mid}", headers=vc)).json()
    assert seen["minutes"] == "Secret minutes"


async def test_selects_examiners_at_their_step(client, session, world, documents_on):  # noqa: F811
    chain = await client.put(
        "/api/v1/settings/chains/thesis_submission",
        headers=auth(world.root_admin.id),
        json={"steps": [{"kind": k} for k in VC_CHAIN]},
    )
    assert chain.status_code == 200, chain.text
    tid = await new_thesis(client, session, world)
    await ready_file(session, world.scholar_a1, "thesis_submissions", tid)
    for user in (world.scholar_a1, world.meera, world.admin_a1):
        await act(client, user, tid, "submit" if user is world.scholar_a1 else "approve")
    await client.put(
        f"/api/v1/theses/{tid}/plagiarism",
        headers=auth(world.library.id),
        json={"plagiarism_tool": "Turnitin", "plagiarism_score": 6.5},
    )
    await act(client, world.library, tid, "approve")
    panel = {"examiners": "Prof. X; Prof. Y; Prof. Z"}
    exams = auth(world.exam_office.id)
    assert (
        await client.put(f"/api/v1/theses/{tid}/examiners", headers=exams, json=panel)
    ).is_success
    at_vc = await act(client, world.exam_office, tid, "approve")
    assert at_vc.json()["waiting_on"] == "Vice Chancellor"

    # The panel is now the Vice Chancellor's: the Exam Office can no longer change it.
    late = await client.put(f"/api/v1/theses/{tid}/examiners", headers=exams, json=panel)
    assert late.status_code == 422
    vc = auth(world.vice_chancellor.id)
    chosen = await client.put(
        f"/api/v1/theses/{tid}/examiners", headers=vc, json={"examiners": "Prof. X; Prof. Z"}
    )
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["content"]["examiners"] == "Prof. X; Prof. Z"
    done = await act(client, world.vice_chancellor, tid, "approve")
    assert done.json()["state"] == "approved"


async def test_only_the_university_admin_appoints_and_lists_role_holders(client, world):
    root = auth(world.root_admin.id)
    holders = await client.get("/api/v1/role-holders", headers=root)
    assert holders.status_code == 200, holders.text
    rows = holders.json()
    assert {h["role"] for h in rows if h["unit_id"] is None} == {
        "vice_chancellor",
        "research_office",
        "exam_office",
        "library",
    }
    # Unit heads and admins come with their unit, so the screen can list them under it.
    by_unit = {(h["user_id"], h["role"]): h["unit_id"] for h in rows if h["unit_id"]}
    assert by_unit[(str(world.dean_a.id), "unit_head")] == str(world.school_a.id)
    assert (str(world.admin_a1.id), "admin") in by_unit
    for user in (world.vice_chancellor, world.research_office, world.dean_a):
        assert (await client.get("/api/v1/role-holders", headers=auth(user.id))).status_code == 403
    grant = await client.post(
        "/api/v1/role-assignments",
        headers=auth(world.vice_chancellor.id),
        json={"user_id": str(world.dean_a.id), "role": "vice_chancellor"},
    )
    assert grant.status_code == 403
