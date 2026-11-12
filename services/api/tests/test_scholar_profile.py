"""Scholar profile (PRD F6): study mode for everyone who sees the scholar; gender, category and
disability only through scope.sees_personal."""

from tests.conftest import auth

PROFILE = {"study_mode": "part_time", "gender": "female", "category": "obc", "has_disability": True}
PERSONAL = ("gender", "category", "has_disability")


async def _set(client, world, **body):
    return await client.patch(
        f"/api/v1/scholars/{world.s_a1b.id}", headers=auth(world.admin_a1.id), json=body or PROFILE
    )


async def _read(client, user, world) -> dict:
    res = await client.get(f"/api/v1/scholars/{world.s_a1b.id}", headers=auth(user.id))
    assert res.status_code == 200, f"{user.email}: {res.text}"
    return res.json()


async def test_admin_records_the_profile_and_bad_values_are_refused(client, world):
    saved = await _set(client, world)
    assert saved.status_code == 200, saved.text
    assert {k: saved.json()[k] for k in PROFILE} == PROFILE
    assert (await _set(client, world, gender="unknown")).status_code == 422
    assert (await _set(client, world, category="General")).status_code == 422
    # Not the supervisor's, nor the scholar's own, to change.
    for user in (world.sup_a2, world.scholar_a1b):
        res = await client.patch(
            f"/api/v1/scholars/{world.s_a1b.id}", headers=auth(user.id), json={"gender": "male"}
        )
        assert res.status_code == 403, user.email


async def test_personal_fields_reach_only_those_who_may_see_them(client, world):
    assert (await _set(client, world)).status_code == 200
    for user in (world.scholar_a1b, world.admin_a1, world.dean_a, world.research_office):
        seen = await _read(client, user, world)
        assert seen["sees_personal"] is True, user.email
        assert {k: seen[k] for k in PERSONAL} == {k: PROFILE[k] for k in PERSONAL}, user.email
    # The supervisor sees the scholar and the study mode, never the personal fields.
    seen = await _read(client, world.sup_a2, world)
    assert seen["study_mode"] == "part_time" and seen["sees_personal"] is False
    assert all(seen[k] is None for k in PERSONAL)
    # The same holds in the list and in the exported file.
    listed = await client.get("/api/v1/scholars", headers=auth(world.sup_a2.id))
    assert all(s[k] is None for s in listed.json() for k in PERSONAL)
    table = (
        await client.get("/api/v1/internal/lists/scholars", headers=auth(world.sup_a2.id))
    ).json()
    at = [table["columns"].index(c) for c in ("Gender", "Category", "Person with disability")]
    assert all(row[i] is None for row in table["rows"] for i in at)
    assert "part time" in {row[table["columns"].index("Mode")] for row in table["rows"]}


async def test_list_filters_by_study_mode(client, world):
    assert (await _set(client, world)).status_code == 200
    office = auth(world.research_office.id)
    part = await client.get("/api/v1/scholars", headers=office, params={"study_mode": "part_time"})
    assert [s["id"] for s in part.json()] == [str(world.s_a1b.id)]
    full = await client.get("/api/v1/scholars", headers=office, params={"study_mode": "full_time"})
    assert full.json() == []  # nobody else has a mode recorded yet
