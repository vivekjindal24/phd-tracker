"""Progress reports end to end over HTTP: create, submit, queue, approve, send back
(PRD F8, UX Flows 1-2)."""

import pytest

from tests.conftest import auth

SUMMARY = "Completed the literature survey and the first experiments on the district panel."


async def _create(client, scholar_user, year=2026, period="January-June"):
    res = await client.post(
        "/api/v1/reports",
        json={"report_year": year, "period": period, "summary": SUMMARY},
        headers=auth(scholar_user.id),
    )
    assert res.status_code == 201, res.text
    return res.json()


async def _act(client, user, item, action, **body):
    return await client.post(
        f"/api/v1/items/progress_report/{item['id']}/{action}",
        json=body or None,
        headers=auth(user.id),
    )


async def _queue_ids(client, user):
    res = await client.get("/api/v1/queue", headers=auth(user.id))
    assert res.status_code == 200, res.text
    return {q["id"] for q in res.json()}


async def test_draft_shows_chain_preview_and_author_controls(client, world):
    r = await _create(client, world.scholar_a1b)
    assert r["state"] == "draft" and r["can_submit"] and r["can_edit"]
    assert [s["label"] for s in r["chain"]] == ["Supervisor", "Department", "Research Office"]
    assert {s["status"] for s in r["chain"]} == {"upcoming"}
    assert r["title"] == "January–June 2026"  # noqa: RUF001


async def test_duplicate_period_is_409(client, world):
    await _create(client, world.scholar_a1b)
    res = await client.post(
        "/api/v1/reports",
        json={"report_year": 2026, "period": "January-June", "summary": SUMMARY},
        headers=auth(world.scholar_a1b.id),
    )
    assert (res.status_code, res.json()["error"]["code"]) == (409, "duplicate_apr")


@pytest.mark.parametrize("who", ["sup_a2", "admin_a1", "research_office"])
async def test_only_scholars_create(client, world, who):
    res = await client.post(
        "/api/v1/reports",
        json={"report_year": 2026, "period": "July-December", "summary": SUMMARY},
        headers=auth(getattr(world, who).id),
    )
    assert res.status_code == 403


async def test_full_chain_through_queues(client, world):
    r = await _create(client, world.scholar_a1b)  # A1 scholar supervised by sup_a2
    r = (await _act(client, world.scholar_a1b, r, "submit")).json()
    assert (r["state"], r["waiting_on"]) == ("in_review", "Supervisor")
    assert r["can_edit"] is False

    assert r["id"] in await _queue_ids(client, world.sup_a2)
    assert r["id"] not in await _queue_ids(client, world.admin_a1)  # not their step yet
    r = (await _act(client, world.sup_a2, r, "approve", comment="Good progress")).json()
    assert r["waiting_on"] == "Department"
    # Department step: A1's head/admin and the Dean above them all see it in their queue.
    for dept in (world.admin_a1, world.meera, world.dean_a):
        assert r["id"] in await _queue_ids(client, dept)
    r = (await _act(client, world.admin_a1, r, "approve")).json()
    r = (await _act(client, world.research_office, r, "approve")).json()
    assert r["state"] == "approved" and r["approved_at"]
    assert [s["status"] for s in r["chain"]] == ["done", "done", "done"]
    assert [(h["action"], h["actor"]) for h in r["history"]] == [
        ("submit", "Scholar A1B"),
        ("approve", "Sup A2"),
        ("approve", "Admin A1"),
        ("approve", "Research Office"),
    ]
    assert r["history"][1]["comment"] == "Good progress"
    seen = (
        await client.get(
            f"/api/v1/items/progress_report/{r['id']}", headers=auth(world.scholar_a1b.id)
        )
    ).json()
    assert seen["state"] == "approved" and seen["can_edit"] is False


async def test_send_back_targets_and_destinations(client, world):
    r = await _create(client, world.scholar_a1b)
    await _act(client, world.scholar_a1b, r, "submit")
    await _act(client, world.sup_a2, r, "approve")
    await _act(client, world.admin_a1, r, "approve")
    view = (
        await client.get(
            f"/api/v1/items/progress_report/{r['id']}", headers=auth(world.research_office.id)
        )
    ).json()
    assert [t["label"] for t in view["send_back_targets"]] == [
        "Back to the scholar",
        "Supervisor",
        "Department",
    ]
    bad = await _act(client, world.research_office, r, "send-back", comment="x", to_step=2)
    assert bad.json()["error"]["code"] == "workflow_violation"
    back = (
        await _act(
            client,
            world.research_office,
            r,
            "send-back",
            comment="Supervisor to re-check",
            to_step=0,
        )
    ).json()
    assert back["waiting_on"] == "Supervisor"
    assert back["history"][-1]["to"] == "Supervisor"


async def test_send_back_needs_a_reason(client, world):
    r = await _create(client, world.scholar_a1b)
    await _act(client, world.scholar_a1b, r, "submit")
    res = await _act(client, world.sup_a2, r, "send-back", comment="")
    assert res.status_code == 422


async def test_author_edits_only_draft_or_sent_back(client, world):
    r = await _create(client, world.scholar_a1b)
    url = f"/api/v1/reports/{r['id']}"
    new = {"summary": SUMMARY + " Updated."}
    assert (
        await client.patch(url, json=new, headers=auth(world.scholar_a1b.id))
    ).status_code == 200
    await _act(client, world.scholar_a1b, r, "submit")
    locked = await client.patch(url, json=new, headers=auth(world.scholar_a1b.id))
    assert locked.json()["error"]["code"] == "workflow_violation"
    await _act(client, world.sup_a2, r, "send-back", comment="Add RAC dates")
    assert (
        await client.patch(url, json=new, headers=auth(world.scholar_a1b.id))
    ).status_code == 200


async def test_blocked_reason_for_consecutive_step(client, world):
    r = await _create(client, world.scholar_a1)  # Meera supervises AND heads A1
    await _act(client, world.scholar_a1, r, "submit")
    after = (await _act(client, world.meera, r, "approve")).json()
    assert after["can_act"] is False and "another approver" in after["blocked_reason"]
    assert r["id"] not in await _queue_ids(client, world.meera)


async def test_scope_on_lists_and_items(client, world):
    r = await _create(client, world.scholar_a1)
    url = f"/api/v1/items/progress_report/{r['id']}"
    for outsider in (world.scholar_b1, world.hod_b1, world.hod_a2):
        assert (await client.get(url, headers=auth(outsider.id))).status_code == 403
    rows = (await client.get("/api/v1/reports", headers=auth(world.hod_b1.id))).json()
    assert rows == []
    assert (await client.get("/api/v1/reports", headers=auth(world.library.id))).status_code == 403


async def test_summary_too_short_is_422(client, world):
    res = await client.post(
        "/api/v1/reports",
        json={"report_year": 2026, "period": "January-June", "summary": "short"},
        headers=auth(world.scholar_a1.id),
    )
    assert res.status_code == 422
