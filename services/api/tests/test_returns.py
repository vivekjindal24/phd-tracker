"""NIRF's and AISHE's research-degree tables (PRD M9, returns.py), and the AISHE fields behind
them: a scholar's minority community and nationality, a unit's AISHE discipline."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select, update

from app.models import LedgerEntry, Milestone, Module, Patent, Project, Scholar
from app.returns import rupees_in_words
from tests.conftest import auth
from tests.test_bulk_import import csv_bytes, upload
from tests.test_publications import enable

API = "/api/v1/internal/returns"


@pytest.fixture(autouse=True)
async def modules_on(session):
    await enable(session, "projects", "patents")


def test_rupees_in_words_follow_lakh_and_crore():
    assert rupees_in_words(123215708) == (
        "Twelve Crore Thirty Two Lakh Fifteen Thousand Seven Hundred Eight"
    )
    assert rupees_in_words(1867000) == "Eighteen Lakh Sixty Seven Thousand"
    assert rupees_in_words(12_00_00_00_000) == "One Thousand Two Hundred Crore"
    assert rupees_in_words(40) == "Forty" and rupees_in_words(0) == "Zero"


async def table(client, world, sheet, year=2024) -> list[dict]:
    res = await client.get(
        f"{API}/{sheet}", headers=auth(world.research_office.id), params={"year": year}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["title"].endswith(f"{year}-{(year + 1) % 100:02d}")
    return [dict(zip(body["columns"], row, strict=False)) for row in body["rows"]]


@pytest.mark.parametrize(
    ("who", "status"),
    [
        ("research_office", 200),
        ("vice_chancellor", 200),
        ("root_admin", 403),  # does not read personal data (scope.sees_personal)
        ("admin_a1", 403),
        ("dean_a", 403),
        ("meera", 403),
        ("exam_office", 403),
        ("scholar_a1", 403),
    ],
)
async def test_who_reads_the_tables(client, world, who, status):
    res = await client.get(
        f"{API}/aishe-enrolment", headers=auth(getattr(world, who).id), params={"year": 2024}
    )
    assert res.status_code == status


async def test_a_sheet_of_a_switched_off_module_is_404(client, session, world):
    await session.execute(update(Module).where(Module.key == "projects").values(enabled=False))
    await session.commit()
    res = await client.get(
        f"{API}/nirf-sponsored", headers=auth(world.research_office.id), params={"year": 2024}
    )
    assert res.status_code == 404


async def _scholars(session, world) -> None:
    """A1: a full-time General woman (Muslim), admitted 2021, viva and degree in 2024-25; a
    part-time EWS man with a disability, an NRI from Nepal, admitted 2022. A2: on roll, nothing
    else recorded. B1: no admission date."""
    rows = {
        world.s_a1.id: {
            "study_mode": "full_time",
            "gender": "female",
            "category": "general",
            "minority": "muslim",
            "admission_date": date(2021, 8, 2),
        },
        world.s_a1b.id: {
            "study_mode": "part_time",
            "gender": "male",
            "category": "ews",
            "has_disability": True,
            "nationality": "nri",
            "country": "Nepal",
            "admission_date": date(2022, 9, 1),
        },
        world.s_a2.id: {"admission_date": date(2024, 1, 10)},
        world.s_b1.id: {"admission_date": None},
    }
    for sid, values in rows.items():
        await session.execute(update(Scholar).where(Scholar.id == sid).values(**values))
    for kind, day in (("viva", date(2024, 10, 3)), ("degree_awarded", date(2024, 12, 5))):
        session.add(
            Milestone(
                scholar_id=world.s_a1.id,
                milestone_type=kind,
                status="Approved",
                approval_body="RDC",
                resolution_date=day,
            )
        )
    await session.commit()


async def test_nirf_phd_students_pursuing_and_graduated(client, session, world):
    await _scholars(session, world)
    rows = await table(client, world, "nirf-phd")
    as_lists = [list(r.values()) for r in rows]
    # On 30 June 2025: A1's part-timer and A2's (mode not recorded); A1's full-timer graduated.
    assert as_lists[0][1:] == [0, 1, 1]
    assert as_lists[1] == ["Graduated in 2024-25", 1, 0, 0]
    assert as_lists[2][0] == "Graduated in 2023-24" and as_lists[3][0] == "Graduated in 2022-23"
    assert as_lists[-1] == ["Not counted: 1 scholar(s) with no admission date recorded"]


async def test_aishe_enrolment_by_unit_year_category_and_gender(client, session, world):
    await _scholars(session, world)
    res = await client.patch(
        f"/api/v1/org-units/{world.a1.id}",
        headers=auth(world.root_admin.id),
        json={"aishe_discipline": "Computer Science and Engineering"},
    )
    assert res.json()["aishe_discipline"] == "Computer Science and Engineering"
    rows = await table(client, world, "aishe-enrolment")
    a1 = {(r["Year of study"], r["Row"]): r for r in rows if r.get("Department") == "Dept A1"}
    assert {r["Faculty / school"] for r in a1.values()} == {"School A"}
    assert {r["AISHE discipline"] for r in a1.values()} == {"Computer Science and Engineering"}
    fourth = a1[4, "Total"]
    assert fourth["General Female"] == 1 and fourth["Total"] == 1
    assert a1[4, "Muslim minority (out of total)"]["General Female"] == 1
    third = a1[3, "Total"]
    assert third["General Male"] == 1 and third["EWS (out of General) Male"] == 1
    assert a1[3, "PwBD (out of total)"]["Total"] == 1
    a2 = next(r for r in rows if r.get("Department") == "Dept A2" and r["Row"] == "Total")
    assert a2["Year of study"] == 2 and a2["Category or gender not recorded"] == 1
    assert rows[-1]["Faculty / school"].startswith("Not counted: 1 scholar(s)")


async def test_aishe_foreign_students_by_country(client, session, world):
    await _scholars(session, world)
    [nepal] = await table(client, world, "aishe-foreign")
    assert nepal["Country"] == "Nepal" and nepal["Department"] == "Dept A1"
    assert (nepal["NRI male"], nepal["NRI total"], nepal["PIO total"], nepal["Total"]) == (
        1,
        1,
        0,
        1,
    )


async def test_aishe_results_appeared_and_awarded(client, session, world):
    await _scholars(session, world)
    rows = {r["Row"]: r for r in await table(client, world, "aishe-results")}
    assert rows["Appeared: Total"]["General Female"] == 1
    assert rows["Awarded: Muslim minority (out of total)"]["General Female"] == 1
    assert await table(client, world, "aishe-results", year=2023) == []


async def test_nirf_sponsored_research_and_patents(client, session, world):
    project = Project(
        pi_id=world.meera_faculty.id,
        unit_id=world.a1.id,
        agency="SERB",
        title="Funded",
        sanction_number="S/1",
        amount_sanctioned=500000,
        start_date=date(2024, 4, 1),
        end_date=date(2027, 3, 31),
    )
    other = Project(
        pi_id=world.meera_faculty.id,
        unit_id=world.a1.id,
        agency=" serb ",
        title="Second",
        sanction_number="S/2",
        amount_sanctioned=100000,
        start_date=date(2024, 4, 1),
        end_date=date(2027, 3, 31),
    )
    session.add_all([project, other])
    await session.flush()
    entries = [
        (project, "disbursement", 200000, date(2024, 5, 1)),
        (project, "disbursement", 15708, date(2025, 3, 31)),  # still 2024-25
        (other, "disbursement", 100000, date(2025, 4, 1)),  # 2025-26
        (project, "expense", 5000, date(2024, 6, 1)),
    ]
    for p, kind, amount, day in entries:
        session.add(
            LedgerEntry(project_id=p.id, entry_kind=kind, head="equipment", amount=amount,
                        entry_date=day)
        )  # fmt: skip
    session.add(
        Patent(
            faculty_id=world.meera_faculty.id,
            title="Seed sorter",
            inventors="M",
            application_number="2024-1",
            filed_on=date(2023, 3, 1),
            office="India",
            patent_status="published",
            published_on=date(2024, 5, 1),
            verification="verified",
            checked_at=datetime.now(UTC),
        )
    )
    await session.commit()
    [this, last, before] = await table(client, world, "nirf-sponsored")
    assert list(this.values()) == [
        "2024-25",
        1,
        1,
        215708,
        "Two Lakh Fifteen Thousand Seven Hundred Eight",
    ]
    assert last["Financial year"] == "2023-24" and last["Total no. of sponsored projects"] == 0
    assert before["Financial year"] == "2022-23"
    later = (await table(client, world, "nirf-sponsored", year=2025))[0]
    assert later["Total no. of funding agencies"] == 1  # " serb " is SERB
    patents = await table(client, world, "nirf-patents")
    assert [list(r.values()) for r in patents] == [[2024, 1, 0], [2023, 0, 0], [2022, 0, 0]]


# --- the fields ---------------------------------------------------------------------------------


async def test_the_scholar_fills_in_minority_and_nationality(client, session, world):
    url = "/api/v1/scholars/mine/profile"
    me = auth(world.scholar_a1.id)
    missing = await client.put(url, headers=me, json={"nationality": "foreign"})
    assert missing.status_code == 422  # a foreign national's country
    res = await client.put(url, headers=me, json={"minority": "sikh", "nationality": "indian"})
    assert res.status_code == 200, res.text
    assert (res.json()["minority"], res.json()["nationality"], res.json()["country"]) == (
        "sikh",
        "indian",
        None,
    )
    again = await client.put(url, headers=me, json={"minority": "none"})
    assert again.status_code == 409


async def test_only_those_who_see_personal_data_read_them(client, session, world):
    await _scholars(session, world)
    url = f"/api/v1/scholars/{world.s_a1b.id}"
    own = (await client.get(url, headers=auth(world.admin_a1.id))).json()
    assert (own["nationality"], own["country"]) == ("nri", "Nepal")
    supervisor = (await client.get(url, headers=auth(world.sup_a2.id))).json()
    assert supervisor["sees_personal"] is False
    assert supervisor["nationality"] is None and supervisor["country"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"nationality": "nri"},  # the country with it
        {"country": "Nepal"},
        {"nationality": "indian", "country": "Nepal"},
        {"nationality": "pio", "country": None},
    ],
)
async def test_the_admin_gives_nationality_and_country_together(client, world, body):
    res = await client.patch(
        f"/api/v1/scholars/{world.s_a1.id}", headers=auth(world.admin_a1.id), json=body
    )
    assert res.status_code == 422


async def test_the_admin_corrects_them(client, world):
    url = f"/api/v1/scholars/{world.s_a1.id}"
    body = {"minority": "parsi", "nationality": "pio", "country": "Kenya"}
    res = await client.patch(url, headers=auth(world.admin_a1.id), json=body)
    assert res.status_code == 200 and res.json()["country"] == "Kenya"
    back = {"nationality": "indian", "country": None}
    assert (await client.patch(url, headers=auth(world.admin_a1.id), json=back)).json()[
        "country"
    ] is None


async def test_import_reads_them_and_checks_the_country(client, session, world):
    header = "Roll number,Name,Email,Unit,Minority community,Nationality,Country"
    bad = csv_bytes(header, "R1,One,r1@x.edu,A1,,foreign,")
    res = await upload(client, world.admin_a1, "scholars", bad, dry_run="true")
    assert [e["column"] for e in res.json()["errors"]] == ["Country"]
    good = csv_bytes(header, "R1,One,r1@x.edu,A1,Jain,Foreign,Sri Lanka")
    assert (await upload(client, world.admin_a1, "scholars", good)).json()["created"] == 1
    s = await session.scalar(select(Scholar).where(Scholar.roll_number == "R1"))
    assert (s.minority, s.nationality, s.country) == ("jain", "foreign", "Sri Lanka")


async def test_the_discipline_is_the_root_admins_to_set(client, world):
    url = f"/api/v1/org-units/{world.a1.id}"
    refused = await client.patch(
        url, headers=auth(world.admin_a1.id), json={"aishe_discipline": "Physics"}
    )
    assert refused.status_code == 403
    cleared = await client.patch(
        url, headers=auth(world.root_admin.id), json={"aishe_discipline": None}
    )
    assert cleared.json()["aishe_discipline"] is None
