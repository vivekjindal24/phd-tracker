"""Reading the audit log (SECURITY.md §3): who did what to which record and when — never the
recorded values. The root admin, Research Office and Vice Chancellor read all of it; a
scoped admin only what concerns scholars in their subtree."""

from tests.conftest import auth

API = "/api/v1"


async def log(client, user, **params):
    return await client.get(f"{API}/audit-log", headers=auth(user.id), params=params)


async def seed(client, world) -> str:
    """A meeting with private minutes for scholar a1, and a register entry for scholar b1."""
    meeting = await client.post(
        f"{API}/meetings",
        headers=auth(world.meera.id),
        json={
            "scholar_id": str(world.s_a1.id),
            "meeting_date": "2026-03-05",
            "agenda": "Plan",
            "minutes": "Strictly private minutes",
        },
    )
    assert meeting.status_code == 201, meeting.text
    entry = await client.post(
        f"{API}/milestones",
        headers=auth(world.research_office.id),
        json={
            "scholar_id": str(world.s_b1.id),
            "milestone_type": "rac_review",
            "status": "Approved",
            "approval_body": "RAC",
        },
    )
    assert entry.status_code == 201, entry.text
    return meeting.json()["id"]


async def test_names_the_change_but_never_its_values(client, world):
    mid = await seed(client, world)
    await client.patch(
        f"{API}/meetings/{mid}", headers=auth(world.meera.id), json={"minutes": "Changed"}
    )
    res = await log(client, world.root_admin, table_name="meetings")
    assert res.status_code == 200, res.text
    update, insert = res.json()  # newest first
    assert (insert["action"], insert["actor"], insert["scholar"]["name"]) == (
        "insert",
        "Meera",
        "Scholar A1",
    )
    assert update["action"] == "update" and update["fields"] == ["minutes"]
    assert "private" not in res.text and "Changed" not in res.text


async def test_who_reads_how_much(client, world):
    await seed(client, world)
    for user in (world.root_admin, world.research_office, world.vice_chancellor):
        tables = {r["table_name"] for r in (await log(client, user)).json()}
        assert {"meetings", "milestones"} <= tables, user.email
    # The A1 admin sees what concerns A1's scholars, not B1's register entry.
    mine = (await log(client, world.admin_a1)).json()
    assert {r["table_name"] for r in mine} == {"meetings"}
    for user in (world.scholar_a1, world.sup_a2, world.dean_a, world.library, world.exam_office):
        assert (await log(client, user)).status_code == 403, user.email


async def test_filters(client, world):
    await seed(client, world)
    root = world.root_admin
    by_scholar = (await log(client, root, scholar_id=str(world.s_b1.id))).json()
    assert [r["table_name"] for r in by_scholar] == ["milestones"]
    by_actor = (await log(client, root, actor_id=str(world.meera.id))).json()
    assert {r["actor"] for r in by_actor} == {"Meera"}
    assert (await log(client, root, action="soft_delete")).json() == []
    assert (await log(client, root, date_from="2100-01-01")).json() == []
    assert len((await log(client, root, limit=1)).json()) == 1


async def test_drafts_stay_out_of_it(client, session, world):
    from tests.test_publications import enable

    await enable(session, "documents")
    doc = await client.post(
        f"{API}/documents",
        headers=auth(world.scholar_a1.id),
        json={"title": "Chapter 1", "doc_kind": "chapter"},
    )
    assert doc.status_code == 201, doc.text
    assert (await log(client, world.root_admin, table_name="documents")).json() == []
