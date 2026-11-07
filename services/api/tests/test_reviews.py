# ruff: noqa: F811
"""External thesis reviewers (PRD M3, UX Flow 8c): an invitation by secure link, a login for one
thesis until the deadline, a review that joins the Exam Office's reports, and a traceable copy."""

import dataclasses
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.config import settings
from app.enums import MODULE_KEYS
from app.main import app
from app.models import AuditLog, FileRow, ThesisReview, ThesisReviewCopy
from app.routers import cron
from tests.conftest import auth
from tests.test_password_links import outbox  # noqa: F401
from tests.test_publications import enable
from tests.test_thesis import approved_thesis, documents_on, evaluation  # noqa: F401

API = "/api/v1"
FUTURE = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()
EMAIL = "prof.reviewer@other.edu"


async def invite(client, world, tid, user=None, **over):
    body = {
        "name": "Prof. Reviewer",
        "email": EMAIL,
        "institution": "Other University",
        "abstract": "A study of low-power inference.",
        "deadline": FUTURE,
    } | over
    return await client.post(
        f"{API}/theses/{tid}/reviews",
        headers=auth((user or world.exam_office).id),
        json=body,
    )


def _newest(mails, pattern: str) -> str:
    """The newest match: notifications to the Exam Office land in the same outbox."""
    found = [m for mail in mails for m in re.findall(pattern, mail.get_content())]
    return found[-1]


def token_in(mails) -> str:
    return _newest(mails, r"/review-invitation/([\w-]+)")


def set_password_token(mails) -> str:
    return _newest(mails, r"/set-password\?token=([\w-]+)")


async def accept(client, token):
    return await client.post(
        f"{API}/review-invitations/{token}/accept",
        json={"no_conflict": True, "confidential": True},
    )


async def reviewer(client, session, world, outbox, tid, **over):
    """An accepted reviewer: (review id, reviewer's auth headers)."""
    res = await invite(client, world, tid, **over)
    assert res.status_code == 201, res.text
    rid = res.json()["id"]
    assert (await accept(client, token_in(outbox))).status_code == 200
    tokens = await client.post(
        f"{API}/auth/set-password",
        json={"token": set_password_token(outbox), "password": "a-long-passphrase"},
    )
    assert tokens.status_code == 200, tokens.text
    return rid, {"Authorization": f"Bearer {tokens.json()['access_token']}"}


async def add_comment(client, headers, rid, page=3, body="Check this claim."):
    return await client.post(
        f"{API}/reviewer/reviews/{rid}/comments",
        headers=headers,
        json={"page": page, "body": body},
    )


async def submit(client, headers, rid, recommendation="minor_revision"):
    return await client.post(
        f"{API}/reviewer/reviews/{rid}/submit",
        headers=headers,
        json={"recommendation": recommendation},
    )


async def test_only_the_exam_office_invites(client, session, world, documents_on, outbox):
    tid = await approved_thesis(client, session, world)
    for user in (world.research_office, world.meera, world.scholar_a1, world.library):
        assert (await invite(client, world, tid, user)).status_code == 403, user.email
    assert (await invite(client, world, tid)).status_code == 201


async def test_a_thesis_must_be_approved_first(client, session, world, documents_on, outbox):
    from tests.test_thesis import new_thesis

    tid = await new_thesis(client, session, world)
    assert (await invite(client, world, tid)).status_code == 422


async def test_invitation_shows_only_title_abstract_and_deadline(
    client, session, world, documents_on, outbox
):
    tid = await approved_thesis(client, session, world)
    await invite(client, world, tid)
    assert EMAIL in [mail["To"] for mail in outbox]
    view = (await client.get(f"{API}/review-invitations/{token_in(outbox)}")).json()
    assert set(view) == {"university", "thesis_title", "abstract", "deadline", "reviewer_name"}
    assert (await client.get(f"{API}/review-invitations/wrong")).status_code == 422


async def test_accepting_needs_both_promises(client, session, world, documents_on, outbox):
    tid = await approved_thesis(client, session, world)
    await invite(client, world, tid)
    res = await client.post(
        f"{API}/review-invitations/{token_in(outbox)}/accept",
        json={"no_conflict": True, "confidential": False},
    )
    assert res.status_code == 422


async def test_decline_tells_the_exam_office(client, session, world, documents_on, outbox):
    tid = await approved_thesis(client, session, world)
    await invite(client, world, tid)
    token = token_in(outbox)
    res = await client.post(
        f"{API}/review-invitations/{token}/decline", json={"reason": "Too busy."}
    )
    assert res.status_code == 204
    assert (await accept(client, token)).status_code == 422
    inbox = (await client.get(f"{API}/notifications", headers=auth(world.exam_office.id))).json()
    assert any("declined" in n["title"] for n in inbox)
    row = (await evaluation(client, world.exam_office, tid)).json()["reviews"][0]
    assert row["status"] == "declined" and row["decline_reason"] == "Too busy."


async def test_staff_cannot_be_reviewers(client, session, world, documents_on, outbox):
    tid = await approved_thesis(client, session, world)
    res = await invite(client, world, tid, email=world.sup_b1.email)
    assert res.status_code == 409 and res.json()["error"]["code"] == "reviewer_is_staff"


async def test_a_reviewer_reaches_nothing_but_their_own_review(
    client, session, world, documents_on, outbox
):
    await enable(session, *MODULE_KEYS)
    tid = await approved_thesis(client, session, world)
    _, headers = await reviewer(client, session, world, outbox, tid)
    opened = {
        "GET /auth/me",
        "PUT /auth/me/email-muted",
        "POST /auth/change-password",
        "POST /files/uploads",
        "POST /files/{file_id}/complete",
        "GET /files",
        "GET /files/{file_id}/download",
        "DELETE /files/{file_id}",
        "GET /internal/reviews/{review_id}/copy",
    }
    for path, item in app.openapi()["paths"].items():
        short = path.removeprefix(API)
        if short.startswith(("/reviewer", "/review-invitations", "/auth/sso")):
            continue
        for method in item:
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            if f"{method.upper()} {short}" in opened or short in (
                "/healthz",
                "/branding",
                "/branding/logo",
                "/verify/{token}",
                "/auth/login",
                "/auth/refresh",
                "/auth/logout",
                "/auth/forgot-password",
                "/auth/set-password",
                "/internal/cron/daily",
            ):
                continue
            url = API + re.sub(r"\{[^}]+\}", str(tid), path.removeprefix(API))
            res = await client.request(method.upper(), url, json={}, headers=headers)
            assert res.status_code == 403, (method, path, res.status_code)
            assert res.json()["error"]["code"] == "reviewers_only_review", (method, path)
    me = (await client.get(f"{API}/auth/me", headers=headers)).json()
    assert me["is_reviewer"] and me["roles"] == []


async def test_a_reviewer_cannot_open_anothers_review(client, session, world, documents_on, outbox):
    tid = await approved_thesis(client, session, world)
    rid, _ = await reviewer(client, session, world, outbox, tid)
    _, other = await reviewer(
        client, session, world, outbox, tid, email="second@other.edu", name="Second"
    )
    res = await client.get(f"{API}/reviewer/reviews/{rid}", headers=other)
    assert res.status_code == 403
    assert (await add_comment(client, other, rid)).status_code == 403


async def test_comments_are_optional_but_a_review_cannot_be_empty(
    client, session, world, documents_on, outbox
):
    tid = await approved_thesis(client, session, world)
    rid, headers = await reviewer(client, session, world, outbox, tid)
    res = await submit(client, headers, rid)
    assert res.status_code == 422 and res.json()["error"]["code"] == "review_is_empty"
    assert (await add_comment(client, headers, rid, page=7)).status_code == 201
    view = (await client.get(f"{API}/reviewer/reviews/{rid}", headers=headers)).json()
    assert [c["page"] for c in view["comments"]] == [7]
    assert (await submit(client, headers, rid)).status_code == 200


async def test_a_file_alone_is_a_review(client, session, world, documents_on, outbox):
    tid = await approved_thesis(client, session, world)
    rid, headers = await reviewer(client, session, world, outbox, tid)
    me = (await client.get(f"{API}/auth/me", headers=headers)).json()
    session.add(
        FileRow(
            storage_key=f"thesis_reviews/{rid}/f/r.pdf",
            file_name="review.pdf",
            content_type="application/pdf",
            size_bytes=10,
            status="ready",
            uploaded_by=me["id"],
            table_name="thesis_reviews",
            record_id=rid,
        )
    )
    await session.commit()
    assert (await submit(client, headers, rid)).status_code == 200
    report = (await evaluation(client, world.exam_office, tid)).json()["reports"][0]
    moved = await session.scalars(select(FileRow).where(FileRow.table_name == "examiner_reports"))
    assert [str(f.record_id) for f in moved] == [report["id"]]


async def test_submitting_locks_the_review_and_joins_the_reports(
    client, session, world, documents_on, outbox
):
    tid = await approved_thesis(client, session, world)
    rid, headers = await reviewer(client, session, world, outbox, tid)
    await add_comment(client, headers, rid, page=7, body="Weak method.")
    assert (await submit(client, headers, rid, "major_revision")).status_code == 200

    assert (await add_comment(client, headers, rid)).status_code == 409
    assert (await submit(client, headers, rid)).status_code == 409
    copy = await client.get(f"{API}/internal/reviews/{rid}/copy", headers=headers)
    assert copy.status_code == 409

    report = (await evaluation(client, world.exam_office, tid)).json()["reports"][0]
    assert report["recommendation"] == "major_revision"
    assert report["examiner_name"] == "Prof. Reviewer" and not report["released"]
    assert report["comments"] == [{"page": 7, "body": "Weak method."}]


async def test_the_scholar_sees_the_review_only_after_release_without_a_name(
    client, session, world, documents_on, outbox
):
    tid = await approved_thesis(client, session, world)
    rid, headers = await reviewer(client, session, world, outbox, tid)
    await add_comment(client, headers, rid, page=7, body="Weak method.")
    await submit(client, headers, rid)
    mine = (await evaluation(client, world.scholar_a1, tid)).json()
    assert (mine["reports"] == [] and "reviews" not in mine) or mine["reviews"] == []

    await client.post(f"{API}/theses/{tid}/release-reports", headers=auth(world.exam_office.id))
    mine = (await evaluation(client, world.scholar_a1, tid)).json()
    assert mine["reviews"] == []
    assert mine["reports"][0]["comments"] == [{"page": 7, "body": "Weak method."}]
    assert mine["reports"][0]["examiner_name"] is None


async def test_access_closes_at_the_deadline_and_extending_reopens_it(
    client, session, world, documents_on, outbox
):
    tid = await approved_thesis(client, session, world)
    rid, headers = await reviewer(client, session, world, outbox, tid)
    await session.execute(
        update(ThesisReview)
        .where(ThesisReview.id == rid)
        .values(deadline=datetime.now(UTC).date() - timedelta(days=3))
    )
    await session.commit()
    res = await add_comment(client, headers, rid)
    assert res.status_code == 409 and res.json()["error"]["code"] == "review_closed"

    patched = await client.patch(
        f"{API}/reviews/{rid}", headers=auth(world.exam_office.id), json={"deadline": FUTURE}
    )
    assert patched.status_code == 200, patched.text
    assert (await add_comment(client, headers, rid)).status_code == 201


async def test_only_the_exam_office_extends(client, session, world, documents_on, outbox):
    tid = await approved_thesis(client, session, world)
    rid, headers = await reviewer(client, session, world, outbox, tid)
    for hdr in (headers, auth(world.research_office.id), auth(world.scholar_a1.id)):
        res = await client.patch(f"{API}/reviews/{rid}", headers=hdr, json={"deadline": FUTURE})
        assert res.status_code == 403


async def test_a_copy_needs_the_toggle_to_download_and_every_copy_is_logged(
    client, session, world, documents_on, outbox, monkeypatch
):
    monkeypatch.setattr("app.reviews.storage.presign_get", lambda key, name: "http://files/x.pdf")
    tid = await approved_thesis(client, session, world)
    rid, headers = await reviewer(client, session, world, outbox, tid)
    url = f"{API}/internal/reviews/{rid}/copy"
    assert (await client.get(url, headers=headers, params={"download": True})).status_code == 403

    view = (await client.get(url, headers=headers)).json()
    assert re.fullmatch(r"[0-9A-F]{4}-[0-9A-F]{4}", view["code"])
    assert view["file_url"] == "http://files/x.pdf"
    second = (await client.get(url, headers=headers)).json()
    assert second["code"] != view["code"]
    copies = (await session.scalars(select(ThesisReviewCopy))).all()
    assert {c.kind for c in copies} == {"view"} and len(copies) == 2

    await client.patch(
        f"{API}/reviews/{rid}",
        headers=auth(world.exam_office.id),
        json={"allow_download": True},
    )
    res = await client.get(url, headers=headers, params={"download": True})
    assert res.status_code == 200


async def test_only_the_exam_office_traces_a_code_and_it_is_audited(
    client, session, world, documents_on, outbox, monkeypatch
):
    monkeypatch.setattr("app.reviews.storage.presign_get", lambda key, name: "http://files/x.pdf")
    tid = await approved_thesis(client, session, world)
    rid, headers = await reviewer(client, session, world, outbox, tid)
    code = (await client.get(f"{API}/internal/reviews/{rid}/copy", headers=headers)).json()["code"]
    for user in (world.research_office, world.root_admin, world.scholar_a1):
        res = await client.get(f"{API}/review-copies/{code}", headers=auth(user.id))
        assert res.status_code == 403
    traced = await client.get(f"{API}/review-copies/{code}", headers=auth(world.exam_office.id))
    assert traced.status_code == 200, traced.text
    assert traced.json()["reviewer_email"] == EMAIL and traced.json()["kind"] == "view"
    assert (
        await client.get(f"{API}/review-copies/0000-0000", headers=auth(world.exam_office.id))
    ).status_code == 404
    rows = (await session.scalars(select(AuditLog).where(AuditLog.action == "lookup"))).all()
    assert len(rows) == 1


async def test_a_guide_in_the_exam_office_cannot_invite(
    client, session, world, documents_on, outbox
):
    from app.models import RoleAssignment

    tid = await approved_thesis(client, session, world)
    session.add(RoleAssignment(user_id=world.meera.id, role="exam_office"))
    await session.commit()
    res = await invite(client, world, tid, world.meera)
    assert res.status_code == 403 and res.json()["error"]["code"] == "own_scholar"


async def test_a_reviewer_list_is_hidden_from_the_scholar_and_guide(
    client, session, world, documents_on, outbox
):
    tid = await approved_thesis(client, session, world)
    await invite(client, world, tid)
    for user in (world.scholar_a1, world.meera, world.library):
        assert (await evaluation(client, user, tid)).json()["reviews"] == []
    assert len((await evaluation(client, world.exam_office, tid)).json()["reviews"]) == 1


async def test_daily_job_expires_reminds_and_closes(
    client, session, world, documents_on, outbox, monkeypatch
):
    secret = "s" * 40
    monkeypatch.setattr(cron, "settings", dataclasses.replace(settings, cron_secret=secret))
    tid = await approved_thesis(client, session, world)
    today = datetime.now(UTC).date()
    await reviewer(
        client, session, world, outbox, tid, deadline=(today + timedelta(days=7)).isoformat()
    )
    stale = (await invite(client, world, tid, email="late@other.edu")).json()["id"]
    await session.execute(
        update(ThesisReview)
        .where(ThesisReview.id == stale)
        .values(invite_expires_at=datetime.now(UTC) - timedelta(hours=1))
    )
    await session.commit()
    res = await client.post(f"{API}/internal/cron/daily", headers={"X-Cron-Secret": secret})
    assert res.json()["review_reminders"] == 1 and res.json()["review_invites_expired"] == 1
    rows = (await evaluation(client, world.exam_office, tid)).json()["reviews"]
    assert {r["status"] for r in rows} == {"accepted", "expired"}


async def test_an_expired_invitation_can_be_resent(client, session, world, documents_on, outbox):
    tid = await approved_thesis(client, session, world)
    rid = (await invite(client, world, tid)).json()["id"]
    old = token_in(outbox)
    await session.execute(
        update(ThesisReview)
        .where(ThesisReview.id == rid)
        .values(invite_expires_at=datetime.now(UTC) - timedelta(hours=1))
    )
    await session.commit()
    assert (await client.get(f"{API}/review-invitations/{old}")).status_code == 422
    res = await client.post(f"{API}/reviews/{rid}/resend", headers=auth(world.exam_office.id))
    assert res.status_code == 200, res.text
    assert token_in(outbox) != old
    assert (await accept(client, token_in(outbox))).status_code == 200


async def test_a_reviewer_reads_no_files_but_their_own(
    client, session, world, documents_on, outbox
):
    tid = await approved_thesis(client, session, world)
    rid, headers = await reviewer(client, session, world, outbox, tid)
    theirs = await client.get(
        f"{API}/files", headers=headers, params={"table_name": "thesis_reviews", "record_id": rid}
    )
    assert theirs.status_code == 200
    thesis_files = await client.get(
        f"{API}/files",
        headers=headers,
        params={"table_name": "thesis_submissions", "record_id": tid},
    )
    assert thesis_files.status_code == 403
    scholar = await client.get(
        f"{API}/files",
        headers=headers,
        params={"table_name": "scholars", "record_id": str(world.s_a1.id)},
    )
    assert scholar.status_code == 403


async def test_upload_closes_with_the_review(client, session, world, documents_on, outbox):
    tid = await approved_thesis(client, session, world)
    rid, headers = await reviewer(client, session, world, outbox, tid)
    await add_comment(client, headers, rid)
    await submit(client, headers, rid)
    res = await client.post(
        f"{API}/files/uploads",
        headers=headers,
        json={
            "table_name": "thesis_reviews",
            "record_id": rid,
            "file_name": "late.pdf",
            "content_type": "application/pdf",
            "size_bytes": 100,
        },
    )
    assert res.status_code == 409 and res.json()["error"]["code"] == "review_closed"


async def test_a_second_invitation_reuses_the_account(client, session, world, documents_on, outbox):
    tid = await approved_thesis(client, session, world)
    rid, headers = await reviewer(client, session, world, outbox, tid)
    await add_comment(client, headers, rid)
    await submit(client, headers, rid)
    assert (await invite(client, world, tid)).status_code == 409  # one per reviewer per thesis
    listed = (await client.get(f"{API}/reviewer/reviews", headers=headers)).json()
    assert [r["status"] for r in listed] == ["submitted"] and not listed[0]["is_open"]
