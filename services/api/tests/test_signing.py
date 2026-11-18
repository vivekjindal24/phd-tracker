"""Signing approvals (PRD F17b): while the university requires it, an approve or send-back needs
a confirmed specimen signature and a fresh code, from the authenticator app or emailed."""

import dataclasses
import re
import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import update

from app import notify
from app.auth import totp
from app.config import Smtp, settings
from app.models import Module, Settings, Signature, User
from tests.conftest import auth

API = "/api/v1"
SMTP = Smtp(host="smtp.test", port=587, user="u", password="p", mail_from="noreply@x.edu")
PUB = {
    "title": "Graph learning for crop yield",
    "authors": "A. Scholar, M. Iyer",
    "pub_type": "journal",
    "venue": "Journal of Things",
    "pub_year": 2025,
    "pub_status": "published",
    "indexing": ["scopus"],
}


@pytest.fixture
def outbox(monkeypatch):
    monkeypatch.setattr(notify, "settings", dataclasses.replace(settings, smtp=SMTP))
    sent = []

    async def fake_send(msg):
        sent.append(msg)

    monkeypatch.setattr(notify, "_send", fake_send)
    return sent


@pytest.fixture
async def pub(session, client, world):
    """A publication waiting at the supervisor step (Meera), with signing switched on."""
    await session.execute(update(Module).where(Module.key == "publications").values(enabled=True))
    await session.execute(update(Settings).where(Settings.id == 1).values(require_signing=True))
    await session.commit()
    scholar = auth(world.scholar_a1.id)
    res = await client.post(f"{API}/publications", headers=scholar, json=PUB)
    assert res.status_code == 201, res.text
    pub_id = res.json()["id"]
    res = await client.post(f"{API}/items/publication/{pub_id}/submit", headers=scholar, json={})
    assert res.status_code == 200, res.text
    return pub_id


async def specimen(session, user, confirmed_by):
    session.add(
        Signature(
            user_id=user.id,
            content=b"\x89PNG\r\n\x1a\n",
            content_type="image/png",
            uploaded_by=confirmed_by.id,
            confirmed_by=confirmed_by.id,
            confirmed_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def act(client, user, pub_id, action="approve", **body):
    return await client.post(
        f"{API}/items/publication/{pub_id}/{action}", headers=auth(user.id), json=body
    )


async def send_code(client, user, pub_id, action="approve"):
    return await client.post(
        f"{API}/items/publication/{pub_id}/signing-code",
        headers=auth(user.id),
        json={"action": action},
    )


def code_in(msg) -> str:
    return re.search(r"^\s+(\d{6})$", msg.get_content(), re.M).group(1)


def error(res) -> str:
    return res.json()["error"]["code"]


async def test_no_signature_on_file_signs_nothing(client, world, pub):
    res = await act(client, world.meera, pub)
    assert res.status_code == 422 and error(res) == "signature_required"


async def test_an_emailed_code_signs_once(session, client, world, pub, outbox):
    await specimen(session, world.meera, world.research_office)
    res = await act(client, world.meera, pub)
    assert res.status_code == 422 and error(res) == "signing_code_required"
    assert res.json()["error"]["details"] == {"method": "email"}

    assert (await send_code(client, world.meera, pub)).status_code == 204
    code = code_in(outbox[-1])
    assert outbox[-1]["To"] == world.meera.email

    res = await act(client, world.meera, pub, code="000000" if code != "000000" else "111111")
    assert res.status_code == 403 and error(res) == "invalid_code"
    res = await act(client, world.meera, pub, code=code)
    assert res.status_code == 200, res.text
    assert res.json()["waiting_on"] != "Supervisor"


async def test_a_code_is_bound_to_its_action(session, client, world, pub, outbox):
    await specimen(session, world.meera, world.research_office)
    await send_code(client, world.meera, pub, "send_back")
    res = await act(client, world.meera, pub, code=code_in(outbox[-1]))
    assert res.status_code == 422 and error(res) == "signing_code_expired"


async def test_five_wrong_tries_end_a_code(session, client, world, pub, outbox):
    await specimen(session, world.meera, world.research_office)
    await send_code(client, world.meera, pub)
    code = code_in(outbox[-1])
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert (await act(client, world.meera, pub, code=wrong)).status_code == 403
    res = await act(client, world.meera, pub, code=code)
    assert res.status_code == 422 and error(res) == "signing_code_expired"


async def test_codes_are_not_sent_back_to_back(session, client, world, pub, outbox):
    await specimen(session, world.meera, world.research_office)
    assert (await send_code(client, world.meera, pub)).status_code == 204
    assert (await send_code(client, world.meera, pub)).status_code == 429


async def test_only_whoever_can_act_gets_a_code(session, client, world, pub, outbox):
    res = await send_code(client, world.sup_a2, pub)
    assert res.status_code in (403, 422)
    assert outbox == []


async def test_without_email_signing_needs_the_authenticator(session, client, world, pub):
    await specimen(session, world.meera, world.research_office)
    res = await send_code(client, world.meera, pub)
    assert res.status_code == 422 and error(res) == "signing_needs_authenticator"


async def test_the_authenticator_signs_when_set_up(session, client, world, pub):
    await specimen(session, world.meera, world.research_office)
    secret = totp.new_secret()
    await session.execute(
        update(User)
        .where(User.id == world.meera.id)
        .values(totp_secret=secret, totp_enabled_at=datetime.now(UTC))
    )
    await session.commit()
    res = await act(client, world.meera, pub)
    assert error(res) == "signing_code_required"
    assert res.json()["error"]["details"] == {"method": "authenticator"}
    good = totp.code(secret, time.time())
    res = await act(client, world.meera, pub, code=str((int(good) + 1) % 10**6).zfill(6))
    assert res.status_code == 403 and error(res) == "invalid_code"
    res = await act(client, world.meera, pub, code=good)
    assert res.status_code == 200, res.text


async def test_send_back_is_signed_too(session, client, world, pub, outbox):
    await specimen(session, world.meera, world.research_office)
    res = await act(client, world.meera, pub, "send-back", comment="Add the DOI")
    assert error(res) == "signing_code_required"
    await send_code(client, world.meera, pub, "send_back")
    res = await act(
        client, world.meera, pub, "send-back", comment="Add the DOI", code=code_in(outbox[-1])
    )
    assert res.status_code == 200, res.text
    assert res.json()["state"] == "sent_back"


async def test_no_bulk_approval_while_signing_is_on(client, world, pub):
    res = await client.get(f"{API}/queue", headers=auth(world.meera.id))
    assert [e["quick_approve"] for e in res.json()] == [False]
