"""Scholar profile (PRD F6): study mode for everyone who sees the scholar; gender, category and
disability only through scope.sees_personal."""

from sqlalchemy import select

from app.models import Scholar
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


async def _fill(client, user, **body):
    return await client.put("/api/v1/scholars/mine/profile", headers=auth(user.id), json=body)


async def test_scholar_fills_in_what_is_missing_but_cannot_change_it(client, world):
    home = await client.get("/api/v1/dashboard", headers=auth(world.scholar_a1b.id))
    assert home.json()["scholar"]["profile_incomplete"] is True
    first = await _fill(client, world.scholar_a1b, gender="female", category="sc")
    assert first.status_code == 200, first.text
    assert (first.json()["gender"], first.json()["category"]) == ("female", "sc")
    # A recorded value is the admin's to correct, not the scholar's to change.
    again = await _fill(client, world.scholar_a1b, category="general", study_mode="full_time")
    assert again.status_code == 409 and again.json()["error"]["details"] == {"fields": ["category"]}
    rest = await _fill(client, world.scholar_a1b, study_mode="full_time", has_disability=False)
    assert rest.status_code == 200 and rest.json()["has_disability"] is False
    home = await client.get("/api/v1/dashboard", headers=auth(world.scholar_a1b.id))
    assert home.json()["scholar"]["profile_incomplete"] is False
    # Only scholars have a profile of their own, and only the four fields are theirs to fill.
    assert (await _fill(client, world.sup_a2, gender="male")).status_code == 403
    assert (await _fill(client, world.scholar_a1, stage="Viva")).status_code == 422


async def test_import_takes_the_profile_columns_and_leaves_blanks_unrecorded(
    client, session, world
):
    file = (
        b"Roll number *,Name *,Email *,Unit *,Mode,Gender,Category,Person with disability\n"
        b"PHD-NEW-1,New One,new1@x.edu,A1,Part time,Female,OBC,no\n"
        b"PHD-NEW-2,New Two,new2@x.edu,A1,,,,\n"
    )

    async def send(content: bytes):
        return await client.post(
            "/api/v1/import/scholars",
            headers=auth(world.admin_a1.id),
            content=content,
            params={"dry_run": "false"},
        )

    res = await send(file)
    assert res.status_code == 200, res.text
    rows = {
        s.roll_number: (s.study_mode, s.gender, s.category, s.has_disability)
        for s in await session.scalars(select(Scholar).where(Scholar.roll_number.like("PHD-NEW-%")))
    }
    assert rows == {
        "PHD-NEW-1": ("part_time", "female", "obc", False),
        "PHD-NEW-2": (None, None, None, None),
    }
    bad = await send(
        file.replace(b"PHD-NEW-1", b"PHD-NEW-3")
        .replace(b"new1@", b"new3@")
        .replace(b"OBC", b"other")
    )
    assert "is not one of" in bad.text
