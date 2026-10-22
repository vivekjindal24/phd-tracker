"""Comments, scholar timeline, search — always the record's own visibility (PRD F11-F13)."""

from datetime import date

from sqlalchemy import select

from app.models import Notification
from tests.conftest import auth

TODAY = date.today().isoformat()
SUMMARY = "Survey finished; first baselines on the district crime panel are promising."


async def _meeting(client, world, **extra):
    res = await client.post(
        "/api/v1/meetings",
        headers=auth(world.meera.id),
        json={
            "scholar_id": str(world.s_a1.id),
            "meeting_date": TODAY,
            "agenda": "Graph baselines review",
            "minutes": "Private notes",
            **extra,
        },
    )
    return res.json()


async def _report(client, world):
    res = await client.post(
        "/api/v1/reports",
        headers=auth(world.scholar_a1.id),
        json={"report_year": 2026, "period": "July-December", "summary": SUMMARY},
    )
    return res.json()


async def _comment(client, user, table, rid, body="Looks good"):
    return await client.post(
        "/api/v1/comments",
        headers=auth(user.id),
        json={"table_name": table, "record_id": rid, "body": body},
    )


async def test_comments_follow_the_record(client, world, session):
    r = await _report(client, world)
    ok = await _comment(client, world.meera, "progress_reports", r["id"], "Tighten section 2")
    assert ok.status_code == 201 and ok.json()["mine"] is True
    thread = (
        await client.get(
            f"/api/v1/comments?table_name=progress_reports&record_id={r['id']}",
            headers=auth(world.scholar_a1.id),
        )
    ).json()
    assert [(c["author"], c["body"], c["mine"]) for c in thread] == [
        ("Meera", "Tighten section 2", False)
    ]
    told = await session.scalar(
        select(Notification.title).where(Notification.user_id == world.scholar_a1.id)
    )
    assert told == "New comment from Meera"
    for outsider in (world.scholar_b1, world.hod_b1):
        assert (await _comment(client, outsider, "progress_reports", r["id"])).status_code == 403


async def test_meeting_comments_need_full_access(client, world):
    m = await _meeting(client, world)
    assert (await _comment(client, world.dean_a, "meetings", m["id"])).status_code == 403
    shared = await _meeting(client, world, shared_with=["unit_heads"])
    assert (await _comment(client, world.dean_a, "meetings", shared["id"])).status_code == 201


async def test_only_authors_delete(client, world):
    r = await _report(client, world)
    c = (await _comment(client, world.meera, "progress_reports", r["id"])).json()
    assert (
        await client.delete(f"/api/v1/comments/{c['id']}", headers=auth(world.scholar_a1.id))
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/comments/{c['id']}", headers=auth(world.meera.id))
    ).status_code == 204


async def test_timeline_merges_records_with_each_viewers_rights(client, world):
    await _meeting(client, world)
    await _report(client, world)
    await client.post(
        "/api/v1/milestones",
        headers=auth(world.research_office.id),
        json={
            "scholar_id": str(world.s_a1.id),
            "milestone_type": "rac_review",
            "status": "Approved",
            "approval_body": "RAC",
            "resolution_number": "RAC/26/3",
            "resolution_date": TODAY,
        },
    )
    url = f"/api/v1/scholars/{world.s_a1.id}/timeline"
    mine = (await client.get(url, headers=auth(world.scholar_a1.id))).json()
    assert {e["kind"] for e in mine} == {"meeting", "report", "decision"}
    assert next(e for e in mine if e["kind"] == "meeting")["title"] == "Graph baselines review"
    dean = (await client.get(url, headers=auth(world.dean_a.id))).json()
    assert next(e for e in dean if e["kind"] == "meeting")["title"] == "Meeting held"
    exam = (await client.get(url, headers=auth(world.exam_office.id))).json()
    assert {e["kind"] for e in exam} == {"decision"}  # no meetings/reports rights
    assert (await client.get(url, headers=auth(world.scholar_b1.id))).status_code == 403


async def test_search_is_scoped_and_respects_redaction(client, world):
    await _meeting(client, world)
    found = (
        await client.get("/api/v1/search?q=PHD-A1", headers=auth(world.research_office.id))
    ).json()
    assert {s["detail"] for s in found["scholars"]} == {"PHD-A1-001", "PHD-A1-002"}
    mine = (await client.get("/api/v1/search?q=PHD", headers=auth(world.scholar_a1.id))).json()
    assert [s["detail"] for s in mine["scholars"]] == ["PHD-A1-001"]
    sup = (await client.get("/api/v1/search?q=baselines", headers=auth(world.meera.id))).json()
    assert [m["title"] for m in sup["meetings"]] == ["Graph baselines review"]
    dean = (await client.get("/api/v1/search?q=baselines", headers=auth(world.dean_a.id))).json()
    assert dean["meetings"] == []  # unshared minutes never surface through search
    short = await client.get("/api/v1/search?q=a", headers=auth(world.dean_a.id))
    assert short.status_code == 422
