"""Seminar grading, supervisor review, AI draft, finalise, to-dos (PRD F15)."""

import pytest
from sqlalchemy import select, update

from app import ai
from app.models import Notification, Settings
from tests.conftest import auth

SCORES = {"Progress": 8, "Presentation": 7.5, "Understanding": 9, "Plan": 6}


@pytest.fixture
async def seminar(client, world):
    body = {
        "unit_id": str(world.a1.id),
        "title": "Autumn seminar",
        "starts_at": "2026-11-20T10:00:00+05:30",
        "report_due": "2026-11-13",
        "report_year": 2026,
        "period": "July-December",
        "scholar_ids": [str(world.s_a1.id), str(world.s_a1b.id)],
        "panel_faculty_ids": [str(world.sup_b1_faculty.id), str(world.co_sup_faculty.id)],
    }
    res = await client.post("/api/v1/seminars", json=body, headers=auth(world.admin_a1.id))
    assert res.status_code == 201, res.text
    return res.json()["id"]


def url(seminar, scholar, action):
    return f"/api/v1/seminars/{seminar}/scholars/{scholar.id}/{action}"


async def _grade(client, user, seminar, scholar, scores=None, comment="Add an ablation study."):
    return await client.put(
        url(seminar, scholar, "grade"),
        headers=auth(user.id),
        json={"scores": scores or SCORES, "comment": comment},
    )


async def test_panel_grades_and_scholar_waits_for_finalise(client, world, seminar):
    res = await _grade(client, world.sup_b1, seminar, world.s_a1)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["my_grade"]["total"] == 30.5 and body["my_grade"]["max_total"] == 40
    early = await client.get(url(seminar, world.s_a1, "review"), headers=auth(world.scholar_a1.id))
    assert early.status_code == 403  # not until the supervisor finalises


async def test_regrading_updates_rather_than_duplicates(client, world, seminar):
    await _grade(client, world.sup_b1, seminar, world.s_a1)
    again = await _grade(client, world.sup_b1, seminar, world.s_a1, comment="Revised view.")
    grades = again.json()["grades"]
    assert len(grades) == 1 and grades[0]["comment"] == "Revised view."


async def test_only_panel_members_grade(client, world, seminar):
    res = await _grade(client, world.sup_a2, seminar, world.s_a1)  # supervisor, not on panel
    assert res.status_code == 403


@pytest.mark.parametrize(
    "scores",
    [
        {"Progress": 8},  # missing criteria
        {**SCORES, "Extra": 3},  # unknown criterion
        {**SCORES, "Plan": 11},  # above max
        {**SCORES, "Plan": 6.25},  # two decimals
    ],
)
async def test_scores_are_validated_against_the_rubric(client, world, seminar, scores):
    res = await _grade(client, world.sup_b1, seminar, world.s_a1, scores=scores)
    assert res.status_code == 422


async def test_attending_faculty_need_the_setting(client, world, seminar, session):
    att = f"/api/v1/seminars/{seminar}/attend"
    hidden = await client.post(att, headers=auth(world.sup_a2.id))
    assert hidden.json()["error"]["code"] == "attending_not_allowed"
    await session.execute(update(Settings).values(seminar_graders="panel_and_attending"))
    await session.commit()
    assert (await client.post(att, headers=auth(world.sup_a2.id))).status_code == 204
    assert (await _grade(client, world.sup_a2, seminar, world.s_a1)).status_code == 200


async def test_open_seminars_are_visible_to_any_faculty_only_in_attending_mode(
    client, world, seminar, session
):
    get = f"/api/v1/seminars/{seminar}"
    # Rajesh-like outsider: faculty in B1 who neither supervises nor sits on the panel.
    assert (await client.get(get, headers=auth(world.meera.id))).status_code == 200  # HoD A1
    assert (await client.get(get, headers=auth(world.hod_b1.id))).status_code == 403
    await session.execute(update(Settings).values(seminar_graders="panel_and_attending"))
    await session.commit()
    assert (await client.get(get, headers=auth(world.sup_a2.id))).status_code == 200


async def test_ai_draft_then_finalise_creates_todos(client, world, seminar, session, monkeypatch):
    await _grade(client, world.sup_b1, seminar, world.s_a1, comment="Add an ablation study.")
    await _grade(client, world.co_sup, seminar, world.s_a1, comment="Cite recent GNN work.")
    seen: list[list[str]] = []

    async def fake_ai(comments):
        seen.append(comments)
        return [
            {"part": "experiments_results", "text": "Add an ablation study"},
            {"part": "literature_review", "text": "Cite recent GNN work"},
        ]

    monkeypatch.setattr(ai, "suggest_points", fake_ai)
    drafted = await client.post(url(seminar, world.s_a1, "suggest"), headers=auth(world.meera.id))
    assert drafted.status_code == 200, drafted.text
    assert [p["part"] for p in drafted.json()["draft_points"]] == [
        "experiments_results",
        "literature_review",
    ]
    assert sorted(seen[0]) == ["Add an ablation study.", "Cite recent GNN work."]  # comments only

    points = drafted.json()["draft_points"] + [
        {"part": "writing_presentation", "text": "Fix figures"}
    ]
    done = await client.post(
        url(seminar, world.s_a1, "finalise"), json={"points": points}, headers=auth(world.meera.id)
    )
    assert done.status_code == 200 and done.json()["finalised_at"]
    assert len(done.json()["todos"]) == 3

    review = await client.get(url(seminar, world.s_a1, "review"), headers=auth(world.scholar_a1.id))
    assert review.status_code == 200
    assert {g["grader"] for g in review.json()["grades"]} == {"Sup B1", "Co Sup"}
    locked = await _grade(client, world.sup_b1, seminar, world.s_a1)
    assert locked.json()["error"]["code"] == "already_finalised"
    told = await session.scalar(
        select(Notification.title).where(
            Notification.user_id == world.scholar_a1.id, Notification.title.like("%feedback%")
        )
    )
    assert told == "Your seminar feedback is ready"


async def test_only_the_supervisor_drafts_and_finalises(client, world, seminar):
    await _grade(client, world.sup_b1, seminar, world.s_a1)
    for outsider in (world.sup_b1, world.admin_a1, world.scholar_a1):
        res = await client.post(
            url(seminar, world.s_a1, "finalise"), json={"points": []}, headers=auth(outsider.id)
        )
        assert res.status_code == 403


async def test_finalise_needs_a_grade_and_ai_failures_are_explained(
    client, world, seminar, monkeypatch
):
    none = await client.post(
        url(seminar, world.s_a1b, "finalise"), json={"points": []}, headers=auth(world.sup_a2.id)
    )
    assert none.json()["error"]["code"] == "no_grades"
    no_comments = await client.post(
        url(seminar, world.s_a1b, "suggest"), headers=auth(world.sup_a2.id)
    )
    assert no_comments.json()["error"]["code"] == "no_comments"
    await _grade(client, world.sup_b1, seminar, world.s_a1b)

    async def busy(_):
        raise ai.AiUnavailable("the AI service answered 503")

    monkeypatch.setattr(ai, "suggest_points", busy)
    res = await client.post(url(seminar, world.s_a1b, "suggest"), headers=auth(world.sup_a2.id))
    assert res.status_code == 503 and "write them yourself" in res.json()["error"]["message"]


async def test_todos_are_ticked_only_by_their_scholar(client, world, seminar):
    await _grade(client, world.sup_b1, seminar, world.s_a1)
    await client.post(
        url(seminar, world.s_a1, "finalise"),
        headers=auth(world.meera.id),
        json={"points": [{"part": "methodology", "text": "Justify the sampling"}]},
    )
    todos = (await client.get("/api/v1/todos", headers=auth(world.scholar_a1.id))).json()
    assert [t["text"] for t in todos] == ["Justify the sampling"]
    tid = todos[0]["id"]
    ticked = await client.patch(
        f"/api/v1/todos/{tid}", json={"status": "done"}, headers=auth(world.scholar_a1.id)
    )
    assert ticked.json()["status"] == "done" and ticked.json()["done_at"]
    by_sup = await client.patch(
        f"/api/v1/todos/{tid}", json={"status": "open"}, headers=auth(world.meera.id)
    )
    assert by_sup.status_code == 403
    sup_view = (
        await client.get(f"/api/v1/todos?scholar_id={world.s_a1.id}", headers=auth(world.meera.id))
    ).json()
    assert len(sup_view) == 1
    other = (await client.get("/api/v1/todos", headers=auth(world.scholar_b1.id))).json()
    assert other == []


def test_ai_reply_parsing_is_defensive():
    fenced = '```json\n{"points": [{"part": "nonsense", "text": " Fix it "}, {"text": ""}]}\n```'
    assert ai._parse(fenced) == [{"part": "other", "text": "Fix it"}]
    with pytest.raises(ai.AiUnavailable):
        ai._parse("I think the scholar should...")
    with pytest.raises(ai.AiUnavailable):
        ai._parse('{"points": "none"}')


async def test_ai_retries_once_when_busy(monkeypatch):
    import dataclasses

    import httpx

    from app.config import Ai, settings

    monkeypatch.setattr(
        ai,
        "settings",
        dataclasses.replace(settings, ai=Ai(base_url="https://ai.test/v1", api_key="k", model="m")),
    )
    monkeypatch.setattr(ai, "RETRY_DELAY_S", 0)
    calls = []
    reply = {
        "choices": [
            {"message": {"content": '{"points": [{"part": "methodology", "text": "Justify"}]}'}}
        ]
    }

    def handler(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json=reply)

    points = await ai.suggest_points(
        ["Justify the method."], transport=httpx.MockTransport(handler)
    )
    assert points == [{"part": "methodology", "text": "Justify"}] and len(calls) == 2
    sent = calls[0].read().decode()
    assert "Justify the method." in sent and calls[0].headers["authorization"] == "Bearer k"

    calls.clear()
    with pytest.raises(ai.AiUnavailable):
        await ai.suggest_points(["x"], transport=httpx.MockTransport(lambda r: httpx.Response(503)))
