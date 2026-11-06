"""NAAC Criterion 3 data (PRD M9): the underlying rows per academic year, from records already
kept, for the Research Office and root admin only."""

from datetime import date

import pytest
from sqlalchemy import update

from app.models import LedgerEntry, Milestone, Module, Project, Publication
from app.naac import academic_year
from tests.conftest import auth
from tests.test_publications import enable

API = "/api/v1/internal/naac"
YEARS = {"from_year": 2024, "to_year": 2025}


@pytest.fixture(autouse=True)
async def modules_on(session):
    await enable(session, "projects", "publications")


def test_the_academic_year_starts_in_july():
    assert academic_year(date(2025, 6, 30)) == "2024-25"
    assert academic_year(date(2025, 7, 1)) == "2025-26"
    assert academic_year(date(2099, 12, 31)) == "2099-00"


async def sheet(client, world, name, **params):
    res = await client.get(
        f"{API}/{name}", headers=auth(world.research_office.id), params=YEARS | params
    )
    assert res.status_code == 200, res.text
    body = res.json()
    return [dict(zip(body["columns"], row, strict=True)) for row in body["rows"]]


@pytest.mark.parametrize("who", ["research_office", "root_admin"])
async def test_research_office_and_root_admin_read(client, world, who):
    res = await client.get(
        f"{API}/publications", headers=auth(getattr(world, who).id), params=YEARS
    )
    assert res.status_code == 200


@pytest.mark.parametrize("who", ["admin_a1", "dean_a", "meera", "exam_office", "scholar_a1"])
async def test_nobody_else_reads(client, world, who):
    res = await client.get(
        f"{API}/publications", headers=auth(getattr(world, who).id), params=YEARS
    )
    assert res.status_code == 403


@pytest.mark.parametrize(
    "params", [{"from_year": 2025, "to_year": 2024}, {"from_year": 2000, "to_year": 2025}]
)
async def test_year_range_is_validated(client, world, params):
    res = await client.get(
        f"{API}/publications", headers=auth(world.research_office.id), params=params
    )
    assert res.status_code == 422


async def test_unknown_sheet_is_404(client, world):
    res = await client.get(f"{API}/nope", headers=auth(world.research_office.id), params=YEARS)
    assert res.status_code == 404


def _publication(world, title, **fields) -> Publication:
    defaults = {
        "scholar_id": world.s_a1.id,
        "authors": "A, B",
        "pub_type": "journal",
        "venue": "J. Graphs",
        "pub_year": 2025,
        "pub_status": "published",
        "state": "approved",
        "indexing": ["scopus", "ugc_care"],
    }
    return Publication(title=title, **(defaults | fields))


async def test_publications_are_approved_published_and_flag_indexing(client, session, world):
    session.add_all(
        [
            _publication(world, "Counted"),
            _publication(world, "Still a draft", state="draft"),
            _publication(world, "Only accepted", pub_status="accepted"),
            _publication(world, "Too old", pub_year=2020),
            _publication(world, "A chapter", pub_type="book_chapter"),
            _publication(world, "A patent", pub_type="patent"),
        ]
    )
    await session.commit()
    rows = await sheet(client, world, "publications")
    assert [r["Title"] for r in rows] == ["Counted"]
    assert (rows[0]["Scopus"], rows[0]["UGC-CARE"], rows[0]["Web of Science"]) == (
        "Yes",
        "Yes",
        "No",
    )
    books = await sheet(client, world, "books")
    assert [r["Title"] for r in books] == ["A chapter"]


async def test_scholars_registered_and_awarded_per_guide(client, session, world):
    scholar = world.s_a1
    scholar.admission_date = date(2024, 8, 1)
    session.add(scholar)
    session.add(
        Milestone(
            scholar_id=world.s_a2.id,
            milestone_type="degree_awarded",
            status="Approved",
            approval_body="RDC",
            resolution_date=date(2026, 1, 15),
        )
    )
    session.add(
        Milestone(
            scholar_id=world.s_b1.id,
            milestone_type="degree_awarded",
            status="Pending",
            approval_body="RDC",
            resolution_date=date(2026, 1, 15),
        )
    )
    await session.commit()
    rows = await sheet(client, world, "scholars")
    events = {(r["Event"], r["Roll number"], r["Academic year"], r["Guide"]) for r in rows}
    assert ("Registered", world.s_a1.roll_number, "2024-25", world.meera.full_name) in events
    assert ("Awarded", world.s_a2.roll_number, "2025-26", world.sup_a2.full_name) in events
    assert not any(r["Roll number"] == world.s_b1.roll_number for r in rows)


async def test_projects_list_each_grant_and_those_without_any(client, session, world):
    funded = Project(
        pi_id=world.meera_faculty.id,
        unit_id=world.a1.id,
        agency="SERB",
        title="Funded",
        sanction_number="S/1",
        amount_sanctioned=100000,
        start_date=date(2024, 8, 1),
        end_date=date(2027, 3, 31),
    )
    waiting = Project(
        pi_id=world.meera_faculty.id,
        unit_id=world.a1.id,
        agency="DST",
        title="Waiting",
        sanction_number="S/2",
        amount_sanctioned=50000,
        start_date=date(2025, 8, 1),
        end_date=date(2027, 3, 31),
    )
    session.add_all([funded, waiting])
    await session.flush()
    session.add_all(
        [
            LedgerEntry(
                project_id=funded.id,
                entry_kind="disbursement",
                head="equipment",
                amount=40000,
                entry_date=date(2025, 1, 10),
                reference="1st",
            ),
            LedgerEntry(
                project_id=funded.id,
                entry_kind="expense",
                head="travel",
                amount=500,
                entry_date=date(2025, 2, 1),
            ),
        ]
    )
    await session.commit()
    rows = await sheet(client, world, "projects")
    assert {(r["Project"], r["Academic year"], r["Grant received"]) for r in rows} == {
        ("Funded", "2024-25", 40000.0),
        ("Waiting", "2025-26", None),
    }


@pytest.mark.parametrize(
    ("name", "module"),
    [("projects", "projects"), ("publications", "publications"), ("books", "publications")],
)
async def test_a_sheet_follows_its_module(client, session, world, name, module):
    await session.execute(update(Module).where(Module.key == module).values(enabled=False))
    await session.commit()
    res = await client.get(f"{API}/{name}", headers=auth(world.research_office.id), params=YEARS)
    assert res.status_code == 404 and res.json()["error"]["code"] == "module_disabled"


async def test_the_scholars_sheet_needs_no_module(client, session, world):
    await session.execute(update(Module).values(enabled=False))
    await session.commit()
    await sheet(client, world, "scholars")
