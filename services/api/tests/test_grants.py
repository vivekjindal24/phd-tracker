"""Grants (PRD M6-M8, UX Flow 11): fellowships, projects and the ledger, scoped per
SECURITY.md §3 — including the negatives (scholars never see money; supervisors see their
scholars' fellowships but not the ledger; heads stay inside their subtree)."""

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.routers import cron
from tests.conftest import auth
from tests.test_publications import enable

API = "/api/v1"


@pytest.fixture
async def grants_on(session, world):
    await enable(session, "fellowships", "projects", "ledger")


async def fellowship(client, world, user=None, scholar=None, **over):
    body = {
        "scholar_id": str((scholar or world.s_a1).id),
        "scheme": "ugc_jrf",
        "amount_monthly": 37000,
        "hra_amount": 3000,
        "start_date": "2024-08-01",
        "end_date": "2026-07-31",
    } | over
    return await client.post(
        f"{API}/fellowships", headers=auth((user or world.admin_a1).id), json=body
    )


async def project(client, world, user=None, **over):
    body = {
        "pi_id": str(world.sup_b1_faculty.id),
        "agency": "SERB",
        "title": "Low-power edge inference",
        "sanction_number": "SERB/CRG/2025/001",
        "amount_sanctioned": 2500000,
        "start_date": "2025-04-01",
        "end_date": "2028-03-31",
    } | over
    return await client.post(
        f"{API}/projects", headers=auth((user or world.research_office).id), json=body
    )


async def get(client, user, path, **params):
    return await client.get(f"{API}{path}", headers=auth(user.id), params=params)


async def test_fellowships_are_scoped(client, world, grants_on):
    res = await fellowship(client, world)
    assert res.status_code == 201, res.text
    fid = res.json()["id"]
    assert res.json()["can_manage"] and res.json()["sees_ledger"]
    for user, scholar in (
        (world.admin_a1, world.s_b1),  # outside the admin's unit
        (world.scholar_a1, world.s_a1),
        (world.meera, world.s_b1),
        (world.exam_office, world.s_a1),
    ):
        assert (await fellowship(client, world, user, scholar)).status_code == 403

    mine = (await get(client, world.scholar_a1, "/fellowships")).json()
    assert [f["id"] for f in mine] == [fid] and not mine[0]["can_manage"]
    assert not mine[0]["sees_ledger"]
    assert len((await get(client, world.co_sup, "/fellowships")).json()) == 0  # co-sup off
    sup = (await get(client, world.meera, "/fellowships")).json()
    assert [f["id"] for f in sup] == [fid]
    for user in (world.scholar_a2, world.sup_b1, world.hod_b1):
        assert (await get(client, user, "/fellowships")).json() == []
    for user in (world.library, world.exam_office):
        assert (await get(client, user, "/fellowships")).status_code == 403


async def test_srf_upgrade_and_dates(client, world, grants_on):
    fid = (await fellowship(client, world)).json()["id"]
    url = f"{API}/fellowships/{fid}"
    outside = await client.patch(
        url, headers=auth(world.admin_a1.id), json={"srf_upgrade_on": "2027-01-01"}
    )
    assert outside.status_code == 422
    upgraded = await client.patch(
        url,
        headers=auth(world.research_office.id),
        json={"srf_upgrade_on": "2026-08-01", "scheme": "ugc_srf", "end_date": "2027-07-31"},
    )
    assert upgraded.status_code == 200, upgraded.text
    assert upgraded.json()["scheme"] == "ugc_srf"
    home = (await get(client, world.scholar_a1, "/dashboard")).json()
    assert home["scholar"]["fellowship_ends"] == "2027-07-31"
    assert (
        await client.patch(url, headers=auth(world.hod_b1.id), json={"status": "completed"})
    ).status_code == 403


async def test_projects_are_scoped(client, world, grants_on):
    res = await project(client, world)
    assert res.status_code == 201, res.text
    pid = res.json()["id"]
    assert res.json()["unit"]["name"] == "Dept B1"  # the PI's unit by default
    assert (await project(client, world)).json()["error"]["code"] == "duplicate_sanction"
    assert (await project(client, world, world.admin_a1, sanction_number="X")).status_code == 403
    member = await client.post(
        f"{API}/projects/{pid}/members",
        headers=auth(world.research_office.id),
        json={"scholar_id": str(world.s_a1.id), "member_role": "JRF"},
    )
    assert member.status_code == 201 and member.json()["members"][0]["member_role"] == "JRF"

    pi = (await get(client, world.sup_b1, f"/projects/{pid}")).json()
    assert pi["sees_ledger"] and not pi["can_manage"]
    as_member = (await get(client, world.scholar_a1, f"/projects/{pid}")).json()
    assert not as_member["sees_ledger"]
    assert (await get(client, world.hod_b1, f"/projects/{pid}")).json()["sees_ledger"]
    for user in (world.scholar_a2, world.dean_a, world.meera, world.library):
        assert (await get(client, user, f"/projects/{pid}")).status_code == 403, user.email
        assert (await get(client, user, "/projects")).json() == []


async def test_ledger_balance_and_who_may_write(client, world, grants_on):
    pid = (await project(client, world)).json()["id"]

    async def entry(user, kind, amount, head="equipment"):
        return await client.post(
            f"{API}/ledger",
            headers=auth(user.id),
            json={
                "project_id": pid,
                "entry_kind": kind,
                "head": head,
                "amount": amount,
                "entry_date": "2025-05-01",
            },
        )

    assert (await entry(world.research_office, "disbursement", 1000000)).status_code == 201
    spent = await entry(world.sup_b1, "expense", 2500.5, "consumables")  # the PI
    assert spent.status_code == 201
    assert spent.json()["balance"] == 997499.5 and spent.json()["can_add_expense"]
    assert [e["balance"] for e in spent.json()["entries"]] == [1000000, 997499.5]
    assert (await entry(world.sup_b1, "disbursement", 10)).status_code == 403
    assert (await entry(world.hod_b1, "expense", 10)).status_code == 403
    assert (await entry(world.admin_a1, "expense", 10)).status_code == 403  # not their unit

    for user in (world.scholar_a1, world.dean_a, world.library):  # scholar_a1 is a member
        assert (await get(client, user, f"/projects/{pid}/ledger")).status_code == 403
    head = (await get(client, world.hod_b1, f"/projects/{pid}/ledger")).json()
    assert head["spent"] == 2500.5 and not head["can_manage"] and head["sanctioned"] == 2500000

    expense_id = spent.json()["entries"][1]["id"]
    assert (
        await client.delete(f"{API}/ledger/{expense_id}", headers=auth(world.sup_b1.id))
    ).status_code == 403
    removed = await client.delete(
        f"{API}/ledger/{expense_id}", headers=auth(world.research_office.id)
    )
    assert removed.json()["balance"] == 1000000


async def test_fellowship_ledger_is_for_offices_and_heads(client, world, grants_on):
    fid = (await fellowship(client, world, scholar=world.s_a1b)).json()["id"]
    paid = await client.post(
        f"{API}/ledger",
        headers=auth(world.admin_a1.id),
        json={
            "fellowship_id": fid,
            "entry_kind": "disbursement",
            "head": "fellowship_salary",
            "amount": 40000,
            "entry_date": "2024-09-01",
        },
    )
    assert paid.status_code == 201 and paid.json()["sanctioned"] is None
    assert (await get(client, world.dean_a, f"/fellowships/{fid}/ledger")).status_code == 200
    # sup_a2 supervises scholar_a1b and sees the fellowship, but not its money.
    assert (await get(client, world.sup_a2, "/fellowships")).json()[0]["sees_ledger"] is False
    for user in (world.scholar_a1b, world.sup_a2, world.hod_b1):
        assert (await get(client, user, f"/fellowships/{fid}/ledger")).status_code == 403
    both = await client.post(
        f"{API}/ledger",
        headers=auth(world.admin_a1.id),
        json={
            "fellowship_id": fid,
            "project_id": fid,
            "entry_kind": "expense",
            "head": "travel",
            "amount": 1,
            "entry_date": "2024-09-01",
        },
    )
    assert both.status_code == 422


async def test_utilisation_certificates(client, world, grants_on):
    pid = (await project(client, world)).json()["id"]
    body = {"period_start": "2025-04-01", "period_end": "2026-03-31"}
    url = f"{API}/projects/{pid}/ucs"
    assert (await client.post(url, headers=auth(world.sup_b1.id), json=body)).status_code == 403
    uc = await client.post(url, headers=auth(world.research_office.id), json=body)
    assert uc.status_code == 201
    uc_id = uc.json()["id"]
    assert [u["id"] for u in (await get(client, world.sup_b1, f"/projects/{pid}/ucs")).json()] == [
        uc_id
    ]
    files = {"table_name": "utilisation_certificates", "record_id": uc_id}
    assert (await get(client, world.sup_b1, "/files", **files)).json() == []
    assert (await get(client, world.scholar_a2, "/files", **files)).status_code == 403
    upload = await client.post(
        f"{API}/files/uploads",
        headers=auth(world.sup_b1.id),
        json=files | {"file_name": "uc.pdf", "content_type": "application/pdf", "size_bytes": 10},
    )
    assert upload.status_code == 403  # only managers attach the signed certificate
    submitted = await client.patch(
        f"{API}/ucs/{uc_id}",
        headers=auth(world.research_office.id),
        json={"submitted_on": "2026-04-15"},
    )
    assert submitted.json()["submitted_on"] == "2026-04-15"


async def test_modules_off_means_404(client, world):
    for path in ("/fellowships", "/projects"):
        res = await get(client, world.research_office, path)
        assert res.json()["error"]["code"] == "module_disabled"


async def test_daily_job_reminds_once(client, world, grants_on, monkeypatch):
    url = f"{API}/internal/cron/daily"
    assert (await client.post(url)).status_code == 404  # CRON_SECRET unset
    secret = "s" * 40
    monkeypatch.setattr(cron, "settings", dataclasses.replace(settings, cron_secret=secret))
    assert (await client.post(url, headers={"X-Cron-Secret": "wrong"})).status_code == 401
    ends = (datetime.now(UTC).date() + timedelta(days=60)).isoformat()
    await fellowship(client, world, start_date="2024-01-01", end_date=ends)
    first = await client.post(url, headers={"X-Cron-Secret": secret})
    assert first.json()["ran"] is True and first.json()["fellowship_reminders"] == 1
    again = await client.post(url, headers={"X-Cron-Secret": secret})
    assert again.json()["ran"] is False
    for user in (world.scholar_a1, world.meera):
        inbox = (await get(client, user, "/notifications")).json()
        assert [n["category"] for n in inbox] == ["fellowship_ending"]
