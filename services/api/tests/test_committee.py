"""Research Advisory Committee members per scholar (PRD F9b): the supervisor convenes, an
admin over the scholar's unit or the Research Office keeps the list, the scholar reads it."""

from tests.conftest import auth


def url(world) -> str:
    return f"/api/v1/scholars/{world.s_a1.id}/committee"


async def test_admin_records_internal_and_outside_members(client, world):
    admin = auth(world.admin_a1.id)
    inside = await client.post(
        url(world), headers=admin, json={"faculty_id": str(world.sup_a2_faculty.id)}
    )
    assert inside.status_code == 200, inside.text
    outside = await client.post(
        url(world), headers=admin, json={"name": "Prof. R. Sen", "institution": "IIT Delhi"}
    )
    view = outside.json()
    assert view["convener"] == "Meera" and view["can_manage"]
    assert [(m["name"], m["institution"], m["external"]) for m in view["members"]] == [
        ("Prof. R. Sen", "IIT Delhi", True),
        ("Sup A2", "Dept A2", False),
    ]
    # The scholar reads their own committee and cannot change it.
    own = await client.get(url(world), headers=auth(world.scholar_a1.id))
    assert len(own.json()["members"]) == 2 and not own.json()["can_manage"]

    gone = await client.delete(
        f"/api/v1/committee-members/{view['members'][0]['id']}", headers=admin
    )
    assert [m["name"] for m in gone.json()["members"]] == ["Sup A2"]


async def test_who_may_read_and_write(client, world):
    body = {"name": "Prof. R. Sen", "institution": "IIT Delhi"}
    for user in (world.scholar_a1, world.sup_a2, world.dean_a, world.vice_chancellor):
        res = await client.post(url(world), headers=auth(user.id), json=body)
        assert res.status_code == 403, user.email
    assert (
        await client.post(url(world), headers=auth(world.research_office.id), json=body)
    ).status_code == 200
    for user in (world.scholar_a2, world.hod_b1, world.library):
        assert (await client.get(url(world), headers=auth(user.id))).status_code == 403, user.email
    for user in (world.dean_a, world.vice_chancellor, world.meera):
        assert (await client.get(url(world), headers=auth(user.id))).status_code == 200, user.email


async def test_bad_members_are_refused(client, world):
    admin = auth(world.admin_a1.id)
    supervisor = await client.post(
        url(world), headers=admin, json={"faculty_id": str(world.meera_faculty.id)}
    )
    assert supervisor.status_code == 409
    assert supervisor.json()["error"]["code"] == "supervisor_is_convener"
    member = {"faculty_id": str(world.sup_a2_faculty.id)}
    assert (await client.post(url(world), headers=admin, json=member)).status_code == 200
    again = await client.post(url(world), headers=admin, json=member)
    assert again.status_code == 409 and again.json()["error"]["code"] == "duplicate_member"
    for bad in ({}, {**member, "name": "X", "institution": "Y"}, {"name": "No institution"}):
        assert (await client.post(url(world), headers=admin, json=bad)).status_code == 422, bad


async def test_committee_prints_on_the_progress_report(client, world):
    await client.post(
        url(world),
        headers=auth(world.admin_a1.id),
        json={"name": "Prof. R. Sen", "institution": "IIT Delhi"},
    )
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
    assert view.json()["committee"] == ["Prof. R. Sen (IIT Delhi)"]
