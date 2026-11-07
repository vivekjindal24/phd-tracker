"""The thesis title comes from the RDC approval (PRD F9, M3): the Research Office records it once,
the thesis and certificate read it, and a printed certificate cannot silently disagree."""

import pytest
from sqlalchemy import select

from app.config import ConfigError, _load_certificate
from app.models import AuditLog, Milestone, ThesisSubmission
from tests.conftest import auth
from tests.test_certificate import issue, passed_thesis, revoke
from tests.test_publications import enable
from tests.test_thesis import new_thesis, record_title

API = "/api/v1"


@pytest.fixture
async def documents_on(session, world):
    await enable(session, "documents")


async def change_title(client, world, milestone_id, title):
    return await client.patch(
        f"{API}/milestones/{milestone_id}",
        headers=auth(world.research_office.id),
        json={"approved_title": title},
    )


async def only_milestone(session):
    return await session.scalar(select(Milestone.id))


async def test_no_thesis_without_an_approved_title(client, world, documents_on):
    res = await client.post(f"{API}/theses", headers=auth(world.scholar_a1.id))
    assert res.status_code == 422 and res.json()["error"]["code"] == "title_not_approved"


async def test_a_scholar_cannot_type_the_title(client, session, world, documents_on):
    await record_title(client, session, world, "Approved by RDC")
    res = await client.post(
        f"{API}/theses", headers=auth(world.scholar_a1.id), json={"title": "My own"}
    )
    assert res.status_code == 201 and res.json()["content"]["title"] == "Approved by RDC"
    edit = await client.patch(
        f"{API}/theses/{res.json()['id']}",
        headers=auth(world.scholar_a1.id),
        json={"title": "My own"},
    )
    assert edit.status_code == 404  # the route is gone


async def test_an_unapproved_decision_gives_no_title(client, session, world, documents_on):
    await record_title(client, session, world, status="Pending")
    res = await client.post(f"{API}/theses", headers=auth(world.scholar_a1.id))
    assert res.status_code == 422


async def test_correcting_the_register_updates_the_thesis_and_is_audited(
    client, session, world, documents_on
):
    tid = await new_thesis(client, session, world)
    res = await change_title(client, world, await only_milestone(session), "Corrected title")
    assert res.status_code == 200 and res.json()["approved_title"] == "Corrected title"
    assert await session.scalar(select(ThesisSubmission.title)) == "Corrected title"
    logged = await session.scalars(
        select(AuditLog).where(AuditLog.table_name == "thesis_submissions")
    )
    assert any(a.data["title"] == "Corrected title" and a.record_id == tid for a in logged)


async def test_a_later_committee_decision_wins(client, session, world, documents_on):
    await record_title(client, session, world, "First", resolution_date="2025-01-01")
    await record_title(client, session, world, "Second", resolution_date="2026-01-01")
    res = await client.post(f"{API}/theses", headers=auth(world.scholar_a1.id))
    assert res.json()["content"]["title"] == "Second"


async def test_only_a_proposal_approval_carries_a_title(client, session, world):
    res = await record_title(client, session, world, milestone_type="viva")
    assert res.status_code == 422 and res.json()["error"]["code"] == "title_not_allowed"
    await record_title(client, session, world)
    moved = await client.patch(
        f"{API}/milestones/{await only_milestone(session)}",
        headers=auth(world.research_office.id),
        json={"milestone_type": "viva"},
    )
    assert moved.status_code == 422


async def test_a_scholar_cannot_change_the_register(client, session, world):
    await record_title(client, session, world)
    res = await client.patch(
        f"{API}/milestones/{await only_milestone(session)}",
        headers=auth(world.scholar_a1.id),
        json={"approved_title": "Mine"},
    )
    assert res.status_code == 403


async def test_a_valid_certificate_locks_the_title_until_revoked(
    client, session, world, documents_on
):
    tid = await passed_thesis(client, session, world)
    assert (await issue(client, world.research_office, tid)).status_code == 200
    milestone = await only_milestone(session)

    res = await change_title(client, world, milestone, "Changed")
    assert res.status_code == 409 and res.json()["error"]["code"] == "certificate_issued"
    assert await session.scalar(select(ThesisSubmission.title)) == "On graphs"

    assert (await revoke(client, world.research_office, tid)).status_code == 200
    assert (await change_title(client, world, milestone, "Changed")).status_code == 200


async def test_a_certificate_needs_an_approved_title(client, session, world, documents_on):
    """A thesis started before titles came from the register."""
    tid = await passed_thesis(client, session, world)
    await session.execute(Milestone.__table__.update().values(approved_title=None))
    await session.commit()
    res = await issue(client, world.research_office, tid)
    assert res.status_code == 422 and res.json()["error"]["code"] == "title_not_approved"


async def test_certificate_export_carries_the_install_wording(client, session, world, documents_on):
    tid = await passed_thesis(client, session, world)
    cert = (await issue(client, world.research_office, tid)).json()["certificates"][0]
    res = await client.get(
        f"{API}/internal/certificates/{cert['id']}/export-view",
        headers=auth(world.research_office.id),
    )
    assert res.status_code == 200
    assert res.json()["degree"] == "Doctor of Philosophy"
    assert res.json()["signatories"] == ["Controller of Examinations", "Registrar"]
    assert "{viva_date}" in res.json()["body"] and res.json()["thesis_title"] == "On graphs"


def test_install_wording_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("CERTIFICATE_DEGREE", "Doctor of Science")
    monkeypatch.setenv("CERTIFICATE_SIGNATORIES", "Dean | Registrar | Vice-Chancellor")
    wording = _load_certificate()
    assert wording.degree == "Doctor of Science"
    assert wording.signatories == ("Dean", "Registrar", "Vice-Chancellor")
    assert wording.opening == "This is to certify that"  # blank keeps the default


def test_a_mistyped_placeholder_stops_startup(monkeypatch):
    monkeypatch.setenv("CERTIFICATE_BODY", "Held on {viva_day}.")
    with pytest.raises(ConfigError, match="viva_day"):
        _load_certificate()
