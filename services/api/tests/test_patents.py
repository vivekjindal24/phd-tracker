"""Patents (PRD M10, patents.py): recorded by a member of faculty or a scholar, verified or
returned by the office the university chose, counted in NAAC once verified. No chain."""

import pytest
from sqlalchemy import select, update

from app.crud import insert
from app.models import Faculty, Module, Notification, Settings
from tests.conftest import auth
from tests.test_publications import PUB, enable

API = "/api/v1/patents"
FILED = {
    "title": "A seed-sorting machine",
    "inventors": "A. Inventor, B. Inventor",
    "application_number": "202441000111",
    "filed_on": "2024-03-01",
    "patent_status": "filed",
}
GRANTED = FILED | {
    "patent_status": "granted",
    "published_on": "2024-09-06",
    "granted_on": "2025-02-10",
    "patent_number": "IN 512345",
}


@pytest.fixture(autouse=True)
async def modules_on(session, world):
    await enable(session, "patents", "publications")


async def add(client, user, **over) -> dict:
    res = await client.post(API, headers=auth(user.id), json=FILED | over)
    assert res.status_code == 201, res.text
    return res.json()


async def act(client, user, pid, step, body=None):
    return await client.post(f"{API}/{pid}/{step}", headers=auth(user.id), json=body or {})


async def notices(session, user) -> list[Notification]:
    rows = select(Notification).where(Notification.user_id == user.id)
    return list(await session.scalars(rows.order_by(Notification.created_at)))


async def choose(session, office: str) -> None:
    await session.execute(update(Settings).values(patent_verifier=office))
    await session.commit()


async def test_faculty_and_scholars_record_their_own(client, session, world):
    mine = await add(client, world.sup_a2)
    assert mine["owner_kind"] == "faculty" and mine["verifier"] == "research_office"
    theirs = await add(client, world.scholar_a1, application_number="2024-B")
    assert theirs["owner_kind"] == "scholar" and theirs["can_edit"]
    assert len(await notices(session, world.research_office)) == 2
    assert await notices(session, world.library) == []
    refused = await client.post(API, headers=auth(world.library.id), json=FILED)
    assert refused.status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        FILED | {"patent_status": "granted", "granted_on": "2025-01-01"},  # no patent number
        FILED | {"patent_status": "published"},  # no publication date
        FILED | {"published_on": "2023-01-01"},  # before it was filed
    ],
)
async def test_status_and_dates_agree(client, world, body):
    res = await client.post(API, headers=auth(world.sup_a2.id), json=body)
    assert res.status_code == 422


@pytest.mark.parametrize(
    ("who", "faculty_status", "scholar_status"),
    [
        ("research_office", 200, 200),
        ("library", 200, 200),
        ("vice_chancellor", 200, 200),
        ("root_admin", 200, 200),
        ("hod_a2", 200, 403),  # the faculty patent is A2's; the scholar's is A1's
        ("dean_a", 200, 200),
        ("meera", 403, 200),  # supervises the scholar
        ("hod_b1", 403, 403),
        ("sup_b1", 403, 403),
        ("scholar_a2", 403, 403),
        ("exam_office", 403, 403),
    ],
)
async def test_who_reads_a_patent(client, world, who, faculty_status, scholar_status):
    faculty = await add(client, world.sup_a2)
    scholar = await add(client, world.scholar_a1, application_number="2024-B")
    user = getattr(world, who)
    for pid, status in ((faculty["id"], faculty_status), (scholar["id"], scholar_status)):
        res = await client.get(f"{API}/{pid}", headers=auth(user.id))
        assert res.status_code == status, (who, pid)


async def test_the_chosen_office_verifies(client, session, world):
    pid = (await add(client, world.sup_a2))["id"]
    assert (await act(client, world.library, pid, "verify")).status_code == 403
    assert (await act(client, world.sup_a2, pid, "verify")).status_code == 403
    await choose(session, "library")
    assert (await act(client, world.research_office, pid, "verify")).status_code == 403
    res = await act(client, world.library, pid, "verify")
    assert res.status_code == 200 and res.json()["verification"] == "verified"
    assert res.json()["checked_by"] == world.library.full_name
    assert [n.category for n in await notices(session, world.sup_a2)] == ["approved"]


async def test_returned_then_corrected_goes_back(client, session, world):
    pid = (await add(client, world.scholar_a1))["id"]
    res = await act(client, world.research_office, pid, "return", {"note": "Wrong number."})
    assert res.json()["verification"] == "returned"
    assert res.json()["return_note"] == "Wrong number."
    told = await notices(session, world.scholar_a1)
    assert [(n.category, n.body) for n in told] == [("sent_back", "Wrong number.")]
    fixed = await client.put(
        f"{API}/{pid}", headers=auth(world.scholar_a1.id), json=FILED | {"application_number": "X"}
    )
    assert fixed.json()["verification"] == "waiting" and fixed.json()["return_note"] is None
    assert len(await notices(session, world.research_office)) == 2  # added, corrected


async def test_a_verified_patent_moves_on_and_is_checked_again(client, world):
    pid = (await add(client, world.sup_a2))["id"]
    await act(client, world.research_office, pid, "verify")
    gone = await client.delete(f"{API}/{pid}", headers=auth(world.sup_a2.id))
    assert gone.status_code == 409
    other = await client.put(f"{API}/{pid}", headers=auth(world.sup_b1.id), json=GRANTED)
    assert other.status_code == 403
    res = await client.put(f"{API}/{pid}", headers=auth(world.sup_a2.id), json=GRANTED)
    body = res.json()
    assert body["patent_status"] == "granted" and body["verification"] == "waiting"


async def test_the_author_removes_one_not_verified(client, world):
    pid = (await add(client, world.sup_a2))["id"]
    assert (await client.delete(f"{API}/{pid}", headers=auth(world.sup_a2.id))).status_code == 204
    assert (await client.get(f"{API}/{pid}", headers=auth(world.sup_a2.id))).status_code == 403


async def test_the_office_never_checks_its_own(client, session, world):
    await insert(
        session,
        None,
        Faculty(
            user_id=world.research_office.id,
            unit_id=world.a1.id,
            designation="Professor",
            max_scholars=8,
            can_supervise=False,
        ),
    )
    await session.commit()
    pid = (await add(client, world.research_office))["id"]
    assert (await act(client, world.research_office, pid, "verify")).status_code == 403
    home = await client.get("/api/v1/dashboard", headers=auth(world.research_office.id))
    assert home.json()["patents"]["to_verify"] == 0


async def test_papers_attach_while_not_verified(client, world):
    pid = (await add(client, world.scholar_a1))["id"]
    url = "/api/v1/files/uploads"
    file = {"table_name": "patents", "record_id": pid, "file_name": "receipt.pdf"}
    file |= {"content_type": "application/pdf", "size_bytes": 10}
    assert (await client.post(url, headers=auth(world.meera.id), json=file)).status_code == 403
    assert (await client.post(url, headers=auth(world.scholar_a1.id), json=file)).status_code == 201
    await act(client, world.research_office, pid, "verify")
    assert (await client.post(url, headers=auth(world.scholar_a1.id), json=file)).status_code == 409


async def test_home_counts(client, world):
    pid = (await add(client, world.scholar_a1))["id"]
    await add(client, world.sup_a2, application_number="2024-C")
    home = lambda who: client.get("/api/v1/dashboard", headers=auth(who.id))  # noqa: E731
    assert (await home(world.research_office)).json()["patents"] == {
        "checks": True,
        "to_verify": 2,
        "returned": 0,
    }
    await act(client, world.research_office, pid, "return", {"note": "Attach the receipt."})
    assert (await home(world.scholar_a1)).json()["patents"]["returned"] == 1
    assert (await home(world.exam_office)).json()["patents"] is None


async def test_the_list_keeps_to_scope_and_filters(client, world):
    await add(client, world.sup_a2, title="From A2")
    await add(client, world.sup_b1, title="From B1", application_number="2024-D")
    titles = lambda res: {r["title"] for r in res.json()}  # noqa: E731
    assert titles(await client.get(API, headers=auth(world.hod_b1.id))) == {"From B1"}
    office = await client.get(API, headers=auth(world.research_office.id), params={"q": "from"})
    assert titles(office) == {"From A2", "From B1"}
    mine = await client.get(API, headers=auth(world.sup_a2.id), params={"mine": "true"})
    assert titles(mine) == {"From A2"}


async def test_naac_counts_verified_publications_and_grants_once(client, session, world):
    granted = await add(client, world.meera, **GRANTED)
    same = await add(client, world.scholar_a1, **GRANTED | {"application_number": "2024 41000111"})
    await add(client, world.sup_a2, **GRANTED | {"application_number": "unchecked"})
    for pid in (granted["id"], same["id"]):
        await act(client, world.research_office, pid, "verify")
    res = await client.get(
        "/api/v1/internal/naac/patents",
        headers=auth(world.research_office.id),
        params={"from_year": 2024, "to_year": 2024},
    )
    body = res.json()
    rows = [dict(zip(body["columns"], r, strict=True)) for r in body["rows"]]
    assert [(r["Event"], r["Academic year"]) for r in rows] == [
        ("Published", "2024-25"),
        ("Granted", "2024-25"),
    ]
    assert "(faculty)" in rows[0]["Recorded by"] and "(scholar)" in rows[0]["Recorded by"]


async def test_a_patent_is_no_longer_a_publication(client, world):
    res = await client.post(
        "/api/v1/publications", headers=auth(world.scholar_a1.id), json=PUB | {"pub_type": "patent"}
    )
    assert res.status_code == 422 and "Patents" in res.text


async def test_search_finds_them(client, world):
    await add(client, world.sup_a2, title="Solar mango dryer")
    found = await client.get(
        "/api/v1/search", headers=auth(world.research_office.id), params={"q": "mango"}
    )
    assert len(found.json()["patents"]) == 1
    hidden = await client.get(
        "/api/v1/search", headers=auth(world.hod_b1.id), params={"q": "mango"}
    )
    assert hidden.json()["patents"] == []


async def test_off_with_the_module(client, session, world):
    pid = (await add(client, world.sup_a2))["id"]
    await session.execute(update(Module).where(Module.key == "patents").values(enabled=False))
    await session.commit()
    assert (await client.get(f"{API}/{pid}", headers=auth(world.sup_a2.id))).status_code == 404
    home = await client.get("/api/v1/dashboard", headers=auth(world.research_office.id))
    assert home.json()["patents"] is None


async def test_the_root_admin_chooses_the_office(client, world):
    url = "/api/v1/settings"
    res = await client.patch(
        url, headers=auth(world.root_admin.id), json={"patent_verifier": "library"}
    )
    assert res.json()["patent_verifier"] == "library"
    bad = await client.patch(url, headers=auth(world.root_admin.id), json={"patent_verifier": "vc"})
    assert bad.status_code == 422
