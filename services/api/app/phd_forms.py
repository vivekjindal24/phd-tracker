"""The PhD file's generated forms (PRD F17, F17b): each entry printed as the university's paper
form — the scholar's particulars, the body of the form, the signature block of those who sign it,
"forwarded to" and "copy to" — from what is already recorded. Layout after the university's own
forms (Medi-Caps: Form V, VI, VII, VIII). Their titles and form numbers become university
settings later (PRD F17, part 4); until then each form carries Anveshan's title.

A form never invents a signature: a signatory's specimen is printed only where they signed an
approval in the portal (F17b); everyone else gets a line to sign the printed copy by hand."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import committee, coursework, grading, items, notices, scope, viva
from app.auth.principal import Principal
from app.enums import (
    LOCAL_TZ,
)
from app.errors import ApiError
from app.models import (
    AuditLog,
    CommitteeFormation,
    ComprehensiveExam,
    Faculty,
    Milestone,
    OrgUnit,
    Scholar,
    Seminar,
    SeminarGrade,
    SeminarPanel,
    SeminarScholar,
    User,
    VivaArrangement,
    VivaBoardMember,
)

Form = dict[str, Any]
RAC = "Signature of the Research Advisory Committee"
SEMINAR_DATES = {
    "registration": "Date of Seminar",
    "pre_synopsis": "Date of Pre-Thesis Synopsis Seminar",
}
SEMINAR_TITLES = {
    "registration": "Registration Seminar Report",
    "pre_synopsis": "Pre-Thesis Synopsis Report",
}
ACTIONS = {
    "submit": "Submitted",
    "resubmit": "Resubmitted",
    "approve": "Approved",
    "send_back": "Sent back",
}
BOARD_ROLES = {
    "chairperson": "Chairperson",
    "external_examiner": "External Examiner",
    "member": "Member",
}
RECOMMENDATIONS = {
    "recommended": "Recommended",
    "recommended_with_changes": "Recommended with changes",
    "not_recommended": "Not recommended",
}
SYNOPSIS_RECOMMENDATION = (
    "The Pre-Thesis Synopsis is presented in front of the RAC and certified to be satisfactory "
    "and has been approved by the RAC to submit the thesis."
)


def _attendance_table(rows: list[list[str]]) -> dict[str, Any]:
    return {
        "title": "",
        "columns": ["S. No.", "Faculty / Scholar Name", "Designation", "Signature"],
        "rows": rows,
        "widths": [0.08, 0.37, 0.25, 0.3],
        "row_height": 24,  # room to sign
    }


def _rac_says(recommended: list[tuple[str, str]]) -> str:
    """The approval sentence only when every member recommended; otherwise what they did
    recommend, member by member when they differ; a blank line when nothing is on record."""
    said = {r for _, r in recommended}
    if not said:
        return "_" * 60
    if said == {"recommended"}:
        return SYNOPSIS_RECOMMENDATION
    if len(said) == 1:
        return RECOMMENDATIONS[said.pop()] + "."
    return "; ".join(f"{name}: {RECOMMENDATIONS[r]}" for name, r in recommended) + "."


def _d(day: date | datetime | None) -> str:
    if day is None:
        return "—"
    if isinstance(day, datetime):
        day = day.astimezone(LOCAL_TZ).date()
    return f"{day:%d/%m/%Y}"


def form(
    title: str,
    fields: list[tuple[str, Any]],
    *,
    intro: str | None = None,
    tables: list[dict[str, Any]] | None = None,
    statement: str | None = None,
    signed_by: list[dict[str, Any]] | None = None,
    signed_heading: str | None = None,
    forwarded: dict[str, Any] | None = None,
    copy_to: list[str] | None = None,
    recorded: str | None = None,
    paper: str | None = None,
) -> Form:
    return {
        "title": title,
        "intro": intro,  # a paragraph above the particulars (a notice's announcement)
        "fields": [[k, str(v)] for k, v in fields if v not in (None, "")],
        "tables": tables or [],
        "statement": statement,
        "signed_heading": signed_heading,
        "signed_by": signed_by or [],
        "forwarded": forwarded,
        "copy_to": copy_to or [],
        "recorded": recorded,
        # The signed paper (enums.DOCUMENT_KINDS) whose approved scan takes this page's place in
        # the signed PhD file; null: printed whatever is uploaded.
        "paper": paper,
    }


ATTENDANCE_ROWS = 18  # one A4 page of rows on the attendance sheet, the named ones included
signer = notices.signer
holder = notices.holder


class Forms:
    """Builds the forms of one scholar's file for one caller; shared particulars are read once."""

    def __init__(self, session: AsyncSession, principal: Principal, scholar: Scholar):
        self.session, self.principal, self.scholar = session, principal, scholar
        self._block: list[tuple[str, Any]] | None = None
        self._officers: dict[str, str | None] | None = None

    # --- what every form shares ----------------------------------------------------------

    async def particulars(self) -> list[tuple[str, Any]]:
        """The scholar's block at the head of every form."""
        if self._block is None:
            s = self.scholar
            name, unit = (
                await self.session.execute(
                    select(User.full_name, OrgUnit.name)
                    .join(Scholar, Scholar.user_id == User.id)
                    .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
                    .where(Scholar.id == s.id)
                )
            ).one()
            mode = {"full_time": "Full time", "part_time": "Part time"}.get(s.study_mode or "")
            self._block = [
                ("Name of Supervisor", await committee.convener(self.session, s)),
                ("Name of the Student", name),
                ("Enrolment No.", s.roll_number),
                ("Date of admission", _d(s.admission_date) if s.admission_date else None),
                ("Nature of registration", mode),
                ("Department", unit),
            ]
        return list(self._block)

    async def officers(self) -> dict[str, str | None]:
        """The Chairperson and Secretary of the department's research committee (DRC) and the
        head of the faculty above the department (the Dean)."""
        if self._officers is None:
            drc = await committee.current(
                self.session, CommitteeFormation.unit_id == self.scholar.unit_id
            )
            members = await committee.members(self.session, drc.id) if drc else []
            chair = next((m["name"] for m in members if m["role"] == "chairperson"), None)
            secretary = next((m["name"] for m in members if m["role"] == "secretary"), None)
            parent = await self.session.scalar(
                select(OrgUnit.parent_id).where(OrgUnit.id == self.scholar.unit_id)
            )
            dean = await holder(self.session, parent, "unit_head")
            self._officers = {"chair": chair, "secretary": secretary, "dean": dean}
        return self._officers

    async def forwarded(self, to: str = "Dean of the Faculty") -> dict[str, Any]:
        o = await self.officers()
        return {"to": to, "by": [signer(o["chair"], "Chairperson, DRC")]}

    async def rac_on(self, day: date | datetime | None) -> list[dict[str, Any]]:
        """The advisory committee as it stood on `day`: the newest version formed by then, else
        the first one."""
        versions = await committee.formations(
            self.session, CommitteeFormation.scholar_id == self.scholar.id
        )
        if not versions:
            return []
        when = day.astimezone(LOCAL_TZ).date() if isinstance(day, datetime) else day
        then = [v for v in versions if when is None or v["formed_on"] <= when]
        return (then[0] if then else versions[-1])["members"]

    async def rac_signers(self, day: date | datetime | None) -> list[dict[str, Any]]:
        """Supervisor first, then the members, the chairperson last — as the paper forms sign."""
        members = await self.rac_on(day)
        supervisor = await committee.convener(self.session, self.scholar)
        out = [signer(supervisor, "Supervisor")]
        for m in members:
            if m["role"] == "secretary" or m["name"] == supervisor:
                continue  # the supervisor is the committee's secretary: signs once
            if m["role"] != "chairperson":
                out.append(signer(m["name"], committee.ROLE_LABELS[m["role"]]))
        out += [signer(m["name"], "Chairperson") for m in members if m["role"] == "chairperson"]
        return out

    async def recorded(self, table: str, record_id: uuid.UUID) -> str | None:
        """Who recorded it in Anveshan and when — the record of a form with no approval chain."""
        row = (
            await self.session.execute(
                select(User.full_name, AuditLog.at)
                .join(User, User.id == AuditLog.actor_id)
                .where(
                    AuditLog.table_name == table,
                    AuditLog.record_id == str(record_id),
                    AuditLog.action == "insert",
                )
                .order_by(AuditLog.at)
                .limit(1)
            )
        ).first()
        return f"Recorded in Anveshan by {row[0]} on {_d(row[1])}." if row else None

    # --- the forms -----------------------------------------------------------------------

    async def appointment(self, a: dict[str, Any]) -> Form:
        o = await self.officers()
        role = "Supervisor" if a["role"] == "supervisor" else "Co-supervisor"
        return form(
            f"Appointment of {role}",
            [
                *await self.particulars(),
                (f"{role} appointed", a["faculty"]["name"]),
                ("Appointed on", _d(a["appointed_on"]) if a["appointed_on"] else None),
                ("Order", a["order_ref"]),
                ("Ended on", _d(a["ended_on"]) if a["ended_on"] else None),
            ],
            signed_by=[signer(o["chair"], "Chairperson, DRC"), signer(o["dean"], "Dean")],
            recorded=await self.recorded("supervisor_appointments", a["id"]),
        )

    async def committee_formation(self, f: dict[str, Any]) -> Form:
        o = await self.officers()
        rows = [
            [m["name"], m["institution"], committee.ROLE_LABELS[m["role"]]] for m in f["members"]
        ]
        if f["secretary"] and all(m["role"] != "secretary" for m in f["members"]):
            unit = (await self.particulars())[-1][1]
            rows.append([f["secretary"], unit, "Supervisor (Secretary and Member)"])
        rows = [[str(n), *r] for n, r in enumerate(rows, start=1)]
        return form(
            "Formation of Research Advisory Committee",
            [
                *await self.particulars(),
                ("Formed on", _d(f["formed_on"])),
                ("Reference", f["reference"]),
            ],
            tables=[
                {
                    "title": "Members",
                    "columns": ["No.", "Name", "Department", "Chairperson/Member"],
                    "rows": rows,
                }
            ],
            signed_by=[
                signer(o["secretary"], "Secretary, DRC"),
                signer(o["chair"], "Chairperson, DRC"),
                signer(o["dean"], "Dean"),
            ],
            copy_to=[
                "Dean of the Faculty",
                "Dean Research",
                "The Chairperson and all the members",
                "Ph.D. Coordinator",
            ],
            recorded=await self.recorded("committee_formations", f["id"]),
        )

    async def comprehensive(self, exam: ComprehensiveExam, attempts: list[ComprehensiveExam]):
        summary = await coursework.summary(self.session, self.scholar.id)
        courses = [[c.code, c.title, f"{c.credits:g}", e.grade or "—"] for e, c in summary["rows"]]
        return form(
            "Report of Comprehensive Examination",
            await self.particulars(),
            tables=[
                {
                    "title": "Course work done",
                    "columns": ["Course code", "Course name", "Credit", "Grade obtained"],
                    "rows": [
                        *courses,
                        ["", "Total credit", f"{summary['credits']:g}", ""],
                        ["", "CGPA", "", str(summary["cgpa"] or "—")],
                    ],
                },
                {
                    "title": "Attempts",
                    "columns": ["No. of attempt", "Date of exam", "Result"],
                    "rows": [
                        [str(a.attempt), f"{a.held_in:%B %Y}", a.result.capitalize()]
                        for a in attempts
                        if a.attempt <= exam.attempt
                    ],
                },
            ],
            statement=f"Result: {exam.result.capitalize()}"
            + (f". {exam.notes}" if exam.notes else ""),
            signed_heading=RAC,
            signed_by=await self.rac_signers(exam.held_in),
            forwarded=await self.forwarded(),
            recorded=await self.recorded("comprehensive_exams", exam.id),
        )

    async def seminar_notice(self, s: Seminar) -> Form:
        """The circular announcing the seminar: Anveshan's wording and the department's signers,
        as the department admin changed them for this seminar (owner, 2026-11-21)."""
        wording = notices.printed(s)
        return form(
            f"{notices.name(s)}: Circular",
            await self._seminar_details(s),
            intro=f"Dated {_d(s.created_at)}\n\n{wording['announcement']}",
            statement=wording["closing"],
            signed_by=await notices.signers(self.session, s),
            copy_to=wording["copy_to"],
            paper="notice",
        )

    async def seminar_attendance(self, s: Seminar) -> Form:
        """The attendance sheet: the notice's announcement and the scholar's details, then a
        row for the supervisor, each panel member and the scholar, already named, and blank
        rows for everyone else who attends — each to sign by hand."""
        supervisor = await self.session.execute(
            select(User.full_name, Faculty.designation)
            .join(Faculty, Faculty.user_id == User.id)
            .where(Faculty.id == self.scholar.supervisor_id)
        )
        panel = await self.session.execute(
            select(User.full_name, Faculty.designation)
            .join(Faculty, Faculty.user_id == User.id)
            .join(SeminarPanel, SeminarPanel.faculty_id == Faculty.id)
            .where(SeminarPanel.seminar_id == s.id, SeminarPanel.deleted_at.is_(None))
            .order_by(User.full_name)
        )
        named: list[tuple[str, str]] = []
        for who, designation in [*supervisor, *panel]:
            if who not in (n for n, _ in named):
                named.append((who, designation))
        rows = await self._attendance_rows(named)
        return form(
            f"{notices.name(s)}: Attendance Sheet",
            await self._seminar_details(s),
            intro=f"Dated {_d(s.starts_at)}\n\n{notices.printed(s)['announcement']}",
            tables=[_attendance_table(rows)],
            paper="attendance",
        )

    async def _attendance_rows(self, named: list[tuple[str, str]]) -> list[list[str]]:
        """Those expected, then the scholar, then blank rows to an A4 page."""
        block = dict(await self.particulars())
        named = [*named, (block["Name of the Student"], "Research Scholar")]
        rows = [[str(i), *n, ""] for i, n in enumerate(named, 1)]
        return rows + [[str(i), "", "", ""] for i in range(len(rows) + 1, ATTENDANCE_ROWS + 1)]

    async def _seminar_details(self, s: Seminar) -> list[tuple[str, Any]]:
        """The scholar's details on the seminar's notice and attendance sheet."""
        block = dict(await self.particulars())
        fields = [
            ("Name of Scholar", block["Name of the Student"]),
            ("Enrolment No.", block["Enrolment No."]),
            ("Date of admission", block["Date of admission"]),
            ("Supervisor", block["Name of Supervisor"]),
            ("Department", block["Department"]),
            ("Topic", await self.title()),
        ]
        if s.kind == "pre_synopsis":
            fields.append(("Date of Registration Seminar", await self.registration_seminar()))
        return fields

    async def title(self) -> str | None:
        """The research title, else the newest approved title on a milestone."""
        return self.scholar.research_title or await self.session.scalar(
            select(Milestone.approved_title)
            .where(
                Milestone.scholar_id == self.scholar.id,
                Milestone.deleted_at.is_(None),
                Milestone.approved_title.is_not(None),
            )
            .order_by(Milestone.resolution_date.desc().nulls_last(), Milestone.created_at.desc())
            .limit(1)
        )

    async def registration_seminar(self) -> str | None:
        """The date of the scholar's first registration seminar."""
        reg = await self.session.scalar(
            select(func.min(Seminar.starts_at))
            .join(SeminarScholar, SeminarScholar.seminar_id == Seminar.id)
            .where(
                SeminarScholar.scholar_id == self.scholar.id,
                SeminarScholar.deleted_at.is_(None),
                Seminar.deleted_at.is_(None),
                Seminar.kind == "registration",
            )
        )
        return _d(reg) if reg else None

    async def seminar(self, s: Seminar, entry: SeminarScholar) -> Form:
        fields = await self.particulars()
        if s.kind == "registration":
            passed = await self.session.scalar(
                select(func.max(ComprehensiveExam.held_in)).where(
                    ComprehensiveExam.scholar_id == self.scholar.id,
                    ComprehensiveExam.result == "satisfactory",
                    ComprehensiveExam.deleted_at.is_(None),
                )
            )
            fields.append(
                ("Date of successful comprehensive exam", f"{passed:%B %Y}" if passed else None)
            )
        if s.kind == "pre_synopsis":
            fields.insert(2, ("Title of the Thesis", await self.title()))
            fields.append(("Date of Registration Seminar", await self.registration_seminar()))
        fields.append((SEMINAR_DATES[s.kind], _d(s.starts_at)))
        tables, comments, recommended = await self._marking(s, entry)
        signers = await self.rac_signers(s.starts_at)
        statement = comments
        if s.kind == "pre_synopsis":
            signers = [signer(fields[1][1], "Student"), *signers]
            statement = "Recommendation of the RAC: " + _rac_says(
                recommended if entry.finalised_at else []
            )
            if comments:
                statement += f"\n\n{comments}"
        return form(
            SEMINAR_TITLES[s.kind],
            fields,
            tables=tables,
            statement=statement,
            signed_heading=RAC,
            signed_by=signers,
            forwarded=await self.forwarded(),
            copy_to=["The student"] if s.kind == "pre_synopsis" else [],
            recorded=f"Review finalised in Anveshan on {_d(entry.finalised_at)}."
            if entry.finalised_at
            else None,
            paper="report",
        )

    async def _marking(
        self, s: Seminar, entry: SeminarScholar
    ) -> tuple[list[dict], str | None, list[tuple[str, str]]]:
        """The panel's answers to the form's questions, their comments and each member's
        recommendation — for those who may read the review on screen
        (grading.require_review_access). The Exam Office, which takes the thesis on from the
        synopsis, gets the synopsis recommendations alone (owner, 2026-11-20)."""
        try:
            path = await scope.unit_path(self.session, s.unit_id)
            await grading.require_review_access(
                self.session, self.principal, s, path, entry, self.scholar
            )
            full = True
        except ApiError:
            full = False
        exam_office = "exam_office" in self.principal.office_roles
        if not full and not (exam_office and s.kind == "pre_synopsis"):
            return [], None, []
        rows = await self.session.execute(
            select(SeminarGrade, User.full_name)
            .join(Faculty, Faculty.id == SeminarGrade.grader_id)
            .join(User, User.id == Faculty.user_id)
            .where(
                SeminarGrade.seminar_scholar_id == entry.id,
                SeminarGrade.deleted_at.is_(None),
                SeminarGrade.answers.is_not(None),
            )
            .order_by(User.full_name)
        )
        grades = list(rows)
        recommended = [(name, g.recommendation) for g, name in grades]
        if not grades or not full:
            return [], None, recommended
        questions = [a["question"] for a in grades[0][0].answers]
        table_rows = [
            [q]
            + [
                next((a["answer"] for a in g.answers if a["question"] == q), "—").capitalize()
                for g, _ in grades
            ]
            for q in questions
        ]
        table_rows.append(
            ["Recommendation"] + [RECOMMENDATIONS.get(g.recommendation, "—") for g, _ in grades]
        )
        comments = "; ".join(f"{name}: {g.comment}" for g, name in grades if g.comment)
        return (
            [{"title": "", "columns": ["", *[name for _, name in grades]], "rows": table_rows}],
            f"Brief comments about the student's performance: {comments}" if comments else None,
            recommended,
        )

    # --- forms approved in the portal: the approval record at the foot (F17b) ------------------

    async def approvals(
        self, item_type: str, item_id: uuid.UUID
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """The approval record as a table, and the approvers as signers with the specimen each
        signed with, if they signed (items.history)."""
        try:
            ctx = await items.load_ctx(self.session, self.principal, item_type, item_id)
        except ApiError:
            return [], []
        history = await items.history(self.session, ctx)
        rows = [
            [
                ACTIONS.get(h["action"], h["action"])
                + (f" at {h['step']}" if h["step"] and h["action"] != "submit" else ""),
                h["actor"] + (f" (on behalf of {h['on_behalf_of']})" if h["on_behalf_of"] else ""),
                _d(h["at"]),
            ]
            for h in history
        ]
        table = [{"title": "Approval record", "columns": ["Action", "By", "On"], "rows": rows}]
        signers = [
            signer(h["actor"], h["step"] or "Approved", h["signature"])
            for h in history
            if h["action"] == "approve"
        ]
        return (table if rows else []), signers

    async def clearance(self, c: Any) -> Form:
        table, approvers = await self.approvals("coursework_clearance", c.id)
        return form(
            "Coursework Clearance",
            [
                *await self.particulars(),
                ("Credits earned", f"{c.credits:g}" if c.credits is not None else None),
                ("CGPA", c.cgpa),
                ("Cleared on", _d(c.cleared_on) if c.cleared_on else None),
            ],
            tables=table,
            signed_heading="Approved by" if approvers else None,
            signed_by=approvers,
        )

    async def submission(self, t: Any) -> Form:
        table, approvers = await self.approvals("thesis_submission", t.id)
        student = (await self.particulars())[1][1]
        return form(
            "Submission of Thesis",
            [
                *await self.particulars(),
                ("Title of the Thesis", t.title),
                ("Submitted on", _d(t.submitted_at) if t.submitted_at else None),
                ("Plagiarism check", t.plagiarism_tool),
                (
                    "Similarity",
                    f"{t.plagiarism_score:g}%" if t.plagiarism_score is not None else None,
                ),
            ],
            tables=table,
            signed_heading="Signatures",
            signed_by=[signer(student, "Student"), *approvers],
        )

    async def _board(self, arrangement_id: uuid.UUID, names: bool) -> list[dict[str, Any]]:
        """The examination board (Form XI): the supervisor and each member by role; an external
        examiner unnamed for whoever may not see examiner names yet (viva.board)."""
        rows = await self.session.execute(
            select(VivaBoardMember, User.full_name, OrgUnit.name)
            .outerjoin(Faculty, Faculty.id == VivaBoardMember.faculty_id)
            .outerjoin(User, User.id == Faculty.user_id)
            .outerjoin(OrgUnit, OrgUnit.id == Faculty.unit_id)
            .where(
                VivaBoardMember.arrangement_id == arrangement_id,
                VivaBoardMember.deleted_at.is_(None),
            )
        )
        out = []
        for m, faculty_name, unit in rows:
            hidden = m.role == "external_examiner" and not names
            out.append(
                {
                    "role": BOARD_ROLES[m.role],
                    "name": "Name withheld until the viva" if hidden else m.name or faculty_name,
                    "institution": "" if hidden else m.institution or unit or "",
                    "order": viva.ROLE_ORDER.index(m.role),
                }
            )
        out.sort(key=lambda m: (m["order"], m["name"]))
        supervisor = await committee.convener(self.session, self.scholar)
        return [{"role": "Supervisor", "name": supervisor or "", "institution": ""}, *out]

    async def _names(self, a: VivaArrangement) -> bool:
        """Whether the caller may see the examiners' names on this viva's papers yet."""
        try:
            ctx = await items.load_ctx(self.session, self.principal, "viva_arrangement", a.id)
        except ApiError:
            return False
        return viva.sees_names(self.principal, ctx, await viva.held(self.session, a.id))

    async def viva_notice(self, a: VivaArrangement, thesis_title: str | None) -> Form:
        """The notice of the viva, with its board: Anveshan's wording and the department's
        signers — the Controller of Examinations, the HoD and the Dean unless the department
        admin changed them (owner, 2026-11-21)."""
        board = await self._board(a.id, await self._names(a))
        wording = notices.printed(a)
        block = dict(await self.particulars())
        return form(
            "Viva-Voce Examination: Notice",
            [
                ("Name of Scholar", block["Name of the Student"]),
                ("Enrolment No.", block["Enrolment No."]),
                ("Supervisor", block["Name of Supervisor"]),
                ("Department", block["Department"]),
                ("Title of the Thesis", thesis_title),
            ],
            intro=f"Dated {_d(a.created_at)}\n\n{wording['announcement']}",
            tables=[
                {
                    "title": "Examination Board",
                    "columns": ["No.", "Name", "Institution", "Role"],
                    "rows": [
                        [str(n), m["name"], m["institution"], m["role"]]
                        for n, m in enumerate(board, start=1)
                    ],
                }
            ],
            statement=wording["closing"],
            signed_by=await notices.signers(self.session, a),
            copy_to=wording["copy_to"],
            paper="viva_notice",
        )

    async def viva_attendance(self, a: VivaArrangement) -> Form:
        """The viva's attendance sheet: the board already named, then the scholar and blank
        rows for everyone else who attends."""
        board = await self._board(a.id, await self._names(a))
        named = [
            (m["name"], f"{m['role']}, {m['institution']}" if m["institution"] else m["role"])
            for m in board
        ]
        return form(
            "Viva-Voce Examination: Attendance Sheet",
            [(k, v) for k, v in (await self.particulars())[:2]],
            intro=f"Dated {_d(a.scheduled_at)}\n\n{notices.printed(a)['announcement']}",
            tables=[_attendance_table(await self._attendance_rows(named))],
            paper="attendance",
        )

    async def viva_approval(self, a: VivaArrangement, thesis_title: str | None) -> Form:
        """Approval to conduct the viva (Form X) with the board constituted for it (Form XI)."""
        table, approvers = await self.approvals("viva_arrangement", a.id)
        board = await self._board(a.id, await self._names(a))
        when = a.scheduled_at.astimezone(LOCAL_TZ)
        return form(
            "Approval for Conduct of Viva-Voce Examination",
            [
                *await self.particulars(),
                ("Title of the Thesis", thesis_title),
                ("Date and time", f"{when:%d/%m/%Y, %H:%M}"),
                ("Venue", a.venue),
                ("Online link", a.online_link),
            ],
            tables=[
                {
                    "title": "Constitution of the Examination Board",
                    "columns": ["No.", "Name", "Institution", "Role"],
                    "rows": [
                        [str(n), m["name"], m["institution"], m["role"]]
                        for n, m in enumerate(board, start=1)
                    ],
                },
                *table,
            ],
            statement=a.notes or None,
            signed_heading="Approved by" if approvers else None,
            signed_by=approvers,
        )

    async def viva_report(self, v: dict[str, Any], thesis_title: str | None) -> Form:
        """The viva-voce examination report (Form XII), signed by the board that held it."""
        board = await self._board(v["arrangement_id"], True) if v["arrangement_id"] else []
        signers = [signer(m["name"], m["role"]) for m in board]
        members_entered = len(board) > 1  # beyond the supervisor, who always sits
        return form(
            "Viva-Voce Examination Report",
            [
                *await self.particulars(),
                ("Title of the Thesis", thesis_title),
                ("Held on", _d(v["held_on"])),
                ("Venue", v["venue"]),
                ("Board", None if members_entered else v["panel"]),
                ("Outcome", v["outcome"].replace("_", " ").capitalize()),
            ],
            statement=v["notes"] or None,
            signed_heading="Signature of the Examination Board",
            signed_by=signers,
            recorded=await self.recorded("vivas", v["id"]),
        )
