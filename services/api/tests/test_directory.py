"""Directory: scoped lists, supervisor assignment under UGC caps, co-supervision (PRD F6)."""

from sqlalchemy import select, update

from app.models import Notification, Settings
from tests.conftest import auth


async def _rolls(client, user, query=""):
    res = await client.get(f"/api/v1/scholars{query}", headers=auth(user.id))
    assert res.status_code == 200, res.text
    return {s["roll_number"] for s in res.json()}


async def test_lists_are_scoped_per_role(client, world):
    assert await _rolls(client, world.scholar_a1) == {"PHD-A1-001"}
    assert await _rolls(client, world.hod_a2) == {"PHD-A2-001"}
    assert await _rolls(client, world.dean_a) == {"PHD-A1-001", "PHD-A1-002", "PHD-A2-001"}
    assert len(await _rolls(client, world.library)) == 4


async def test_unit_filter_includes_sub_units(client, world):
    rolls = await _rolls(client, world.research_office, f"?unit_id={world.school_a.id}")
    assert rolls == {"PHD-A1-001", "PHD-A1-002", "PHD-A2-001"}


async def test_search_by_roll_number_prefix(client, world):
    assert await _rolls(client, world.root_admin, "?q=PHD-A1") == {"PHD-A1-001", "PHD-A1-002"}


async def test_other_scholar_detail_is_403(client, world):
    res = await client.get(f"/api/v1/scholars/{world.s_b1.id}", headers=auth(world.scholar_a1.id))
    assert res.status_code == 403


async def test_co_supervisor_hidden_while_setting_off(client, world, session):
    url = f"/api/v1/scholars/{world.s_a1.id}"
    assert (await client.get(url, headers=auth(world.meera.id))).json()["co_supervisor"] is None
    await session.execute(update(Settings).values(co_supervision="view"))
    await session.commit()
    body = (await client.get(url, headers=auth(world.meera.id))).json()
    assert body["co_supervisor"]["name"] == "Co Sup"


async def test_admin_assigns_cross_unit_supervisor_and_both_are_told(client, world, session):
    res = await client.put(
        f"/api/v1/scholars/{world.s_a1b.id}/supervisor",
        json={"faculty_id": str(world.sup_b1_faculty.id)},
        headers=auth(world.admin_a1.id),
    )
    assert res.status_code == 200 and res.json()["supervisor"]["name"] == "Sup B1"
    told = set(await session.scalars(select(Notification.user_id)))
    assert {world.sup_b1.id, world.scholar_a1b.id} <= told


async def test_ugc_cap_blocks_over_assignment(client, world):
    # Lower Meera's cap to her current load (1), then try to give her another scholar.
    cap = await client.patch(
        f"/api/v1/faculty/{world.meera_faculty.id}",
        json={"max_scholars": 1},
        headers=auth(world.admin_a1.id),
    )
    assert cap.status_code == 200 and cap.json()["load"] == 1
    res = await client.put(
        f"/api/v1/scholars/{world.s_a1b.id}/supervisor",
        json={"faculty_id": str(world.meera_faculty.id)},
        headers=auth(world.admin_a1.id),
    )
    assert (res.status_code, res.json()["error"]["code"]) == (409, "supervisor_cap_exceeded")


async def test_only_admin_over_the_unit_assigns(client, world):
    body = {"faculty_id": str(world.sup_a2_faculty.id)}
    hod = await client.put(
        f"/api/v1/scholars/{world.s_a2.id}/supervisor", json=body, headers=auth(world.hod_a2.id)
    )
    assert hod.status_code == 403
    other_unit = await client.put(
        f"/api/v1/scholars/{world.s_a2.id}/supervisor", json=body, headers=auth(world.admin_a1.id)
    )
    assert other_unit.status_code == 403


async def test_non_supervising_faculty_cannot_be_assigned(client, world):
    await client.patch(
        f"/api/v1/faculty/{world.co_sup_faculty.id}",
        json={"can_supervise": False},
        headers=auth(world.root_admin.id),
    )
    res = await client.put(
        f"/api/v1/scholars/{world.s_a2.id}/supervisor",
        json={"faculty_id": str(world.co_sup_faculty.id)},
        headers=auth(world.root_admin.id),
    )
    assert res.json()["error"]["code"] == "cannot_supervise"


async def test_co_supervisor_rules(client, world, session):
    url = f"/api/v1/scholars/{world.s_a2.id}/co-supervisor"
    body = {"faculty_id": str(world.co_sup_faculty.id)}
    off = await client.put(url, json=body, headers=auth(world.root_admin.id))
    assert off.json()["error"]["code"] == "co_supervision_off"
    await session.execute(update(Settings).values(co_supervision="approve"))
    await session.commit()
    ok = await client.put(url, json=body, headers=auth(world.root_admin.id))
    assert ok.json()["co_supervisor"]["name"] == "Co Sup"
    same = await client.put(
        url, json={"faculty_id": str(world.sup_a2_faculty.id)}, headers=auth(world.root_admin.id)
    )
    assert same.json()["error"]["code"] == "co_supervisor_same_as_supervisor"


async def test_scholar_edits_and_moves(client, world):
    url = f"/api/v1/scholars/{world.s_a1.id}"
    stage = await client.patch(url, json={"stage": "Coursework"}, headers=auth(world.admin_a1.id))
    assert stage.json()["stage"] == "Coursework"
    by_supervisor = await client.patch(url, json={"stage": "Viva"}, headers=auth(world.meera.id))
    assert by_supervisor.status_code == 200  # Meera is also admin of A1
    by_plain_sup = await client.patch(
        f"/api/v1/scholars/{world.s_a2.id}", json={"stage": "Viva"}, headers=auth(world.sup_a2.id)
    )
    assert by_plain_sup.status_code == 403
    move_out = await client.patch(
        url, json={"unit_id": str(world.b1.id)}, headers=auth(world.admin_a1.id)
    )
    assert move_out.status_code == 403  # no admin over the destination
    moved = await client.patch(
        url, json={"unit_id": str(world.b1.id)}, headers=auth(world.root_admin.id)
    )
    assert moved.json()["unit"]["name"] == "Dept B1"


async def test_faculty_directory_and_caps(client, world):
    listed = await client.get("/api/v1/faculty", headers=auth(world.scholar_b1.id))
    assert len(listed.json()) == 4  # readable by everyone
    above = await client.patch(
        f"/api/v1/faculty/{world.meera_faculty.id}",
        json={"max_scholars": 12},
        headers=auth(world.root_admin.id),
    )
    assert above.json()["error"]["code"] == "cap_above_ugc"
    demoted = await client.patch(
        f"/api/v1/faculty/{world.sup_b1_faculty.id}",
        json={"designation": "Assistant Professor"},
        headers=auth(world.root_admin.id),
    )
    assert demoted.json()["max_scholars"] == 4
    other = await client.patch(
        f"/api/v1/faculty/{world.sup_b1_faculty.id}",
        json={"can_supervise": False},
        headers=auth(world.admin_a1.id),
    )
    assert other.status_code == 403


async def test_with_capacity_hides_full_supervisors(client, world):
    await client.patch(
        f"/api/v1/faculty/{world.meera_faculty.id}",
        json={"max_scholars": 1},
        headers=auth(world.root_admin.id),
    )
    res = await client.get("/api/v1/faculty?with_capacity=true", headers=auth(world.admin_a1.id))
    assert "Meera" not in {f["full_name"] for f in res.json()}
