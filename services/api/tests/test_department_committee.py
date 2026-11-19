"""A department's research committee (PRD F9b): versions like the advisory committee, each
member with a role (chairperson, secretary, member) and a seat (HoD, Dean's nominee, faculty
nominee, VC nominee, scholar). Kept by an admin over the department or the Research Office."""

from tests.conftest import auth

OUTSIDER = {"name": "Dr. V. Ganeshan", "institution": "IIT Indore", "email": "vg@iiti.example"}


def url(unit) -> str:
    return f"/api/v1/org-units/{unit.id}/committee"


async def form(client, unit, user, formed_on="2021-09-24"):
    return await client.post(
        f"{url(unit)}/formations", headers=auth(user.id), json={"formed_on": formed_on}
    )


async def add(client, world, formation_id, body, user=None):
    return await client.post(
        f"/api/v1/committee-formations/{formation_id}/members",
        headers=auth((user or world.admin_a1).id),
        json=body,
    )


async def test_admin_constitutes_the_department_committee(client, world):
    formed = await form(client, world.a1, world.admin_a1)
    assert formed.status_code == 200, formed.text
    assert formed.json()["title"] == "Department Research Committee (DRC)"
    fid = formed.json()["formations"][0]["id"]
    for body in (
        {"faculty_id": str(world.meera_faculty.id), "role": "chairperson", "seat": "hod"},
        {"faculty_id": str(world.sup_a2_faculty.id), "role": "secretary", "seat": "dean_nominee"},
        {**OUTSIDER, "seat": "vc_nominee"},
        {"scholar_member_id": str(world.s_a1.id), "seat": "scholar"},
    ):
        res = await add(client, world, fid, body)
        assert res.status_code == 200, (body, res.text)
    view = res.json()
    assert view["convener"] is None and view["can_manage"]
    assert [(m["name"], m["role"], m["seat"]) for m in view["formations"][0]["members"]] == [
        ("Meera", "chairperson", "hod"),
        ("Sup A2", "secretary", "dean_nominee"),
        ("Dr. V. Ganeshan", "member", "vc_nominee"),
        ("Scholar A1", "member", "scholar"),
    ]
    second = await add(
        client,
        world,
        fid,
        {**OUTSIDER, "name": "Dr. X", "role": "secretary", "seat": "dean_nominee"},
    )
    assert second.json()["error"]["code"] == "secretary_taken"

    # Re-constituting copies the members with their seats; the first stays as history.
    new, old = (await form(client, world.a1, world.admin_a1, "2024-07-01")).json()["formations"]
    assert [m["seat"] for m in new["members"]] == [m["seat"] for m in old["members"]]

    # The university names the committee.
    await client.patch(
        "/api/v1/settings",
        headers=auth(world.root_admin.id),
        json={"department_committee_name": "Departmental Post Graduate Committee (DPGC)"},
    )
    renamed = await client.get(url(world.a1), headers=auth(world.admin_a1.id))
    assert renamed.json()["title"] == "Departmental Post Graduate Committee (DPGC)"


async def test_roles_seats_and_members_must_fit_the_committee(client, world):
    fid = (await form(client, world.a1, world.admin_a1)).json()["formations"][0]["id"]
    faculty = {"faculty_id": str(world.sup_a2_faculty.id)}
    for body, code in (
        (faculty, "seat_mismatch"),  # every member sits in a seat
        ({**faculty, "seat": "scholar"}, "seat_mismatch"),  # the scholar's seat is a scholar's
        ({"scholar_member_id": str(world.s_a1.id), "seat": "hod"}, "seat_mismatch"),
        ({**faculty, "seat": "vc_nominee", "role": "vc_nominee"}, "role_not_allowed"),
        ({"scholar_member_id": str(world.s_b1.id), "seat": "scholar"}, "scholar_not_in_unit"),
    ):
        res = await add(client, world, fid, body)
        assert (res.status_code, res.json()["error"]["code"]) == (422, code), body

    # A scholar's advisory committee takes no seats and no scholar members.
    rac = await client.post(
        f"/api/v1/scholars/{world.s_a1.id}/committee/formations",
        headers=auth(world.admin_a1.id),
        json={"formed_on": "2022-02-15"},
    )
    rid = rac.json()["formations"][0]["id"]
    for body in (
        {**faculty, "seat": "hod"},
        {**faculty, "role": "secretary"},
        {"scholar_member_id": str(world.s_a1b.id)},
    ):
        res = await add(client, world, rid, body)
        assert res.json()["error"]["code"] == "role_not_allowed", body


async def test_who_may_read_and_keep_it(client, world):
    assert (await form(client, world.b1, world.admin_a1)).status_code == 403  # not their unit
    for user in (world.hod_a2, world.dean_a, world.scholar_a1, world.vice_chancellor):
        assert (await form(client, world.a1, user)).status_code == 403, user.email
    fid = (await form(client, world.b1, world.research_office)).json()["formations"][0]["id"]
    assert (await add(client, world, fid, {**OUTSIDER, "seat": "vc_nominee"})).status_code == 403

    for user in (world.scholar_a1, world.dean_a, world.hod_a2, world.vice_chancellor):
        res = await client.get(url(world.a1), headers=auth(user.id))
        assert res.status_code == 200 and not res.json()["can_manage"], user.email
    # A scholar reads only their own department's committee.
    assert (await client.get(url(world.a1), headers=auth(world.scholar_a2.id))).status_code == 403
