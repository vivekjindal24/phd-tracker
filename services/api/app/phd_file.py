"""The PhD file (PRD F17): every annexure of a scholar's career in the order the university files
them, gathered from what is already recorded. Each part is read through the same rule as its
screen, so the file holds only what the caller may already see; an annexure the caller may not
read says so, and one with nothing recorded says "Not on record" — none is left out."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Any

from sqlalchemy import ColumnElement, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app import committee, coursework, phd_forms, scope, seminars, supervision, thesis
from app.auth.principal import Principal
from app.enums import LOCAL_TZ, PHD_ANNEXURES
from app.models import (
    Admission,
    ApprovalActionRow,
    CommitteeFormation,
    ComprehensiveExam,
    Conference,
    CourseworkClearance,
    Document,
    DocumentVersion,
    Faculty,
    FileRow,
    Milestone,
    NoDuesClearance,
    ProgressReport,
    Publication,
    Scholar,
    Seminar,
    SeminarPanel,
    SeminarScholar,
    ThesisSubmission,
    User,
    VivaArrangement,
)
from app.modules import module_enabled

NOT_ON_RECORD = "Not on record"
NOT_SHOWN = "Not shown to you"
NOT_IN_USE = "Not in use at this university"

Entry = dict[str, Any]


def _d(day: date | datetime | None) -> str:
    if day is None:
        return "—"
    if isinstance(day, datetime):
        day = day.astimezone(LOCAL_TZ).date()
    return f"{day.day} {day:%b %Y}"


def _day(at: date | datetime | None) -> date | None:
    return at.astimezone(LOCAL_TZ).date() if isinstance(at, datetime) else at


def _entry(
    at: date | datetime | None,
    heading: str,
    lines: list[tuple[str, Any]],
    signed=None,
    record: uuid.UUID | None = None,
    papers: tuple[str, ...] = ("signed_copy",),
    forms: list[dict[str, Any]] | None = None,
):
    """`record`: the row behind the entry; `papers`: the signed copies it holds, in the paper
    file's order (enums.DOCUMENT_KINDS, F17b). An entry with no record holds none."""
    return {
        "date": _day(at),
        "heading": heading,
        "lines": [[k, str(v)] for k, v in lines if v not in (None, "")],
        "signed": signed,
        "record": record,
        "papers": list(papers) if record else [],
        # The entry printed as the university's forms (phd_forms.py), in the paper file's order.
        "forms": forms or [],
    }


SEMINAR_PAPERS = ("notice", "report", "attendance")
EXAMINER_PAPERS = (
    "examiner_panel",
    "invite_national",
    "accept_national",
    "invite_international",
    "accept_international",
)


class _File:
    def __init__(self, session: AsyncSession, principal: Principal, scholar: Scholar):
        self.session, self.principal, self.scholar = session, principal, scholar
        self.forms = phd_forms.Forms(session, principal, scholar)
        self._ev: dict[str, Any] | bool | None = False  # the thesis evaluation, read once

    async def reads(self, entity: str) -> bool:
        """The caller reads this scholar's records of `entity` (scope.py, as every screen)."""
        return (
            await self.session.scalar(
                select(Scholar.id).where(
                    Scholar.id == self.scholar.id, scope.scholar_predicate(self.principal, entity)
                )
            )
            is not None
        )

    async def all(self, model: type, *where: ColumnElement[bool]) -> list[Any]:
        return list(
            await self.session.scalars(
                select(model).where(
                    model.scholar_id == self.scholar.id, model.deleted_at.is_(None), *where
                )
            )
        )

    async def signed(self, item_type: str, item: Any) -> bool | None:
        """An approved item is signed when every approval on it carries a signature (F17b)."""
        if item.state != "approved":
            return None
        sigs = list(
            await self.session.scalars(
                select(ApprovalActionRow.signature_id).where(
                    ApprovalActionRow.item_type == item_type,
                    ApprovalActionRow.item_id == item.id,
                    ApprovalActionRow.action == "approve",
                )
            )
        )
        return bool(sigs) and all(sigs)

    async def slot_files(self, slot: str) -> list[Entry]:
        rows = await self.session.scalars(
            select(FileRow).where(
                FileRow.table_name == "scholars",
                FileRow.record_id == self.scholar.id,
                FileRow.slot == slot,
                FileRow.status == "ready",
                FileRow.deleted_at.is_(None),
            )
        )
        return [_entry(f.created_at, f.file_name, [("Uploaded", _d(f.created_at))]) for f in rows]

    # --- the annexures, in the order of the career ----------------------------------------------

    async def admission(self) -> list[Entry]:
        out = []
        if await module_enabled(self.session, "admissions"):
            rows = await self.session.scalars(
                select(Admission).where(
                    Admission.scholar_id == self.scholar.id,
                    Admission.deleted_at.is_(None),
                    scope.unit_predicate(self.principal, "admissions", Admission.unit_id),
                )
            )
            out += [
                _entry(
                    a.admitted_on or a.interview_date,
                    "Admission",
                    [
                        ("Entrance route", a.entrance_route.replace("_", " ")),
                        ("Entrance score", a.entrance_score),
                        ("Interview", _d(a.interview_date) if a.interview_date else None),
                        ("Result", a.interview_result),
                        ("Admitted on", _d(a.admitted_on) if a.admitted_on else None),
                    ],
                    record=a.id,
                )
                for a in rows
            ]
        return out + await self.slot_files("entrance_minutes")

    async def employer_noc(self) -> list[Entry]:
        return await self.slot_files("employer_noc")

    async def supervision(self) -> list[Entry]:
        rows = await supervision.history(
            self.session, self.scholar.id, with_co=self.principal.co_supervision != "off"
        )
        rows.sort(key=lambda a: a["appointed_on"] or a["since"].date())
        return [
            _entry(
                a["appointed_on"] or a["since"],
                f"{'Supervisor' if a['role'] == 'supervisor' else 'Co-supervisor'}: "
                f"{a['faculty']['name']}",
                [
                    ("Appointed on", _d(a["appointed_on"]) if a["appointed_on"] else None),
                    ("Order", a["order_ref"]),
                    ("Ended on", _d(a["ended_on"]) if a["ended_on"] else None),
                ],
                record=a["id"],
                forms=[await self.forms.appointment(a)],
            )
            for a in rows
        ]

    async def advisory_committee(self) -> list[Entry]:
        if not await self.reads("committee_members"):
            raise _Hidden
        versions = await committee.formations(
            self.session, CommitteeFormation.scholar_id == self.scholar.id
        )
        return [
            _entry(
                f["formed_on"],
                f"Formed {_d(f['formed_on'])}" + (f" ({f['reference']})" if f["reference"] else ""),
                [
                    (m["name"], f"{m['institution']} · {committee.ROLE_LABELS[m['role']]}")
                    for m in f["members"]
                ],
                record=f["id"],
                forms=[await self.forms.committee_formation(f)],
            )
            for f in reversed(versions)  # oldest first, as filed
        ]

    async def coursework(self) -> list[Entry]:
        if not await module_enabled(self.session, "coursework"):
            raise _Off
        out = []
        if await self.reads("enrolments"):
            summary = await coursework.summary(self.session, self.scholar.id)
            # Always listed: the place for the mark sheets, before any grade is recorded too.
            out.append(
                _entry(
                    None,
                    "Courses and grades",
                    [
                        (f"{c.code} {c.title} ({e.semester})", e.grade or "Not graded")
                        for e, c in summary["rows"]
                    ]
                    + (
                        [("Credits", summary["credits"]), ("CGPA", summary["cgpa"])]
                        if summary["rows"]
                        else [("Courses", "None recorded yet")]
                    ),
                    record=self.scholar.id,
                    papers=("mark_sheet",),
                )
            )
        if await self.reads("coursework_clearances"):
            for c in await self.all(CourseworkClearance):
                out.append(
                    _entry(
                        c.cleared_on or c.approved_at,
                        "Coursework clearance",
                        [("State", c.state), ("Credits", c.credits), ("CGPA", c.cgpa)],
                        await self.signed("coursework_clearance", c),
                        c.id,
                        forms=[await self.forms.clearance(c)],
                    )
                )
        if not out and not await self.reads("enrolments"):
            raise _Hidden
        return out

    async def comprehensive(self) -> list[Entry]:
        if not await self.reads("comprehensive_exams"):
            raise _Hidden
        rows = sorted(await self.all(ComprehensiveExam), key=lambda e: e.attempt)
        return [
            _entry(
                e.held_in,
                f"Attempt {e.attempt}, {e.held_in:%B %Y}",
                [("Result", e.result.capitalize()), ("Notes", e.notes)],
                record=e.id,
                forms=[await self.forms.comprehensive(e, rows)],
            )
            for e in rows
        ]

    async def _seminars(self, kind: str) -> list[Entry]:
        visible = seminars.visible(self.principal, await seminars.open_to_faculty(self.session))
        if kind == "pre_synopsis" and "exam_office" in self.principal.office_roles:
            # The exam team takes the thesis on from the synopsis (owner, 2026-11-20).
            visible = true()
        rows = await self.session.execute(
            select(Seminar, SeminarScholar)
            .join(SeminarScholar, SeminarScholar.seminar_id == Seminar.id)
            .where(
                SeminarScholar.scholar_id == self.scholar.id,
                SeminarScholar.deleted_at.is_(None),
                Seminar.deleted_at.is_(None),
                Seminar.kind == kind,
                visible,
            )
            .order_by(Seminar.starts_at)
        )
        out = []
        for s, entry in rows:
            panel = await self.session.scalars(
                select(User.full_name)
                .join(Faculty, Faculty.user_id == User.id)
                .join(SeminarPanel, SeminarPanel.faculty_id == Faculty.id)
                .where(SeminarPanel.seminar_id == s.id, SeminarPanel.deleted_at.is_(None))
                .order_by(User.full_name)
            )
            out.append(
                _entry(
                    s.starts_at,
                    s.title,
                    [
                        ("Held", f"{_d(s.starts_at)}, {s.starts_at.astimezone(LOCAL_TZ):%H:%M}"),
                        ("Venue", s.venue),
                        ("Panel", ", ".join(panel)),
                        ("Status", s.status),
                        (
                            "Review finalised",
                            _d(entry.finalised_at) if entry.finalised_at else None,
                        ),
                    ],
                    record=entry.id,
                    papers=SEMINAR_PAPERS,
                    # As the paper file keeps them: the notice, the report, the attendance sheet.
                    # A progress seminar's report is the progress report, with its own PDF.
                    forms=[
                        await self.forms.seminar_notice(s),
                        *([await self.forms.seminar(s, entry)] if kind != "progress" else []),
                        await self.forms.seminar_attendance(s),
                    ],
                )
            )
        return out

    async def registration_seminar(self) -> list[Entry]:
        return await self._seminars("registration")

    async def decisions(self) -> list[Entry]:
        if not await self.reads("milestones"):
            raise _Hidden
        rows = sorted(
            await self.all(Milestone),
            key=lambda m: (m.resolution_date or m.created_at.date(), m.created_at),
        )
        return [
            _entry(
                m.resolution_date or m.created_at,
                m.milestone_type.replace("_", " ").capitalize(),
                [
                    ("Status", m.status),
                    ("Body", m.approval_body),
                    ("Resolution", m.resolution_number),
                    ("Dated", _d(m.resolution_date) if m.resolution_date else None),
                    ("Approved title", m.approved_title),
                    ("Notes", m.notes),
                ],
                record=m.id,
                papers=("drc_minutes", "drc_notice"),
            )
            for m in rows
        ]

    async def progress(self) -> list[Entry]:
        out = []
        if await self.reads("progress_reports"):
            for r in await self.all(ProgressReport):
                out.append(
                    _entry(
                        r.approved_at or r.submitted_at or r.created_at,
                        f"Progress report, {r.period} {r.report_year}",
                        [
                            ("State", r.state.replace("_", " ")),
                            ("Approved on", _d(r.approved_at) if r.approved_at else None),
                            (
                                "Assistantship",
                                f"May continue {r.assistantship} assistantship"
                                if r.assistantship
                                else None,
                            ),
                        ],
                        await self.signed("progress_report", r),
                        r.id,
                    )
                )
        out += await self._seminars("progress")
        return sorted(out, key=lambda e: e["date"] or date.max)

    async def publications(self) -> list[Entry]:
        out = []
        if await module_enabled(self.session, "publications") and await self.reads("publications"):
            for p in sorted(await self.all(Publication), key=lambda p: p.pub_year):
                out.append(
                    _entry(
                        p.approved_at or p.created_at,
                        p.title,
                        [
                            ("Authors", p.authors),
                            ("In", f"{p.venue} ({p.pub_year})"),
                            ("DOI", p.doi),
                            ("Indexing", ", ".join(p.indexing)),
                            ("Verified", p.state.replace("_", " ")),
                        ],
                        await self.signed("publication", p),
                        p.id,
                    )
                )
        if await module_enabled(self.session, "conferences") and await self.reads("conferences"):
            for c in sorted(await self.all(Conference), key=lambda c: c.event_date):
                out.append(
                    _entry(
                        c.event_date,
                        c.event_name,
                        [("Type", c.event_type), ("Place", c.place), ("Paper", c.title)],
                        record=c.id,
                    )
                )
        return out

    async def pre_synopsis_seminar(self) -> list[Entry]:
        return await self._seminars("pre_synopsis")

    async def _thesis(self) -> ThesisSubmission | None:
        if not await self.reads("thesis_submissions"):
            raise _Hidden
        rows = await self.all(ThesisSubmission)
        return max(rows, key=lambda t: t.created_at) if rows else None

    async def submission(self) -> list[Entry]:
        out = []
        t = await self._thesis()
        if t is not None:
            out.append(
                _entry(
                    t.submitted_at or t.created_at,
                    f"Thesis: {t.title}",
                    [
                        ("State", t.state.replace("_", " ")),
                        ("Plagiarism check", t.plagiarism_tool),
                        (
                            "Similarity",
                            f"{t.plagiarism_score}%" if t.plagiarism_score is not None else None,
                        ),
                    ],
                    await self.signed("thesis_submission", t),
                    t.id,
                    ("signed_copy", "fee_due", "corrections"),
                    [await self.forms.submission(t)],
                )
            )
        if await self.reads("no_dues_clearances"):
            for n in await self.all(NoDuesClearance):
                out.append(
                    _entry(
                        n.approved_at or n.created_at,
                        "No-dues clearance",
                        [("State", n.state.replace("_", " "))],
                        await self.signed("no_dues_clearance", n),
                        n.id,
                    )
                )
        return out

    async def _arrangement(self, arrangement_id: uuid.UUID | None) -> VivaArrangement | None:
        return await self.session.get(VivaArrangement, arrangement_id) if arrangement_id else None

    async def _title(self) -> str | None:
        """The thesis title the viva forms print, if the caller reads the thesis."""
        try:
            t = await self._thesis()
        except _Hidden:
            return None
        return t.title if t else None

    async def _evaluation(self) -> dict[str, Any] | None:
        """The thesis as its page shows it: examiner names withheld, unreleased reports kept
        from whoever may not see them (thesis.evaluation)."""
        if self._ev is False:
            t = await self._thesis()
            ctx = t and await thesis.load_thesis(self.session, self.principal, t.id)
            self._ev = ctx and await thesis.evaluation(self.session, self.principal, ctx)
        return self._ev  # type: ignore[return-value]

    async def examiners(self) -> list[Entry]:
        ev = await self._evaluation()
        if ev is None:
            return []
        return await self._examiner_papers() + [
            _entry(
                r["received_on"],
                f"Report of {r['examiner_name'] or 'an examiner (name withheld until the viva)'}",
                [
                    ("Institution", r["institution"]),
                    ("Examiner", r["origin"]),
                    ("Recommendation", r["recommendation"].replace("_", " ")),
                    ("Received", _d(r["received_on"])),
                ],
                record=r["id"],
            )
            for r in ev["reports"]
        ]

    async def _examiner_papers(self) -> list[Entry]:
        """The panel of examiners and the letters with them, which name the examiners: for the
        Research Office, the Exam Office and the admin over the scholar's unit; never the scholar
        or their supervisor, whatever other role they hold (owner, 2026-11-19)."""
        t = await self._thesis()
        if t is None or self.principal.scholar_id == self.scholar.id:
            return []
        if scope.guides(self.principal, self.scholar):
            return []
        offices = {"research_office", "exam_office"} & self.principal.office_roles
        if not offices and not self.principal.covers(
            "admin", await scope.unit_path(self.session, self.scholar.unit_id)
        ):
            return []
        return [
            _entry(
                t.submitted_at or t.created_at,
                "Panel of examiners and letters with the examiners",
                [],
                record=t.id,
                papers=EXAMINER_PAPERS,
            )
        ]

    async def viva(self) -> list[Entry]:
        out = []
        if await self.reads("viva_arrangements"):
            for a in sorted(await self.all(VivaArrangement), key=lambda a: a.scheduled_at):
                out.append(
                    _entry(
                        a.approved_at or a.created_at,
                        "Approval to hold the viva",
                        [
                            (
                                "Scheduled",
                                f"{_d(a.scheduled_at)}, "
                                f"{a.scheduled_at.astimezone(LOCAL_TZ):%H:%M}",
                            ),
                            ("Venue", a.venue),
                            ("State", a.state.replace("_", " ")),
                        ],
                        await self.signed("viva_arrangement", a),
                        a.id,
                        ("viva_approval", "viva_board", "viva_notice", "viva_examiner_email"),
                        [
                            await self.forms.viva_approval(a, await self._title()),
                            await self.forms.viva_notice(a, await self._title()),
                        ],
                    )
                )
        ev = await self._evaluation()
        for v in ev["vivas"] if ev else []:
            out.append(
                _entry(
                    v["held_on"],
                    "Viva voce",
                    [
                        ("Venue", v["venue"]),
                        ("Board", v["panel"]),
                        ("Outcome", v["outcome"]),
                        ("Notes", v["notes"]),
                    ],
                    record=v["id"],
                    papers=("viva_report", "attendance"),
                    forms=[
                        await self.forms.viva_report(v, await self._title()),
                        *(
                            [await self.forms.viva_attendance(arranged)]
                            if (arranged := await self._arrangement(v["arrangement_id"]))
                            else []
                        ),
                    ],
                )
            )
        return out

    async def award(self) -> list[Entry]:
        ev = await self._evaluation()
        if ev is None:
            return []
        out = [
            _entry(
                c["issued_on"],
                f"Provisional certificate {c['serial']}",
                [
                    ("Revoked", _d(c["revoked_at"]) if c["revoked_at"] else None),
                    ("Reason", c["revoked_reason"]),
                ],
                record=c["id"],
            )
            for c in reversed(ev["certificates"])
        ]
        if ev["deposit"]:
            d = ev["deposit"]
            out.append(
                _entry(
                    d["deposited_on"],
                    "Shodhganga deposit",
                    [("Handle", d["handle_url"])],
                    record=d["id"],
                )
            )
        return out

    async def copies(self) -> list[Entry]:
        if not await module_enabled(self.session, "documents"):
            raise _Off
        if not await self.reads("documents"):
            raise _Hidden
        rows = await self.session.execute(
            select(Document, DocumentVersion)
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .where(
                Document.scholar_id == self.scholar.id,
                Document.deleted_at.is_(None),
                DocumentVersion.deleted_at.is_(None),
                Document.doc_kind.in_(("proposal", "synopsis")),
            )
            .order_by(Document.created_at, DocumentVersion.version_no.desc())
        )
        latest: dict[uuid.UUID, Entry] = {}
        for doc, v in rows:
            latest.setdefault(
                doc.id,
                _entry(
                    v.created_at,
                    doc.title,
                    [("Kind", doc.doc_kind), ("Version", v.version_no)],
                    record=doc.id,
                ),
            )
        return list(latest.values())


class _Hidden(Exception):
    """The caller may not read this part of the record."""


class _Off(Exception):
    """The university does not use the module this part comes from."""


# key, default title, gatherer — the order of the career (PRD F17).
ANNEXURES: list[tuple[str, str, Callable[[_File], Awaitable[list[Entry]]]]] = [
    ("admission", "Admission and entrance record", _File.admission),
    ("employer_noc", "No-objection certificate from the employer", _File.employer_noc),
    ("supervision", "Appointment of supervisor and co-supervisor", _File.supervision),
    (
        "advisory_committee",
        "Formation of the research advisory committee",
        _File.advisory_committee,
    ),
    ("coursework", "Coursework, grades and clearance", _File.coursework),
    ("comprehensive", "Comprehensive examination", _File.comprehensive),
    ("registration_seminar", "Registration seminar", _File.registration_seminar),
    ("decisions", "Committee decisions", _File.decisions),
    ("progress", "Progress reports and progress seminars", _File.progress),
    ("publications", "Publications and conferences", _File.publications),
    ("pre_synopsis_seminar", "Pre-synopsis seminar", _File.pre_synopsis_seminar),
    ("submission", "Thesis submission, plagiarism check and no-dues", _File.submission),
    ("examiners", "Examiners' reports", _File.examiners),
    ("viva", "Viva voce", _File.viva),
    ("award", "Provisional certificate and Shodhganga deposit", _File.award),
    ("copies", "Copies of the synopsis and proposal", _File.copies),
]


assert tuple(k for k, _, _ in ANNEXURES) == PHD_ANNEXURES  # one list of keys, in the DB too


async def find_entry(
    session: AsyncSession, principal: Principal, scholar: Scholar, annexure: str, record: uuid.UUID
) -> Entry | None:
    """The entry as the caller's copy of the file holds it, if it does (a signed copy is read
    exactly as its entry)."""
    gather = next((g for k, _, g in ANNEXURES if k == annexure), None)
    if gather is None:
        return None
    try:
        entries = await gather(_File(session, principal, scholar))
    except (_Hidden, _Off):
        return None
    return next((e for e in entries if e["record"] == record), None)


async def build(session: AsyncSession, principal: Principal, scholar: Scholar) -> list[Entry]:
    """Every annexure, in order: its entries, or why it has none."""
    f = _File(session, principal, scholar)
    out = []
    for key, title, gather in ANNEXURES:
        try:
            entries, note = await gather(f), None
        except _Hidden:
            entries, note = [], NOT_SHOWN
        except _Off:
            entries, note = [], NOT_IN_USE
        dates = [e["date"] for e in entries if e["date"]]
        out.append(
            {
                "key": key,
                "title": title,
                "date": min(dates) if dates else None,
                "entries": entries,
                "note": note or (None if entries else NOT_ON_RECORD),
            }
        )
    return out
