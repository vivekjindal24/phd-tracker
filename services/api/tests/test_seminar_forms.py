"""Seminar kinds (PRD F15): progress seminars review a report period; registration and
pre-synopsis seminars do not. Each kind is marked by rubric scores or by the university's own
form questions with a recommendation, chosen per kind in settings.seminar_forms."""

from tests.conftest import approved_stages, auth

API = "/api/v1"


def body(world, kind="registration", **over):
    return {
        "unit_id": str(world.a1.id),
        "kind": kind,
        "title": "Proposal seminar",
        "starts_at": "2026-11-20T10:00:00+05:30",
        "scholar_ids": [str(world.s_a1.id)],
        "panel_faculty_ids": [str(world.sup_b1_faculty.id)],
    } | over


async def schedule(client, world, **kw):
    return await client.post(
        f"{API}/seminars", json=body(world, **kw), headers=auth(world.admin_a1.id)
    )


async def grade(client, seminar_id, world, payload):
    return await client.put(
        f"{API}/seminars/{seminar_id}/scholars/{world.s_a1.id}/grade",
        headers=auth(world.sup_b1.id),
        json=payload,
    )


async def questions(client, world, kind):
    res = await client.get(f"{API}/settings", headers=auth(world.root_admin.id))
    return res.json()["seminar_forms"][kind]["questions"]


async def test_only_progress_seminars_review_a_report_period(client, world):
    res = await schedule(client, world)
    assert res.status_code == 201, res.text
    assert res.json()["kind"] == "registration" and res.json()["report_due"] is None
    # Report fields on another kind, or missing on a progress seminar, are refused.
    assert (await schedule(client, world, report_due="2026-11-13")).status_code == 422
    assert (await schedule(client, world, kind="progress")).status_code == 422
    seminar_id = res.json()["id"]
    res = await client.patch(
        f"{API}/seminars/{seminar_id}",
        headers=auth(world.admin_a1.id),
        json={"report_due": "2026-11-13"},
    )
    assert res.status_code == 422 and res.json()["error"]["code"] == "no_report"


async def test_form_questions_and_a_recommendation(client, world):
    seminar_id = (await schedule(client, world)).json()["id"]
    asked = await questions(client, world, "registration")
    answers = [{"question": q, "answer": "yes"} for q in asked]

    review = await client.get(
        f"{API}/seminars/{seminar_id}/scholars/{world.s_a1.id}/review",
        headers=auth(world.sup_b1.id),
    )
    assert review.json()["form"]["marking"] == "questions"

    res = await grade(client, seminar_id, world, {"answers": answers})
    assert res.status_code == 422 and res.json()["error"]["code"] == "recommendation_required"
    res = await grade(
        client, seminar_id, world, {"answers": answers[:-1], "recommendation": "recommended"}
    )
    assert res.status_code == 422 and res.json()["error"]["code"] == "answers_mismatch"

    answers[1] = {"question": asked[1], "answer": "no", "remark": "Add recent work."}
    res = await grade(
        client,
        seminar_id,
        world,
        {"answers": answers, "recommendation": "recommended_with_changes", "comment": "Revise."},
    )
    assert res.status_code == 200, res.text
    mine = res.json()["my_grade"]
    assert mine["recommendation"] == "recommended_with_changes"
    assert mine["answers"][1] == {
        "question": asked[1],
        "answer": "no",
        "remark": "Add recent work.",
    }
    assert res.json()["average_percent"] is None  # no rubric scores to average


async def test_a_university_can_mark_a_kind_by_rubric_instead(client, world):
    res = await client.patch(
        f"{API}/settings",
        headers=auth(world.root_admin.id),
        json={"seminar_forms": {"pre_synopsis": {"marking": "rubric"}}},
    )
    assert res.status_code == 200, res.text
    forms = res.json()["seminar_forms"]
    assert forms["pre_synopsis"]["marking"] == "rubric"
    assert forms["registration"]["marking"] == "questions"  # the other kinds are kept

    seminar_id = (await schedule(client, world, kind="pre_synopsis")).json()["id"]
    scores = {"Progress": 8, "Presentation": 7, "Understanding": 9, "Plan": 6}
    res = await grade(client, seminar_id, world, {"scores": scores})
    assert res.status_code == 200, res.text
    assert res.json()["my_grade"]["total"] == 30


async def test_the_university_writes_its_own_form(client, world):
    own = {
        "marking": "questions",
        "form_name": "Form VII",
        "questions": ["Is the literature review satisfactory?", "Is the problem formulated?"],
    }
    res = await client.patch(
        f"{API}/settings",
        headers=auth(world.root_admin.id),
        json={"seminar_forms": {"registration": own}},
    )
    assert res.status_code == 200 and res.json()["seminar_forms"]["registration"] == own
    bad = own | {"questions": []}
    res = await client.patch(
        f"{API}/settings",
        headers=auth(world.root_admin.id),
        json={"seminar_forms": {"registration": bad}},
    )
    assert res.status_code == 422
    res = await client.patch(
        f"{API}/settings",
        headers=auth(world.admin_a1.id),
        json={"seminar_forms": {"registration": own}},
    )
    assert res.status_code == 403


async def test_a_registration_seminar_goes_on_to_the_register(client, world, session):
    seminar_id = (await schedule(client, world)).json()["id"]
    answers = [
        {"question": q, "answer": "yes"} for q in await questions(client, world, "registration")
    ]
    await grade(client, seminar_id, world, {"answers": answers, "recommendation": "recommended"})
    register = f"{API}/milestones?scholar_id={world.s_a1.id}"
    assert (await client.get(register, headers=auth(world.admin_a1.id))).json() == []

    done = await client.post(
        f"{API}/seminars/{seminar_id}/scholars/{world.s_a1.id}/finalise",
        headers=auth(world.meera.id),
        json={"points": []},
    )
    assert done.status_code == 200, done.text
    (entry,) = (await client.get(register, headers=auth(world.admin_a1.id))).json()
    assert (entry["milestone_type"], entry["status"], entry["seminar_id"]) == (
        "proposal_approval",
        "Pending",
        seminar_id,
    )
    assert "registration seminar of 20 Nov 2026" in entry["notes"]
    assert "1 recommended" in entry["notes"]
    # The committee's decision is recorded on it as on any entry (the title comes with it).
    await approved_stages(session, world.s_a1.id, "coursework")
    decided = await client.patch(
        f"{API}/milestones/{entry['id']}",
        headers=auth(world.research_office.id),
        json={
            "status": "Approved",
            "resolution_number": "RDC/2026/31",
            "approved_title": "Water quality of district ponds",
        },
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "Approved" and decided.json()["seminar_id"] == seminar_id
