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

from app import committee, coursework, grading, scope
from app.auth.principal import Principal
from app.enums import LOCAL_TZ
from app.errors import ApiError
from app.models import (
    AuditLog,
    CommitteeFormation,
    ComprehensiveExam,
    Faculty,
    Milestone,
    OrgUnit,
    RoleAssignment,
    Scholar,
    Seminar,
    SeminarGrade,
    SeminarScholar,
    User,
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
RECOMMENDATIONS = {
    "recommended": "Recommended",
    "recommended_with_changes": "Recommended with changes",
    "not_recommended": "Not recommended",
}
SYNOPSIS_RECOMMENDATION = (
    "The Pre-Thesis Synopsis is presented in front of the RAC and certified to be satisfactory "
    "and has been approved by the RAC to submit the thesis."
)


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
    tables: list[dict[str, Any]] | None = None,
    statement: str | None = None,
    signed_by: list[dict[str, Any]] | None = None,
    signed_heading: str | None = None,
    forwarded: dict[str, Any] | None = None,
    copy_to: list[str] | None = None,
    recorded: str | None = None,
) -> Form:
    return {
        "title": title,
        "fields": [[k, str(v)] for k, v in fields if v not in (None, "")],
        "tables": tables or [],
        "statement": statement,
        "signed_heading": signed_heading,
        "signed_by": signed_by or [],
        "forwarded": forwarded,
        "copy_to": copy_to or [],
        "recorded": recorded,
    }


def signer(name: str | None, role: str, signature: str | None = None) -> dict[str, Any]:
    return {"name": name or "", "role": role, "signature": signature}


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
            dean = parent and await self.session.scalar(
                select(User.full_name)
                .join(RoleAssignment, RoleAssignment.user_id == User.id)
                .where(
                    RoleAssignment.unit_id == parent,
                    RoleAssignment.role == "unit_head",
                    RoleAssignment.deleted_at.is_(None),
                )
                .order_by(User.full_name)
                .limit(1)
            )
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
            title = self.scholar.research_title or await self.session.scalar(
                select(Milestone.approved_title)
                .where(
                    Milestone.scholar_id == self.scholar.id,
                    Milestone.deleted_at.is_(None),
                    Milestone.approved_title.is_not(None),
                )
                .order_by(
                    Milestone.resolution_date.desc().nulls_last(), Milestone.created_at.desc()
                )
                .limit(1)
            )
            fields.insert(2, ("Title of the Thesis", title))
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
            fields.append(("Date of Registration Seminar", _d(reg) if reg else None))
        fields.append((SEMINAR_DATES[s.kind], _d(s.starts_at)))
        tables, comments = await self._marking(s, entry)
        signers = await self.rac_signers(s.starts_at)
        statement = comments
        if s.kind == "pre_synopsis":
            signers = [signer(fields[1][1], "Student"), *signers]
            statement = "Recommendation of the RAC: " + (
                SYNOPSIS_RECOMMENDATION if entry.finalised_at else "_" * 60
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
        )

    async def _marking(self, s: Seminar, entry: SeminarScholar) -> tuple[list[dict], str | None]:
        """The panel's answers to the form's questions and their comments — only for those who
        may read the review on screen (grading.require_review_access)."""
        try:
            path = await scope.unit_path(self.session, s.unit_id)
            await grading.require_review_access(
                self.session, self.principal, s, path, entry, self.scholar
            )
        except ApiError:
            return [], None
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
        if not grades:
            return [], None
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
        )
