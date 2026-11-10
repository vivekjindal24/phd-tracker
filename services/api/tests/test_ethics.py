"""Research ethics clearance (PRD F9c): a record per scholar kept by an admin over their unit
or the Research Office, an expiry reminder, and the thesis gate while `require_ethics` is on."""

from datetime import UTC, datetime, timedelta

from app.routers import cron
from tests.conftest import auth
from tests.test_daily_job import inbox
from tests.test_thesis import act, documents_on, new_thesis, ready_file  # noqa: F401

CLEARANCE = {
    "kind": "human",
    "committee": "Institutional Ethics Committee",
    "approval_number": "IEC/2026/041",
    "approved_on": "2026-02-01",
    "valid_until": "2027-01-31",
}
NOT_REQUIRED = {"kind": "not_required", "notes": "Theoretical work, no subjects or samples."}


def url(world) -> str:
    return f"/api/v1/scholars/{world.s_a1.id}/ethics"


async def test_admin_records_and_the_scholar_reads(client, world):
    saved = await client.post(url(world), headers=auth(world.admin_a1.id), json=CLEARANCE)
    assert saved.status_code == 200, saved.text
    view = saved.json()
    assert view["satisfied"] and view["can_manage"]
    assert view["records"][0]["approval_number"] == "IEC/2026/041"
    own = (await client.get(url(world), headers=auth(world.scholar_a1.id))).json()
    assert len(own["records"]) == 1 and not own["can_manage"]
    # The certificate hangs off the record, readable exactly when the record is.
    params = {"table_name": "ethics_clearances", "record_id": view["records"][0]["id"]}
    for user, status in ((world.scholar_a1, 200), (world.scholar_a2, 403), (world.hod_b1, 403)):
        res = await client.get("/api/v1/files", headers=auth(user.id), params=params)
        assert res.status_code == status, user.email
    gone = await client.delete(
        f"/api/v1/ethics-clearances/{view['records'][0]['id']}", headers=auth(world.admin_a1.id)
    )
    assert gone.json()["records"] == [] and not gone.json()["satisfied"]


async def test_who_may_read_and_write(client, world):
    for user in (world.scholar_a1, world.sup_a2, world.dean_a):
        res = await client.post(url(world), headers=auth(user.id), json=NOT_REQUIRED)
        assert res.status_code == 403, user.email
    ok = await client.post(url(world), headers=auth(world.research_office.id), json=NOT_REQUIRED)
    assert ok.status_code == 200, ok.text
    for user in (world.scholar_a2, world.hod_b1, world.library):
        assert (await client.get(url(world), headers=auth(user.id))).status_code == 403, user.email
    for user in (world.meera, world.dean_a, world.vice_chancellor):
        assert (await client.get(url(world), headers=auth(user.id))).status_code == 200, user.email


async def test_bad_records_are_refused(client, world):
    admin = auth(world.admin_a1.id)
    for bad in (
        {"kind": "not_required"},  # no reason
        {"kind": "human", "committee": "IEC"},  # no approval number or date
        {**CLEARANCE, "valid_until": "2026-01-01"},  # ends before it starts
        {**NOT_REQUIRED, "approval_number": "X"},
    ):
        assert (await client.post(url(world), headers=admin, json=bad)).status_code == 422, bad
    assert (await client.post(url(world), headers=admin, json=CLEARANCE)).status_code == 200
    clash = await client.post(url(world), headers=admin, json=NOT_REQUIRED)
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "ethics_conflict"


async def test_thesis_waits_for_an_ethics_record(client, session, world, documents_on):  # noqa: F811
    on = await client.patch(
        "/api/v1/settings", headers=auth(world.root_admin.id), json={"require_ethics": True}
    )
    assert on.status_code == 200 and on.json()["require_ethics"] is True
    tid = await new_thesis(client, session, world)
    await ready_file(session, world.scholar_a1, "thesis_submissions", tid)
    blocked = await act(client, world.scholar_a1, tid, "submit")
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "ethics_pending"
    await client.post(url(world), headers=auth(world.admin_a1.id), json=NOT_REQUIRED)
    assert (await act(client, world.scholar_a1, tid, "submit")).status_code == 200


async def test_expiry_reminder_goes_out_sixty_days_before(client, session, world):
    today = datetime.now(UTC).date()
    ends = today + timedelta(days=cron.ETHICS_NOTICE_DAYS)
    body = {**CLEARANCE, "approved_on": str(today), "valid_until": str(ends)}
    assert (await client.post(url(world), headers=auth(world.admin_a1.id), json=body)).is_success
    assert await cron._ethics_expiring(session, today) == 1
    assert await cron._ethics_expiring(session, today + timedelta(days=1)) == 0
    await session.commit()
    for user in (world.scholar_a1, world.meera):
        assert any("Ethics clearance" in title for _, title in await inbox(session, user))
