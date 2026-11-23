"""Faculty publications (PRD M1, faculty_papers.py): recorded by the member of faculty, verified
or returned by the Library, counted in NAAC once verified. No approval chain."""

import httpx
import pytest
from sqlalchemy import select

from app import doi, orcid
from app.crud import insert
from app.models import Faculty, Notification
from tests.conftest import auth
from tests.test_naac import _publication, sheet
from tests.test_orcid import ID, crossref_work, summary
from tests.test_publications import PUB, enable

API = "/api/v1/faculty-publications"


@pytest.fixture(autouse=True)
async def modules_on(session, world):
    await enable(session, "publications")


async def add(client, user, **over) -> dict:
    res = await client.post(API, headers=auth(user.id), json=PUB | over)
    assert res.status_code == 201, res.text
    return res.json()


async def act(client, user, pid, step, body=None):
    return await client.post(f"{API}/{pid}/{step}", headers=auth(user.id), json=body or {})


async def notices(session, user) -> list[Notification]:
    return list(
        await session.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at)
        )
    )


async def test_faculty_record_and_the_library_is_told(client, session, world):
    paper = await add(client, world.sup_a2)
    assert paper["verification"] == "waiting"
    assert paper["faculty"]["id"] == str(world.sup_a2_faculty.id)
    assert paper["can_edit"] and not paper["can_check"]
    told = await notices(session, world.library)
    assert [n.category for n in told] == ["approval_waiting"]


async def test_only_faculty_record(client, world):
    for who in (world.scholar_a1, world.library, world.research_office):
        res = await client.post(API, headers=auth(who.id), json=PUB)
        assert res.status_code == 403, who.email


@pytest.mark.parametrize(
    ("who", "status"),
    [
        ("sup_a2", 200),  # the author
        ("library", 200),
        ("research_office", 200),
        ("vice_chancellor", 200),
        ("hod_a2", 200),  # head of the author's department
        ("dean_a", 200),  # head of the school above it
        ("root_admin", 200),
        ("hod_b1", 403),  # another department
        ("sup_b1", 403),  # another member of faculty
        ("scholar_a2", 403),
        ("exam_office", 403),
    ],
)
async def test_who_reads_a_faculty_paper(client, world, who, status):
    paper = await add(client, world.sup_a2)
    res = await client.get(f"{API}/{paper['id']}", headers=auth(getattr(world, who).id))
    assert res.status_code == status


async def test_the_list_keeps_to_scope(client, world):
    await add(client, world.sup_a2, title="From A2")
    await add(client, world.sup_b1, title="From B1", doi="10.1234/b1")
    titles = lambda res: {r["title"] for r in res.json()}  # noqa: E731
    hod_b1 = await client.get(API, headers=auth(world.hod_b1.id))
    assert titles(hod_b1) == {"From B1"}
    library = await client.get(API, headers=auth(world.library.id), params={"q": "from"})
    assert titles(library) == {"From A2", "From B1"}
    mine = await client.get(
        API, headers=auth(world.sup_a2.id), params={"faculty_id": str(world.sup_a2_faculty.id)}
    )
    assert titles(mine) == {"From A2"}
    assert (await client.get(API, headers=auth(world.scholar_a1.id))).status_code == 403


async def test_the_library_verifies_and_it_is_then_locked(client, session, world):
    paper = await add(client, world.sup_a2)
    pid = paper["id"]
    assert (await act(client, world.sup_a2, pid, "verify", {"indexing": []})).status_code == 403
    res = await act(client, world.library, pid, "verify", {"indexing": ["wos"], "doi": None})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["verification"] == "verified" and body["indexing"] == ["wos"]
    assert body["doi"] is None and body["checked_by"] == world.library.full_name
    assert not body["can_edit"]
    edit = await client.patch(f"{API}/{pid}", headers=auth(world.sup_a2.id), json={"title": "X"})
    assert edit.status_code == 409
    gone = await client.delete(f"{API}/{pid}", headers=auth(world.sup_a2.id))
    assert gone.status_code == 409
    again = await act(client, world.library, pid, "verify", {"indexing": ["wos"]})
    assert again.status_code == 409
    assert [n.category for n in await notices(session, world.sup_a2)] == ["approved"]


async def test_returned_with_a_note_then_back_to_the_library(client, session, world):
    pid = (await add(client, world.sup_a2))["id"]
    assert (await act(client, world.library, pid, "return", {"note": ""})).status_code == 422
    res = await act(client, world.library, pid, "return", {"note": "Not in Scopus: untick it."})
    assert res.json()["verification"] == "returned"
    assert res.json()["library_note"] == "Not in Scopus: untick it."
    told = await notices(session, world.sup_a2)
    assert [(n.category, n.body) for n in told] == [("sent_back", "Not in Scopus: untick it.")]
    other = await client.patch(f"{API}/{pid}", headers=auth(world.sup_b1.id), json={"title": "X"})
    assert other.status_code == 403
    fixed = await client.patch(f"{API}/{pid}", headers=auth(world.sup_a2.id), json={"indexing": []})
    assert fixed.json()["verification"] == "waiting" and fixed.json()["library_note"] is None
    assert len(await notices(session, world.library)) == 2  # added, then corrected


async def test_a_verified_paper_can_be_returned_for_a_correction(client, world):
    pid = (await add(client, world.sup_a2))["id"]
    await act(client, world.library, pid, "verify", {"indexing": ["scopus"]})
    res = await act(client, world.library, pid, "return", {"note": "Wrong year."})
    assert res.json()["verification"] == "returned" and res.json()["can_edit"] is False
    mine = await client.get(f"{API}/{pid}", headers=auth(world.sup_a2.id))
    assert mine.json()["can_edit"] is True


async def test_the_library_does_not_verify_its_own_paper(client, session, world):
    await insert(
        session,
        None,
        Faculty(
            user_id=world.library.id,
            unit_id=world.a1.id,
            designation="Assistant Professor",
            max_scholars=4,
            can_supervise=False,
        ),
    )
    await session.commit()
    pid = (await add(client, world.library))["id"]
    res = await act(client, world.library, pid, "verify", {"indexing": []})
    assert res.status_code == 403
    home = await client.get("/api/v1/dashboard", headers=auth(world.library.id))
    assert home.json()["faculty_papers"]["to_verify"] == 0


async def test_the_author_deletes_one_waiting(client, world):
    pid = (await add(client, world.sup_a2))["id"]
    other = await client.delete(f"{API}/{pid}", headers=auth(world.library.id))
    assert other.status_code == 403
    res = await client.delete(f"{API}/{pid}", headers=auth(world.sup_a2.id))
    assert res.status_code == 204
    assert (await client.get(f"{API}/{pid}", headers=auth(world.sup_a2.id))).status_code == 403


async def test_home_shows_what_waits(client, world):
    pid = (await add(client, world.sup_a2))["id"]
    await add(client, world.sup_b1, doi="10.1234/b1")
    home = lambda who: client.get("/api/v1/dashboard", headers=auth(who.id))  # noqa: E731
    assert (await home(world.library)).json()["faculty_papers"] == {
        "to_verify": 2,
        "returned": 0,
    }
    await act(client, world.library, pid, "return", {"note": "Attach the paper."})
    assert (await home(world.sup_a2)).json()["faculty_papers"]["returned"] == 1
    assert (await home(world.scholar_a1)).json()["faculty_papers"] is None


async def test_naac_counts_verified_papers_once(client, session, world):
    shared = "10.5555/Shared"
    await add(client, world.sup_a2, title="Waiting", doi="10.5555/w")
    both = await add(client, world.meera, title="Joint paper", doi=shared, indexing=["scopus"])
    own = await add(client, world.sup_b1, title="Faculty alone", doi=None, pub_type="book_chapter")
    await act(client, world.library, both["id"], "verify", {"indexing": ["scopus"], "doi": shared})
    await act(client, world.library, own["id"], "verify", {"indexing": []})
    session.add(_publication(world, "Joint paper", doi=shared.lower()))
    await session.commit()
    rows = await sheet(client, world, "publications")
    assert [r["Title"] for r in rows] == ["Joint paper"]
    assert "(scholar)" in rows[0]["Recorded by"] and "(faculty)" in rows[0]["Recorded by"]
    books = await sheet(client, world, "books")
    assert [(r["Title"], r["Recorded by"]) for r in books] == [
        ("Faculty alone", f"{world.sup_b1.full_name} (faculty)")
    ]


async def test_imported_from_orcid_go_to_the_library_with_one_notice(
    client, session, world, monkeypatch
):
    groups = [
        summary(1, "On graphs", doi_value="10.5555/one"),
        summary(2, "B", doi_value="10.5555/two"),
    ]
    monkeypatch.setattr(
        orcid,
        "TRANSPORT",
        httpx.MockTransport(lambda _: httpx.Response(200, json={"group": groups})),
    )
    monkeypatch.setattr(doi, "TRANSPORT", httpx.MockTransport(crossref_work))
    works = await client.get(f"{API}/orcid", headers=auth(world.sup_a2.id), params={"q": ID})
    assert works.status_code == 200 and len(works.json()) == 2
    res = await client.post(
        f"{API}/import",
        headers=auth(world.sup_a2.id),
        json={"dois": ["10.5555/one", "10.5555/two"]},
    )
    assert len(res.json()["created"]) == 2
    told = await notices(session, world.library)
    assert len(told) == 1 and "2 papers" in told[0].title
    again = await client.get(
        f"{API}/doi", headers=auth(world.sup_a2.id), params={"q": "10.5555/ONE"}
    )
    assert again.json()["already_recorded"] is True
    scholar = await client.get(f"{API}/orcid", headers=auth(world.scholar_a1.id), params={"q": ID})
    assert scholar.status_code == 403


async def test_the_paper_is_attached_by_its_author_until_verified(client, world):
    pid = (await add(client, world.sup_a2))["id"]
    url = "/api/v1/files/uploads"
    file = {"table_name": "faculty_publications", "record_id": pid, "file_name": "paper.pdf"}
    file |= {"content_type": "application/pdf", "size_bytes": 10}
    assert (await client.post(url, headers=auth(world.library.id), json=file)).status_code == 403
    assert (await client.post(url, headers=auth(world.sup_a2.id), json=file)).status_code == 201
    listed = await client.get(
        "/api/v1/files",
        headers=auth(world.library.id),
        params={"table_name": "faculty_publications", "record_id": pid},
    )
    assert listed.status_code == 200
    await act(client, world.library, pid, "verify", {"indexing": []})
    assert (await client.post(url, headers=auth(world.sup_a2.id), json=file)).status_code == 409


async def test_search_finds_them_within_scope(client, world):
    await add(client, world.sup_a2, title="Quantum sorting of mangoes")
    find = lambda who: client.get(  # noqa: E731
        "/api/v1/search", headers=auth(who.id), params={"q": "mangoes"}
    )
    assert len((await find(world.library)).json()["faculty_publications"]) == 1
    assert (await find(world.hod_b1)).json()["faculty_publications"] == []


async def test_off_with_the_publications_module(client, session, world):
    from sqlalchemy import update

    from app.models import Module

    pid = (await add(client, world.sup_a2))["id"]
    await session.execute(update(Module).where(Module.key == "publications").values(enabled=False))
    await session.commit()
    res = await client.get(f"{API}/{pid}", headers=auth(world.sup_a2.id))
    assert res.status_code == 404
    home = await client.get("/api/v1/dashboard", headers=auth(world.library.id))
    assert home.json()["faculty_papers"] is None
