"""Provisional certificate (PRD M3): issued after a passed viva, verified in public, revoked
but never deleted."""

from datetime import date

import pytest

from tests.conftest import auth
from tests.test_publications import enable
from tests.test_thesis import add_report, approved_thesis, evaluation, record_viva

API = "/api/v1"


@pytest.fixture
async def documents_on(session, world):
    await enable(session, "documents")


async def passed_thesis(client, session, world) -> str:
    tid = await approved_thesis(client, session, world)
    await add_report(client, world, tid)
    assert (await record_viva(client, world, tid)).status_code == 200
    return tid


async def issue(client, user, tid):
    return await client.post(f"{API}/theses/{tid}/certificate", headers=auth(user.id))


async def revoke(client, user, tid, reason="Issued in error"):
    return await client.post(
        f"{API}/theses/{tid}/certificate/revoke", headers=auth(user.id), json={"reason": reason}
    )


async def test_issue_after_a_passed_viva_and_verify_in_public(client, session, world, documents_on):
    tid = await passed_thesis(client, session, world)
    assert (await evaluation(client, world.research_office, tid)).json()["can_issue_certificate"]

    res = await issue(client, world.research_office, tid)
    assert res.status_code == 200, res.text
    cert = res.json()["certificates"][0]
    assert cert["serial"] == f"{world.root.code}/PHD/{date.today().year}/1"
    assert not res.json()["can_issue_certificate"]

    token = cert["verify_path"].rsplit("/", 1)[-1]
    public = await client.get(f"{API}/verify/{token}")  # no login
    assert public.status_code == 200
    assert public.json() == {
        "name": world.scholar_a1.full_name,
        "thesis_title": "On graphs",
        "unit": world.a1.name,
        "viva_date": public.json()["viva_date"],
        "issued_on": date.today().isoformat(),
        "status": "valid",
    }


async def test_unknown_token_is_404(client, world):
    assert (await client.get(f"{API}/verify/no-such-token")).status_code == 404


async def test_needs_a_passed_viva(client, session, world, documents_on):
    tid = await approved_thesis(client, session, world)
    await add_report(client, world, tid)
    res = await issue(client, world.research_office, tid)
    assert res.status_code == 422 and res.json()["error"]["code"] == "viva_not_passed"
    await record_viva(client, world, tid, outcome="redefend")
    res = await issue(client, world.research_office, tid)
    assert res.status_code == 422 and res.json()["error"]["code"] == "viva_not_passed"


@pytest.mark.parametrize("who", ["exam_office", "library", "meera", "scholar_a1", "root_admin"])
async def test_only_the_research_office_issues_and_revokes(
    client, session, world, documents_on, who
):
    tid = await passed_thesis(client, session, world)
    assert (await issue(client, getattr(world, who), tid)).status_code == 403
    assert (await issue(client, world.research_office, tid)).status_code == 200
    assert (await revoke(client, getattr(world, who), tid)).status_code == 403


async def test_one_live_certificate_per_thesis(client, session, world, documents_on):
    tid = await passed_thesis(client, session, world)
    await issue(client, world.research_office, tid)
    res = await issue(client, world.research_office, tid)
    assert res.status_code == 409 and res.json()["error"]["code"] == "certificate_exists"


async def test_revoked_shows_in_public_and_a_new_one_gets_a_new_serial(
    client, session, world, documents_on
):
    tid = await passed_thesis(client, session, world)
    first = (await issue(client, world.research_office, tid)).json()["certificates"][0]
    res = await revoke(client, world.research_office, tid)
    assert res.status_code == 200, res.text
    kept = res.json()["certificates"][0]
    assert kept["revoked_at"] and kept["revoked_reason"] == "Issued in error"

    token = first["verify_path"].rsplit("/", 1)[-1]
    public = (await client.get(f"{API}/verify/{token}")).json()
    assert public["status"] == "revoked" and "revoked_reason" not in public

    res = await revoke(client, world.research_office, tid)
    assert res.status_code == 422 and res.json()["error"]["code"] == "no_live_certificate"
    again = (await issue(client, world.research_office, tid)).json()["certificates"]
    assert len(again) == 2 and again[0]["serial"].endswith("/2")


async def test_a_revoked_certificate_has_no_export(client, session, world, documents_on):
    tid = await passed_thesis(client, session, world)
    cert = (await issue(client, world.research_office, tid)).json()["certificates"][0]
    path = f"{API}/internal/certificates/{cert['id']}/export-view"
    res = await client.get(path, headers=auth(world.scholar_a1.id))
    assert res.status_code == 200
    assert res.json()["verify_url"].endswith(cert["verify_path"])
    assert res.json()["scholar"] == world.scholar_a1.full_name
    await revoke(client, world.research_office, tid)
    res = await client.get(path, headers=auth(world.scholar_a1.id))
    assert res.status_code == 409 and res.json()["error"]["code"] == "certificate_revoked"


async def test_export_view_stays_in_scope(client, session, world, documents_on):
    tid = await passed_thesis(client, session, world)
    cert = (await issue(client, world.research_office, tid)).json()["certificates"][0]
    path = f"{API}/internal/certificates/{cert['id']}/export-view"
    assert (await client.get(path, headers=auth(world.scholar_b1.id))).status_code == 403
