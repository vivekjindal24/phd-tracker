"""The advisory committee in reviews (PRD F9b, owner 2026-11-26): an approval step a university
may add to the progress report chain, signed by the chairperson (or a member from this
university when the chair is an outside expert); and the committee linked to the scholar's
seminars, apart from the panel."""

from sqlalchemy import select

from app.models import Notification
from tests.conftest import auth
from tests.test_committee import SEN, add, form
from tests.test_daily_job import cron_on, inbox, run_daily  # noqa: F401  (fixture)
from tests.test_reports import _act, _create, _queue_ids
from tests.test_seminars import _schedule, seminar_body
from tests.test_stand_ins import _age

CHAIN = "/api/v1/settings/chains/progress_report"
WITH_COMMITTEE = {"steps": [{"kind": "supervisor"}, {"kind": "committee"}, {"kind": "department"}]}


async def use_committee_step(client, world, body=WITH_COMMITTEE):
    res = await client.put(CHAIN, headers=auth(world.root_admin.id), json=body)
    assert res.status_code == 200, res.text


async def committee_of_s_a1(client, world, chair, member):
    fid = (await form(client, world)).json()["formations"][0]["id"]
    assert (await add(client, world, fid, {**chair, "role": "chairperson"})).status_code == 200
    assert (await add(client, world, fid, member)).status_code == 200


def faculty(f) -> dict:
    return {"faculty_id": str(f.id)}


async def submitted_to_committee(client, world) -> dict:
    report = await _create(client, world.scholar_a1)
    assert (await _act(client, world.scholar_a1, report, "submit")).status_code == 200
    moved = await _act(client, world.meera, report, "approve")
    assert moved.status_code == 200, moved.text
    assert moved.json()["waiting_on"] == "Advisory committee"
    return report


async def get_report(client, user, report):
    return await client.get(f"/api/v1/items/progress_report/{report['id']}", headers=auth(user.id))


async def test_the_internal_chair_signs_and_nobody_else(client, session, world):
    await use_committee_step(client, world)
    await committee_of_s_a1(
        client, world, faculty(world.sup_b1_faculty), faculty(world.sup_a2_faculty)
    )
    report = await submitted_to_committee(client, world)

    told = await session.scalars(
        select(Notification.user_id).where(Notification.category == "approval_waiting")
    )
    assert world.sup_b1.id in set(told)
    assert report["id"] in {str(i) for i in await _queue_ids(client, world.sup_b1)}
    assert (await get_report(client, world.sup_b1, report)).status_code == 200
    # A plain member is not the signer and reads nothing of the scholar's reports.
    assert (await get_report(client, world.sup_a2, report)).status_code == 403
    assert (await _act(client, world.sup_a2, report, "approve")).status_code == 403

    signed = await _act(client, world.sup_b1, report, "approve")
    assert signed.status_code == 200, signed.text
    assert signed.json()["waiting_on"] == "Department"


async def test_an_outside_chair_leaves_it_to_the_members_from_here(client, world):
    await use_committee_step(client, world)
    await committee_of_s_a1(client, world, SEN, faculty(world.sup_a2_faculty))
    report = await submitted_to_committee(client, world)
    signed = await _act(client, world.sup_a2, report, "approve")
    assert signed.status_code == 200, signed.text


async def test_no_member_from_here_stops_the_report_before_the_step(client, world):
    await use_committee_step(client, world)
    report = await _create(client, world.scholar_a1)
    await _act(client, world.scholar_a1, report, "submit")
    stuck = await _act(client, world.meera, report, "approve")
    assert stuck.status_code == 422 and "advisory committee" in stuck.json()["error"]["message"]
    still = await get_report(client, world.meera, report)
    assert still.json()["waiting_on"] == "Supervisor"


async def test_without_the_step_the_committee_reads_no_reports(client, world):
    await committee_of_s_a1(
        client, world, faculty(world.sup_b1_faculty), faculty(world.sup_a2_faculty)
    )
    report = await _create(client, world.scholar_a1)
    await _act(client, world.scholar_a1, report, "submit")
    assert (await get_report(client, world.sup_b1, report)).status_code == 403


async def test_the_step_belongs_to_progress_reports_and_stays_while_in_use(client, world):
    on_papers = await client.put(
        "/api/v1/settings/chains/publication",
        headers=auth(world.root_admin.id),
        json={"steps": [{"kind": "committee"}]},
    )
    assert on_papers.status_code == 422
    assert on_papers.json()["error"]["code"] == "committee_step_reports_only"

    await use_committee_step(client, world)
    await committee_of_s_a1(client, world, SEN, faculty(world.sup_a2_faculty))
    await submitted_to_committee(client, world)
    removed = await client.put(
        CHAIN, headers=auth(world.root_admin.id), json={"steps": [{"kind": "supervisor"}]}
    )
    assert removed.status_code == 409
    assert removed.json()["error"]["code"] == "committee_step_in_use"


async def test_committee_sees_and_hears_of_the_seminar_but_is_not_the_panel(client, session, world):
    await committee_of_s_a1(client, world, SEN, faculty(world.sup_b1_faculty))
    body = seminar_body(world, scholars=[world.s_a1], panel=[world.sup_a2_faculty])
    res = await _schedule(client, world.admin_a1, body)
    assert res.status_code == 201, res.text
    seminar = res.json()
    (row,) = seminar["scholars"]
    assert [(m["name"], m["role"], m["external"]) for m in row["committee"]] == [
        ("Prof. R. Sen", "chairperson", True),
        ("Sup B1", "member", False),
    ]
    assert [p["name"] for p in seminar["panel"]] == ["Sup A2"]

    told = set(
        await session.scalars(
            select(Notification.user_id).where(Notification.category == "seminar")
        )
    )
    assert world.sup_b1.id in told
    seen = await client.get(f"/api/v1/seminars/{seminar['id']}", headers=auth(world.sup_b1.id))
    assert seen.status_code == 200
    # Someone on no committee of these scholars still does not see it.
    other = await client.get(f"/api/v1/seminars/{seminar['id']}", headers=auth(world.co_sup.id))
    assert other.status_code in (403, 404)


async def test_head_or_admin_acts_for_a_silent_committee_after_fourteen_days(
    client, session, world
):
    await use_committee_step(client, world)
    await committee_of_s_a1(
        client, world, faculty(world.sup_b1_faculty), faculty(world.sup_a2_faculty)
    )
    report = await submitted_to_committee(client, world)
    assert (await _act(client, world.admin_a1, report, "approve")).status_code == 422
    await _age(session, report["id"], 13)
    assert (await _act(client, world.admin_a1, report, "approve")).status_code == 422
    await _age(session, report["id"], 1)
    assert report["id"] in {str(i) for i in await _queue_ids(client, world.admin_a1)}
    # Another department's head never, however long it waits.
    assert (await _act(client, world.hod_b1, report, "approve")).status_code == 403
    done = await _act(client, world.admin_a1, report, "approve")
    assert done.status_code == 200, done.text
    committee_step = done.json()["history"][-1]
    assert (committee_step["actor"], committee_step["on_behalf_of"]) == ("Admin A1", "Sup B1")


async def _silent_for(client, session, world, days: int) -> None:
    await use_committee_step(client, world)
    await committee_of_s_a1(client, world, SEN, faculty(world.sup_a2_faculty))
    report = await submitted_to_committee(client, world)
    await _age(session, report["id"], days)


async def test_daily_job_reminds_signer_and_admin_at_seven_days(
    client,
    session,
    world,
    cron_on,  # noqa: F811
):
    await _silent_for(client, session, world, 7)
    assert (await run_daily(client))["approval_reminders"] == 1
    for user in (world.sup_a2, world.admin_a1):  # the signer, and the admin who can chase it
        titles = [t for c, t in await inbox(session, user) if c == "approval_waiting"]
        assert any(t.startswith("Still waiting: Progress report") for t in titles), user.email


async def test_daily_job_tells_head_and_admin_at_fourteen_days(
    client,
    session,
    world,
    cron_on,  # noqa: F811
):
    await _silent_for(client, session, world, 14)
    assert (await run_daily(client))["approval_escalations"] == 1
    for user in (world.dean_a, world.admin_a1):
        assert any(t.startswith("Waiting 14 days") for _, t in await inbox(session, user))
    assert not any(t.startswith("Waiting 14 days") for _, t in await inbox(session, world.hod_b1))
