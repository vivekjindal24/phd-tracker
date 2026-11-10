"""What a progress report holds (PRD F8): the sections of the university's template, files,
each approver's rating with written remarks, and the period's activity."""

from tests.conftest import APR_SECTIONS, ASSESS, auth

API = "/api/v1"
SUMMARY = "Completed the literature survey and the first experiments on the district panel."


async def create(client, user, sections=None):
    body = {"report_year": 2026, "period": "January-June", "summary": SUMMARY}
    if sections is not None:
        body["sections"] = sections
    return await client.post(f"{API}/reports", headers=auth(user.id), json=body)


async def act(client, user, rid, action, body=None):
    return await client.post(
        f"{API}/items/progress_report/{rid}/{action}", headers=auth(user.id), json=body
    )


async def test_a_draft_may_be_partial_but_a_submission_is_complete(client, world):
    draft = await create(client, world.scholar_a1, APR_SECTIONS[:1])
    assert draft.status_code == 201, draft.text
    rid = draft.json()["id"]
    assert [s["name"] for s in draft.json()["content"]["sections"]] == [APR_SECTIONS[0]["name"]]
    early = await act(client, world.scholar_a1, rid, "submit")
    assert early.status_code == 422
    assert "Plan for the next six months" in early.json()["error"]["message"]
    full = await client.patch(
        f"{API}/reports/{rid}", headers=auth(world.scholar_a1.id), json={"sections": APR_SECTIONS}
    )
    assert len(full.json()["content"]["sections"]) == 4
    assert (await act(client, world.scholar_a1, rid, "submit")).status_code == 200
    unknown = await create(client, world.scholar_a2, [{"name": "Made up", "text": "x"}])
    assert unknown.status_code == 422 and unknown.json()["error"]["code"] == "unknown_section"


async def test_approving_needs_a_rating_and_remarks(client, world):
    rid = (await create(client, world.scholar_a1b, APR_SECTIONS)).json()["id"]
    await act(client, world.scholar_a1b, rid, "submit")
    for body in (None, {"comment": "Fine"}, {"rating": "satisfactory"}):
        bare = await act(client, world.sup_a2, rid, "approve", body)
        assert bare.status_code == 422 and "rating" in bare.json()["error"]["message"], body
    # Someone not at the step still gets the ordinary refusal.
    other = await act(client, world.library, rid, "approve", ASSESS)
    assert other.status_code in (403, 422)
    ok = await act(
        client,
        world.sup_a2,
        rid,
        "approve",
        {"rating": "needs_improvement", "comment": "Experiments are behind the plan."},
    )
    assert ok.status_code == 200, ok.text
    last = ok.json()["history"][-1]
    assert (last["rating"], last["comment"]) == (
        "needs_improvement",
        "Experiments are behind the plan.",
    )


async def test_the_university_may_set_its_own_template(client, world):
    root = auth(world.root_admin.id)
    own = [{"name": "Objectives", "hint": ""}, {"name": "Outcome", "hint": "What changed"}]
    saved = await client.patch(
        f"{API}/settings", headers=root, json={"apr_custom_template": True, "apr_sections": own}
    )
    assert saved.status_code == 200, saved.text
    assert [s["name"] for s in saved.json()["apr_template"]] == ["Objectives", "Outcome"]
    assert (await create(client, world.scholar_a1, APR_SECTIONS)).status_code == 422
    mine = [{"name": "Objectives", "text": "Done."}, {"name": "Outcome", "text": "A model."}]
    rid = (await create(client, world.scholar_a2, mine)).json()["id"]
    assert (await act(client, world.scholar_a2, rid, "submit")).status_code == 200
    # Switching the toggle off returns to the standard template and keeps theirs for later.
    off = await client.patch(f"{API}/settings", headers=root, json={"apr_custom_template": False})
    assert len(off.json()["apr_template"]) == 4 and len(off.json()["apr_sections"]) == 2
    dup = [{"name": "A", "hint": ""}, {"name": "a", "hint": ""}]
    bad = await client.patch(f"{API}/settings", headers=root, json={"apr_sections": dup})
    assert bad.status_code == 422


async def test_files_follow_the_report(client, world):
    rid = (await create(client, world.scholar_a1, APR_SECTIONS)).json()["id"]
    params = {"table_name": "progress_reports", "record_id": rid}
    for user, status in ((world.scholar_a1, 200), (world.meera, 200), (world.scholar_a2, 403)):
        res = await client.get(f"{API}/files", headers=auth(user.id), params=params)
        assert res.status_code == status, user.email
    upload = {
        **params,
        "file_name": "report.pdf",
        "content_type": "application/pdf",
        "size_bytes": 1000,
    }
    mine = await client.post(f"{API}/files/uploads", headers=auth(world.scholar_a1.id), json=upload)
    assert mine.status_code == 201, mine.text
    theirs = await client.post(f"{API}/files/uploads", headers=auth(world.meera.id), json=upload)
    assert theirs.status_code in (403, 422)


async def test_activity_of_the_period(client, world):
    await client.post(
        f"{API}/meetings",
        headers=auth(world.meera.id),
        json={"scholar_id": str(world.s_a1.id), "meeting_date": "2026-03-05", "agenda": "Plan"},
    )
    await client.post(
        f"{API}/meetings",
        headers=auth(world.meera.id),
        json={"scholar_id": str(world.s_a1.id), "meeting_date": "2026-09-05", "agenda": "Later"},
    )
    rid = (await create(client, world.scholar_a1, APR_SECTIONS)).json()["id"]
    activity = await client.get(f"{API}/reports/{rid}/activity", headers=auth(world.meera.id))
    assert activity.status_code == 200, activity.text
    assert activity.json()["meetings"] == 1
    export = await client.get(
        f"{API}/internal/reports/{rid}/export-view", headers=auth(world.scholar_a1.id)
    )
    body = export.json()
    assert body["activity"]["meetings"] == 1 and len(body["sections"]) == 4
    assert body["files"] == []
