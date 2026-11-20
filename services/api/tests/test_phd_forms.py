"""The PhD file's generated forms (PRD F17, F17b): each entry as the university's paper form."""

from app.phd_forms import SYNOPSIS_RECOMMENDATION, _rac_says
from tests.conftest import auth
from tests.test_committee import SEN, add, form
from tests.test_viva_arrangements import act, documents_on, ready_arrangement  # noqa: F401

API = "/api/v1"


def entry(view, key, n=-1):
    """The entry's form: its last by default; a seminar's are its notice, report, attendance."""
    (e,) = next(a for a in view["annexures"] if a["key"] == key)["entries"]
    return e["forms"][n]


def test_the_synopsis_sentence_prints_only_when_the_panel_recommended():
    assert _rac_says([("A", "recommended"), ("B", "recommended")]) == SYNOPSIS_RECOMMENDATION
    assert _rac_says([("A", "not_recommended"), ("B", "not_recommended")]) == "Not recommended."
    assert _rac_says([("A", "recommended"), ("B", "recommended_with_changes")]) == (
        "A: Recommended; B: Recommended with changes."
    )
    assert _rac_says([]) == "_" * 60  # nothing on record, or not finalised: a line to fill in


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


async def test_approved_items_carry_their_approval_record_and_the_viva_its_board(
    client,
    session,
    world,
    documents_on,  # noqa: F811
):
    tid, aid = await ready_arrangement(client, session, world)
    await act(client, world.exam_office, aid, "submit")
    assert (await act(client, world.vice_chancellor, aid, "approve")).status_code == 200

    def forms(view, key):
        return [
            e["forms"][-1] for e in next(a for a in view["annexures"] if a["key"] == key)["entries"]
        ]

    async def view_of(user):
        url = f"{API}/internal/scholars/{world.s_a1.id}/phd-file"
        return (await client.get(url, headers=auth(user.id))).json()

    office = await view_of(world.exam_office)
    thesis = forms(office, "submission")[0]
    assert thesis["title"] == "Submission of Thesis"
    record = thesis["tables"][-1]
    assert record["title"] == "Approval record" and record["rows"][0][0] == "Submitted"
    assert thesis["signed_by"][0]["role"] == "Student"
    assert all(s["signature"] is None for s in thesis["signed_by"])  # nobody signed in the portal

    (approval,) = forms(office, "viva")
    board = approval["tables"][0]
    assert board["title"] == "Constitution of the Examination Board"
    assert [r[3] for r in board["rows"]] == ["Supervisor", "Chairperson", "External Examiner"]
    assert "Prof. K. Rao" in str(board["rows"])
    assert [s["role"] for s in approval["signed_by"]] == ["Vice Chancellor"]
    # Before the viva the scholar's copy does not name the external examiner.
    (own,) = forms(await view_of(world.scholar_a1), "viva")
    assert "Prof. K. Rao" not in str(own) and "Name withheld until the viva" in str(own)

    await client.post(
        f"{API}/theses/{tid}/vivas",
        headers=auth(world.exam_office.id),
        json={"held_on": "2026-10-10", "outcome": "pass"},
    )
    (_, report) = forms(await view_of(world.scholar_a1), "viva")
    assert report["title"] == "Viva-Voce Examination Report"
    assert ["Outcome", "Pass"] in report["fields"]
    assert [s["role"] for s in report["signed_by"]] == [
        "Supervisor",
        "Chairperson",
        "External Examiner",
    ]


async def test_the_exam_office_sees_the_synopsis_result_but_not_the_answers(client, world):
    from tests.test_seminar_forms import grade, questions, schedule

    seminar_id = (await schedule(client, world, kind="pre_synopsis")).json()["id"]
    answers = [
        {"question": q, "answer": "yes"} for q in await questions(client, world, "pre_synopsis")
    ]
    res = await grade(
        client,
        seminar_id,
        world,
        {"answers": answers, "recommendation": "recommended", "comment": "Good."},
    )
    assert res.status_code == 200, res.text

    async def synopsis(user):
        res = await client.get(
            f"{API}/internal/scholars/{world.s_a1.id}/phd-file", headers=auth(user.id)
        )
        assert res.status_code == 200, res.text
        return entry(res.json(), "pre_synopsis_seminar", 1)

    blank = "Recommendation of the RAC: " + "_" * 60
    assert (await synopsis(world.exam_office))["statement"] == blank  # not finalised yet

    done = await client.post(
        f"{API}/seminars/{seminar_id}/scholars/{world.s_a1.id}/finalise",
        json={"points": [{"part": "writing_presentation", "text": "Fix figures"}]},
        headers=auth(world.meera.id),
    )
    assert done.status_code == 200, done.text

    exam = await synopsis(world.exam_office)
    assert exam["statement"] == "Recommendation of the RAC: " + SYNOPSIS_RECOMMENDATION
    assert exam["tables"] == []  # the answers and comments stay with the review's readers
    library = await client.get(
        f"{API}/internal/scholars/{world.s_a1.id}/phd-file", headers=auth(world.library.id)
    )
    (seminar,) = [a for a in library.json()["annexures"] if a["key"] == "pre_synopsis_seminar"]
    assert seminar["entries"] == []  # the Library sees no seminars at all
    admin = await synopsis(world.admin_a1)
    assert admin["tables"] and "Good." in admin["statement"]


async def test_a_seminar_notice_is_signed_by_the_admin_the_head_and_the_dean(client, world):
    from tests.test_seminar_forms import schedule

    seminar_id = (await schedule(client, world, kind="pre_synopsis", venue="Bosch Hall")).json()[
        "id"
    ]
    view = (
        await client.get(
            f"{API}/internal/scholars/{world.s_a1.id}/phd-file", headers=auth(world.admin_a1.id)
        )
    ).json()
    notice = entry(view, "pre_synopsis_seminar", 0)
    assert notice["title"] == "Pre-Thesis Synopsis Seminar: Circular"
    assert "scheduled on 20 November 2026 (Friday) at 10:00 AM in Bosch Hall." in notice["intro"]
    assert [s["role"] for s in notice["signed_by"]] == [
        "Department Admin",
        "Head of Department",
        "Dean",
    ]
    assert all(s["signature"] is None for s in notice["signed_by"])  # signed by hand
    assert entry(view, "pre_synopsis_seminar", 1)["title"] == "Pre-Thesis Synopsis Report"

    # The department prints it from the seminar; a panel member may not.
    res = await client.get(
        f"{API}/internal/seminars/{seminar_id}/notice", headers=auth(world.admin_a1.id)
    )
    assert res.status_code == 200, res.text
    assert [n["title"] for n in res.json()["forms"]] == [notice["title"]]
    res = await client.get(
        f"{API}/internal/seminars/{seminar_id}/notice", headers=auth(world.sup_b1.id)
    )
    assert res.status_code == 403


async def test_the_department_admin_changes_who_signs_and_what_the_notice_says(client, world):
    from tests.test_seminar_forms import schedule

    seminar_id = (await schedule(client, world, kind="pre_synopsis")).json()["id"]
    notice_url = f"{API}/seminars/{seminar_id}/notice"
    admin = auth(world.admin_a1.id)

    async def printed():
        res = await client.get(f"{API}/internal/seminars/{seminar_id}/notice", headers=admin)
        assert res.status_code == 200, res.text
        (only,) = res.json()["forms"]
        return only

    # The department's own signers, for every seminar of the department.
    res = await client.put(
        f"{notice_url}/department", headers=admin, json={"signers": ["dean", "drc_secretary"]}
    )
    assert res.status_code == 200, res.text
    assert res.json()["department_signers"] == ["drc_secretary", "dean"]  # in signing order
    assert [s["role"] for s in (await printed())["signed_by"]] == ["Secretary, DRC", "Dean"]

    # This seminar only: signers, wording and copy list; the rest stays as it was.
    res = await client.put(
        notice_url,
        headers=admin,
        json={
            "signers": ["unit_head", "admin"],
            "announcement": "The seminar is moved.",
            "copy_to": ["The Registrar"],
        },
    )
    assert res.status_code == 200, res.text
    notice = await printed()
    assert [s["role"] for s in notice["signed_by"]] == ["Department Admin", "Head of Department"]
    assert notice["intro"].endswith("The seminar is moved.")
    assert notice["copy_to"] == ["The Registrar"]
    assert notice["statement"].startswith("All are cordially invited")  # not changed: standard

    # Back to the department's signers and Anveshan's wording.
    res = await client.put(notice_url, headers=admin, json={})
    assert res.json()["custom"] == {} and res.json()["signers"] == ["drc_secretary", "dean"]

    # A head (the Dean) may read it but not change it; a panel member may do neither.
    assert (await client.get(notice_url, headers=auth(world.dean_a.id))).status_code == 200
    head = await client.put(notice_url, headers=auth(world.dean_a.id), json={})
    assert head.status_code == 403
    assert (await client.get(notice_url, headers=auth(world.sup_b1.id))).status_code == 403
    bad = await client.put(notice_url, headers=admin, json={"signers": ["registrar"]})
    assert bad.status_code == 422


async def test_the_attendance_sheet_names_who_is_expected_and_leaves_rows_to_sign(client, world):
    from tests.test_seminar_forms import schedule

    seminar_id = (await schedule(client, world, kind="registration")).json()["id"]
    res = await client.get(
        f"{API}/internal/seminars/{seminar_id}/attendance", headers=auth(world.admin_a1.id)
    )
    assert res.status_code == 200, res.text
    (sheet,) = res.json()["forms"]
    assert sheet["title"] == "Registration Seminar: Attendance Sheet"
    (table,) = sheet["tables"]
    assert table["columns"] == ["S. No.", "Faculty / Scholar Name", "Designation", "Signature"]
    names = [r[1] for r in table["rows"] if r[1]]
    # The supervisor, the panel, then the scholar; the rest left blank to sign.
    assert names == [world.meera.full_name, world.sup_b1.full_name, world.scholar_a1.full_name]
    assert table["rows"][2][2] == "Research Scholar"
    assert table["rows"][-1][1:] == ["", "", ""] and len(table["rows"]) == 18
    assert sheet["signed_by"] == []  # everyone signs in the table
    assert sheet["paper"] == "attendance"  # its approved scan replaces it in the signed file
    view = (
        await client.get(
            f"{API}/internal/scholars/{world.s_a1.id}/phd-file", headers=auth(world.admin_a1.id)
        )
    ).json()
    (e,) = next(a for a in view["annexures"] if a["key"] == "registration_seminar")["entries"]
    assert [f["title"].split(": ")[-1] for f in e["forms"]] == [
        "Circular",
        "Registration Seminar Report",
        "Attendance Sheet",
    ]
    bad = await client.get(
        f"{API}/internal/seminars/{seminar_id}/minutes", headers=auth(world.admin_a1.id)
    )
    assert bad.status_code in (404, 422)  # no such paper
