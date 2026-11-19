"""The PhD file's generated forms (PRD F17, F17b): each entry as the university's paper form."""

from tests.conftest import auth
from tests.test_committee import SEN, add, form

API = "/api/v1"


def entry(view, key):
    (e,) = next(a for a in view["annexures"] if a["key"] == key)["entries"]
    return e["form"]


async def test_committee_and_comprehensive_print_as_their_forms(client, world):
    fid = (await form(client, world, reference="DRC/2026/14")).json()["formations"][0]["id"]
    await add(client, world, fid, {"faculty_id": str(world.sup_a2_faculty.id)})
    await add(client, world, fid, {**SEN, "role": "chairperson"})
    await client.post(
        f"{API}/scholars/{world.s_a1.id}/comprehensive",
        headers=auth(world.admin_a1.id),
        json={"held_in": "2026-05-01", "result": "satisfactory"},
    )
    view = (
        await client.get(
            f"{API}/internal/scholars/{world.s_a1.id}/phd-file", headers=auth(world.admin_a1.id)
        )
    ).json()

    rac = entry(view, "advisory_committee")
    assert rac["title"] == "Formation of Research Advisory Committee"
    assert ["Name of the Student", "Scholar A1"] in rac["fields"]
    assert ["Reference", "DRC/2026/14"] in rac["fields"]
    (members,) = rac["tables"]
    assert [r[1:] for r in members["rows"]] == [
        ["Prof. R. Sen", "IIT Delhi", "Chairperson"],
        ["Sup A2", "Dept A2", "Member"],
        ["Meera", "Dept A1", "Supervisor (Secretary and Member)"],
    ]
    assert [s["role"] for s in rac["signed_by"]] == ["Secretary, DRC", "Chairperson, DRC", "Dean"]
    assert "Ph.D. Coordinator" in rac["copy_to"]
    assert rac["recorded"].startswith("Recorded in Anveshan by ")

    exam = entry(view, "comprehensive")
    assert exam["title"] == "Report of Comprehensive Examination"
    assert exam["tables"][1]["rows"] == [["1", "May 2026", "Satisfactory"]]
    # Signed by the committee as it stood: supervisor first, chairperson last; nobody's
    # specimen is printed — none of them signed this in the portal.
    assert [(s["name"], s["role"], s["signature"]) for s in exam["signed_by"]] == [
        ("Meera", "Supervisor", None),
        ("Sup A2", "Member", None),
        ("Prof. R. Sen", "Chairperson", None),
    ]
    assert exam["forwarded"]["to"] == "Dean of the Faculty"
