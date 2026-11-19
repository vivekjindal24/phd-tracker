"""Research Advisory Committee per scholar (PRD F9b): formed in dated versions, the supervisor
its secretary, members with roles; an admin over the scholar's unit or the Research Office
keeps it, the scholar reads it, and earlier versions stay as frozen history."""

from tests.conftest import auth

SEN = {"name": "Prof. R. Sen", "institution": "IIT Delhi"}


def url(world) -> str:
    return f"/api/v1/scholars/{world.s_a1.id}/committee"


async def form(client, world, formed_on="2026-02-15", user=None, **extra):
    return await client.post(
        f"{url(world)}/formations",
        headers=auth((user or world.admin_a1).id),
        json={"formed_on": formed_on, **extra},
    )


async def add(client, world, formation_id, body, user=None):
    return await client.post(
        f"/api/v1/committee-formations/{formation_id}/members",
        headers=auth((user or world.admin_a1).id),
        json=body,
    )


async def test_admin_forms_the_committee_with_roles(client, world):
    admin = auth(world.admin_a1.id)
    formed = await form(client, world, reference="DRC/2026/14")
    assert formed.status_code == 200, formed.text
    fid = formed.json()["formations"][0]["id"]
    inside = await add(client, world, fid, {"faculty_id": str(world.sup_a2_faculty.id)})
    assert inside.status_code == 200, inside.text
    view = (await add(client, world, fid, {**SEN, "role": "chairperson"})).json()
    assert view["convener"] == "Meera" and view["can_manage"]
    (current,) = view["formations"]
    assert (current["formed_on"], current["reference"], current["secretary"]) == (
        "2026-02-15",
        "DRC/2026/14",
        "Meera",
    )
    assert [
        (m["name"], m["institution"], m["external"], m["role"]) for m in current["members"]
    ] == [
        ("Prof. R. Sen", "IIT Delhi", True, "chairperson"),
        ("Sup A2", "Dept A2", False, "member"),
    ]
    # The scholar reads their own committee and cannot change it.
    own = await client.get(url(world), headers=auth(world.scholar_a1.id))
    assert len(own.json()["formations"][0]["members"]) == 2 and not own.json()["can_manage"]

    sup_a2 = current["members"][1]["id"]
    nominee = await client.patch(
        f"/api/v1/committee-members/{sup_a2}", headers=admin, json={"role": "vc_nominee"}
    )
    assert nominee.json()["formations"][0]["members"][1]["role"] == "vc_nominee"
    gone = await client.delete(f"/api/v1/committee-members/{sup_a2}", headers=admin)
    assert [m["name"] for m in gone.json()["formations"][0]["members"]] == ["Prof. R. Sen"]


async def test_who_may_read_and_write(client, world):
    for user in (world.scholar_a1, world.sup_a2, world.dean_a, world.vice_chancellor):
        assert (await form(client, world, user=user)).status_code == 403, user.email
    assert (await form(client, world, user=world.research_office)).status_code == 200
    for user in (world.scholar_a2, world.hod_b1, world.library):
        assert (await client.get(url(world), headers=auth(user.id))).status_code == 403, user.email
    for user in (world.dean_a, world.vice_chancellor, world.meera):
        assert (await client.get(url(world), headers=auth(user.id))).status_code == 200, user.email


async def test_bad_members_are_refused(client, world):
    fid = (await form(client, world)).json()["formations"][0]["id"]
    supervisor = await add(client, world, fid, {"faculty_id": str(world.meera_faculty.id)})
    assert supervisor.status_code == 409
    assert supervisor.json()["error"]["code"] == "supervisor_is_convener"
    member = {"faculty_id": str(world.sup_a2_faculty.id), "role": "chairperson"}
    assert (await add(client, world, fid, member)).status_code == 200
    again = await add(client, world, fid, member)
    assert again.status_code == 409 and again.json()["error"]["code"] == "duplicate_member"
    second_chair = await add(client, world, fid, {**SEN, "role": "chairperson"})
    assert second_chair.json()["error"]["code"] == "chairperson_taken"
    for bad in (
        {},
        {**member, "name": "X", "institution": "Y"},
        {"name": "No institution"},
        {**SEN, "role": "secretary"},  # the supervisor is the secretary
    ):
        assert (await add(client, world, fid, bad)).status_code == 422, bad


async def test_re_forming_keeps_the_earlier_version_as_history(client, world):
    admin = auth(world.admin_a1.id)
    first = (await form(client, world, "2022-02-15")).json()["formations"][0]["id"]
    await add(client, world, first, {**SEN, "role": "chairperson"})
    await add(client, world, first, {"faculty_id": str(world.sup_a2_faculty.id)})

    early = await form(client, world, "2021-12-01")
    assert early.json()["error"]["code"] == "formation_out_of_order"
    second, earlier = (await form(client, world, "2023-08-01")).json()["formations"]
    assert earlier["id"] == first
    # The new version starts as a copy; a new chairperson takes over in it alone.
    assert [(m["name"], m["role"]) for m in second["members"]] == [
        ("Prof. R. Sen", "chairperson"),
        ("Sup A2", "member"),
    ]
    await client.patch(
        f"/api/v1/committee-members/{second['members'][0]['id']}",
        headers=admin,
        json={"role": "member"},
    )
    view = await client.patch(
        f"/api/v1/committee-members/{second['members'][1]['id']}",
        headers=admin,
        json={"role": "chairperson"},
    )
    new, old = view.json()["formations"]
    assert [m["name"] for m in new["members"] if m["role"] == "chairperson"] == ["Sup A2"]
    assert [m["name"] for m in old["members"] if m["role"] == "chairperson"] == ["Prof. R. Sen"]

    # The earlier version's members and roles are frozen.
    sen, sup_a2 = (m["id"] for m in old["members"])
    for res in (
        await add(client, world, first, {"name": "Late", "institution": "X"}),
        await client.delete(f"/api/v1/committee-members/{sen}", headers=admin),
        await client.patch(
            f"/api/v1/committee-members/{sen}", headers=admin, json={"role": "member"}
        ),
    ):
        assert res.json()["error"]["code"] == "formation_superseded", res.text

    # Its wording may still be corrected: date, order number, an outside expert's name.
    fixed = await client.patch(
        f"/api/v1/committee-formations/{first}",
        headers=admin,
        json={"formed_on": "2022-03-01", "reference": "DRC/2022/7"},
    )
    assert (
        fixed.json()["formations"][1]["formed_on"],
        fixed.json()["formations"][1]["reference"],
    ) == (
        "2022-03-01",
        "DRC/2022/7",
    )
    late = await client.patch(
        f"/api/v1/committee-formations/{first}", headers=admin, json={"formed_on": "2024-01-01"}
    )
    assert late.json()["error"]["code"] == "formation_out_of_order"  # after the newer one
    renamed = await client.patch(
        f"/api/v1/committee-members/{sen}", headers=admin, json={"name": "Prof. R. K. Sen"}
    )
    assert renamed.json()["formations"][1]["members"][0]["name"] == "Prof. R. K. Sen"
    assert renamed.json()["formations"][0]["members"][1]["name"] == "Prof. R. Sen"
    internal = await client.patch(
        f"/api/v1/committee-members/{sup_a2}", headers=admin, json={"name": "Typo"}
    )
    assert internal.json()["error"]["code"] == "directory_name"
    nothing = await client.patch(f"/api/v1/committee-members/{sen}", headers=admin, json={})
    assert nothing.status_code == 422

    # The current one may be corrected, or withdrawn, which makes the earlier current again.
    moved = await client.patch(
        f"/api/v1/committee-formations/{new['id']}",
        headers=admin,
        json={"formed_on": "2021-01-01"},
    )
    assert moved.json()["error"]["code"] == "formation_out_of_order"
    back = await client.delete(f"/api/v1/committee-formations/{new['id']}", headers=admin)
    assert [f["id"] for f in back.json()["formations"]] == [first]


async def test_committee_prints_on_the_progress_report(client, world):
    fid = (await form(client, world)).json()["formations"][0]["id"]
    await add(client, world, fid, {**SEN, "role": "chairperson"})
    rid = (
        await client.post(
            "/api/v1/reports",
            headers=auth(world.scholar_a1.id),
            json={
                "report_year": 2026,
                "period": "January-June",
                "summary": "Completed the literature survey and the first experiment.",
            },
        )
    ).json()["id"]
    view = await client.get(
        f"/api/v1/internal/reports/{rid}/export-view", headers=auth(world.scholar_a1.id)
    )
    assert view.json()["committee"] == ["Prof. R. Sen (IIT Delhi), Chairperson"]
