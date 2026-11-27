"""Personal data under the DPDP Act 2023 (privacy.py): the notice everyone reads once and again
when it changes; each person's summary; requests answered by the privacy officer (the root
admins until one is named), kept out of the audit trail."""

from sqlalchemy import select

from app.models import AuditLog, Notification
from tests.conftest import auth

API = "/api/v1/privacy"


async def me(client, user) -> dict:
    return (await client.get("/api/v1/auth/me", headers=auth(user.id))).json()


async def test_notice_is_public_and_starts_as_the_draft(client, world):
    notice = (await client.get(API)).json()
    assert notice["is_draft"] and notice["university"] == "Test University"
    assert notice["text"].startswith("Test University uses Anveshan")
    assert notice["officer"] is None
    assert {p["service"] for p in notice["processors"]} >= {"File storage", "Crossref and ORCID"}


async def test_read_once_and_again_after_a_change(client, world):
    assert (await me(client, world.scholar_a1))["privacy_notice_due"]
    assert (await client.post(f"{API}/seen", headers=auth(world.scholar_a1.id))).status_code == 204
    assert not (await me(client, world.scholar_a1))["privacy_notice_due"]

    root = auth(world.root_admin.id)
    same = await client.patch("/api/v1/settings", headers=root, json={"privacy_notice": ""})
    assert same.status_code == 200
    assert not (await me(client, world.scholar_a1))["privacy_notice_due"]  # nothing changed
    ours = "Our own notice."
    await client.patch("/api/v1/settings", headers=root, json={"privacy_notice": ours})
    assert (await me(client, world.scholar_a1))["privacy_notice_due"]
    notice = (await client.get(API)).json()
    assert notice["text"] == ours and not notice["is_draft"]


async def test_only_the_root_admin_names_the_officer(client, world):
    body = {"user_id": str(world.research_office.id)}
    for who in (world.research_office, world.admin_a1):
        res = await client.put("/api/v1/settings/privacy-officer", headers=auth(who.id), json=body)
        assert res.status_code == 403
    named = await client.put(
        "/api/v1/settings/privacy-officer", headers=auth(world.root_admin.id), json=body
    )
    assert named.status_code == 200
    officer = (await client.get(API)).json()["officer"]
    assert officer == {
        "name": world.research_office.full_name,
        "email": world.research_office.email,
    }


async def test_summary_holds_the_persons_own_data(client, world):
    res = await client.get(f"{API}/my-data", headers=auth(world.scholar_a1.id))
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]
    data = res.json()
    assert data["account"]["email"] == world.scholar_a1.email
    assert data["scholar"]["roll_number"] == world.s_a1.roll_number
    assert data["scholar"]["supervisor"] == world.meera.full_name
    assert "faculty" not in data
    faculty = (await client.get(f"{API}/my-data", headers=auth(world.sup_a2.id))).json()
    assert "scholar" not in faculty and faculty["faculty"]["designation"]


async def test_requests_go_to_the_officer_and_the_answer_back(client, session, world):
    await client.put(
        "/api/v1/settings/privacy-officer",
        headers=auth(world.root_admin.id),
        json={"user_id": str(world.research_office.id)},
    )
    asked = await client.post(
        f"{API}/requests",
        headers=auth(world.scholar_a1.id),
        json={"kind": "correction", "details": "My father's name is misspelt."},
    )
    assert asked.status_code == 201, asked.text
    rid = asked.json()["id"]
    told = await session.scalars(
        select(Notification.user_id).where(Notification.category == "data_request")
    )
    assert list(told) == [world.research_office.id]

    # Nobody else reads the list or answers.
    for who in (world.root_admin, world.admin_a1, world.scholar_b1):
        assert (await client.get(f"{API}/requests", headers=auth(who.id))).status_code == 403
    listed = (await client.get(f"{API}/requests", headers=auth(world.research_office.id))).json()
    assert [(r["requester"], r["status"]) for r in listed] == [(world.scholar_a1.full_name, "open")]
    assert (await me(client, world.research_office))["answers_data_requests"]

    reply = {"reply": "Corrected by your department admin."}
    stranger = await client.post(
        f"{API}/requests/{rid}/answer", headers=auth(world.admin_a1.id), json=reply
    )
    assert stranger.status_code == 403
    done = await client.post(
        f"{API}/requests/{rid}/answer", headers=auth(world.research_office.id), json=reply
    )
    assert done.status_code == 200 and done.json()["status"] == "answered"
    again = await client.post(
        f"{API}/requests/{rid}/answer", headers=auth(world.research_office.id), json=reply
    )
    assert again.status_code == 409
    mine = (await client.get(f"{API}/requests/mine", headers=auth(world.scholar_a1.id))).json()
    assert mine[0]["reply"] == reply["reply"]
    others = (await client.get(f"{API}/requests/mine", headers=auth(world.scholar_b1.id))).json()
    assert others == []

    # The words stay on the request: the audit trail records that it happened, not what it said.
    logged = await session.scalars(select(AuditLog).where(AuditLog.table_name == "data_requests"))
    for entry in logged:
        for side in (entry.prev or {}, entry.data or {}):
            assert side.get("details") in (None, "[redacted]")
            assert side.get("reply") in (None, "[redacted]")


async def test_root_admins_answer_while_no_officer_is_named(client, world):
    await client.post(
        f"{API}/requests",
        headers=auth(world.scholar_a1.id),
        json={"kind": "erasure", "details": "Remove my WhatsApp number."},
    )
    listed = await client.get(f"{API}/requests", headers=auth(world.root_admin.id))
    assert listed.status_code == 200 and len(listed.json()) == 1


async def test_bad_requests_are_refused(client, world):
    for body in ({"kind": "gossip", "details": "x"}, {"kind": "other", "details": "  "}):
        res = await client.post(f"{API}/requests", headers=auth(world.scholar_a1.id), json=body)
        assert res.status_code == 422
