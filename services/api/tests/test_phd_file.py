"""The PhD file (PRD F17): every annexure in career order, each as the caller may read it."""

from tests.conftest import auth
from tests.test_thesis import approved_thesis, documents_on  # noqa: F401

API = "/api/v1"


def url(world) -> str:
    return f"{API}/internal/scholars/{world.s_a1.id}/phd-file"


def part(view, key):
    return next(a for a in view["annexures"] if a["key"] == key)


async def test_every_annexure_in_order_and_none_left_out(client, world):
    admin = auth(world.admin_a1.id)
    await client.post(
        f"{API}/scholars/{world.s_a1.id}/comprehensive",
        headers=admin,
        json={"held_in": "2022-05-01", "result": "satisfactory"},
    )
    view = (await client.get(url(world), headers=auth(world.scholar_a1.id))).json()
    assert view["scholar"] == "Scholar A1" and view["supervisor"] == "Meera"
    assert [a["key"] for a in view["annexures"]][:4] == [
        "admission",
        "employer_noc",
        "supervision",
        "advisory_committee",
    ]
    exam = part(view, "comprehensive")
    assert exam["date"] == "2022-05-01" and exam["note"] is None
    assert exam["entries"][0]["lines"] == [["Result", "Satisfactory"]]
    assert part(view, "supervision")["entries"][0]["heading"] == "Supervisor: Meera"
    assert part(view, "employer_noc") == {
        "key": "employer_noc",
        "title": "No-objection certificate from the employer",
        "date": None,
        "entries": [],
        "note": "Not on record",
    }
    assert part(view, "publications")["note"] == "Not on record"  # module off: nothing shown


async def test_only_who_reads_the_scholar(client, world):
    for outsider in (world.scholar_b1, world.hod_b1, world.sup_b1):
        assert (await client.get(url(world), headers=auth(outsider.id))).status_code == 403


async def test_examiner_names_stay_withheld(client, session, world, documents_on):  # noqa: F811
    tid = await approved_thesis(client, session, world)
    await client.post(
        f"{API}/theses/{tid}/examiner-reports",
        headers=auth(world.exam_office.id),
        json={
            "examiner_name": "Prof. X",
            "institution": "IIT Bombay",
            "received_on": "2026-09-01",
            "recommendation": "minor_revision",
        },
    )
    dept = (await client.get(url(world), headers=auth(world.admin_a1.id))).json()
    letters, report = part(dept, "examiners")["entries"]  # the admin's papers, then the report
    assert letters["heading"] == "Panel of examiners and letters with the examiners"
    assert "Prof. X" not in str(report) and "IIT Bombay" not in str(report)
    assert report["heading"] == "Report of an examiner (name withheld until the viva)"
    # Unreleased: the scholar's file does not hold the report at all.
    own = (await client.get(url(world), headers=auth(world.scholar_a1.id))).json()
    assert part(own, "examiners")["note"] == "Not on record"
    office = (await client.get(url(world), headers=auth(world.exam_office.id))).json()
    assert part(office, "examiners")["entries"][1]["heading"] == "Report of Prof. X"
    assert part(office, "submission")["entries"][0]["signed"] is False  # approved, unsigned
