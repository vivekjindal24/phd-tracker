"""Boundary models of the research-record modules: publications, conferences, documents and
thesis (PRD M1-M3). Literals come from app/enums.py, mirroring the DB CHECKs."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.enums import (
    ConferenceType,
    CopyKind,
    DocKind,
    Indexing,
    ItemState,
    PubStatus,
    PubType,
    Recommendation,
    ReviewStatus,
    VivaOutcome,
)
from app.schemas import LongTitle, Name, Notes, Ref, Venue

# --- publications & conferences ---------------------------------------------------------

Doi = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^10\.\d{4,9}/\S{1,200}$")]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]


class PublicationIn(BaseModel):
    title: LongTitle
    authors: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    pub_type: PubType
    venue: LongTitle
    issn_isbn: ShortText | None = None
    indexing: list[Indexing] = Field(default_factory=list, max_length=4)
    doi: Doi | None = None
    pub_year: int = Field(ge=1950, le=2100)
    pub_status: PubStatus


class PublicationUpdate(BaseModel):
    title: LongTitle | None = None
    authors: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
        | None
    ) = None
    pub_type: PubType | None = None
    venue: LongTitle | None = None
    issn_isbn: ShortText | None = None
    indexing: list[Indexing] | None = Field(default=None, max_length=4)
    doi: Doi | None = None
    pub_year: int | None = Field(default=None, ge=1950, le=2100)
    pub_status: PubStatus | None = None


class VerificationIn(BaseModel):
    """What the Library confirms at its step (PRD M1)."""

    indexing: list[Indexing] = Field(max_length=4)
    doi: Doi | None = None


class PublicationRow(BaseModel):
    id: uuid.UUID
    scholar: Ref
    title: str
    venue: str
    pub_type: PubType
    pub_year: int
    indexing: list[Indexing]
    state: ItemState
    waiting_on: str | None
    updated_at: datetime


class ConferenceIn(BaseModel):
    event_name: LongTitle
    event_type: ConferenceType
    event_date: date
    place: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    title: LongTitle | None = None


class ConferenceUpdate(BaseModel):
    event_name: LongTitle | None = None
    event_type: ConferenceType | None = None
    event_date: date | None = None
    place: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    title: LongTitle | None = None


class ConferenceOut(BaseModel):
    id: uuid.UUID
    scholar: Ref
    event_name: str
    event_type: ConferenceType
    event_date: date
    place: str
    title: str | None
    can_edit: bool


# --- documents & thesis -----------------------------------------------------------------


class DocumentIn(BaseModel):
    title: LongTitle
    doc_kind: DocKind


class DocumentUpdate(BaseModel):
    title: LongTitle | None = None
    doc_kind: DocKind | None = None


class VersionIn(BaseModel):
    file_id: uuid.UUID
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""


class VersionOut(BaseModel):
    id: uuid.UUID
    version_no: int
    note: str
    file_id: uuid.UUID
    file_name: str
    size_bytes: int
    created_at: datetime


class DocumentOut(BaseModel):
    id: uuid.UUID
    scholar: Ref
    title: str
    doc_kind: DocKind
    updated_at: datetime
    can_edit: bool
    versions: list[VersionOut]


class PlagiarismIn(BaseModel):
    plagiarism_tool: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    plagiarism_score: float = Field(ge=0, le=100)


class ExaminersIn(BaseModel):
    examiners: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


class ThesisRow(BaseModel):
    id: uuid.UUID
    scholar: Ref
    title: str
    state: ItemState
    waiting_on: str | None
    updated_at: datetime


class ExaminerReportIn(BaseModel):
    examiner_name: Name
    institution: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    received_on: date
    recommendation: Recommendation
    notes: Notes = ""


class ExaminerReportUpdate(BaseModel):
    examiner_name: Name | None = None
    institution: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = (
        None
    )
    received_on: date | None = None
    recommendation: Recommendation | None = None
    notes: Notes | None = None


class VivaIn(BaseModel):
    held_on: date
    venue: Venue = ""
    panel: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    outcome: VivaOutcome
    notes: Notes = ""


class VivaUpdate(BaseModel):
    held_on: date | None = None
    venue: Venue | None = None
    panel: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    outcome: VivaOutcome | None = None
    notes: Notes | None = None


class DepositIn(BaseModel):
    deposited_on: date
    handle_url: Annotated[
        str, StringConstraints(strip_whitespace=True, pattern=r"^https?://\S{3,500}$")
    ]


class ReviewCommentView(BaseModel):
    page: int
    body: str


class ExaminerReportView(BaseModel):
    id: uuid.UUID
    examiner_name: str | None
    institution: str | None
    received_on: date
    recommendation: Recommendation
    notes: str
    released: bool
    comments: list[ReviewCommentView] = []


class ReviewInviteIn(BaseModel):
    name: Name
    email: EmailStr
    institution: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    abstract: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
    ]
    deadline: date
    allow_download: bool = False


class ReviewUpdate(BaseModel):
    deadline: date | None = None
    allow_download: bool | None = None


class ReviewRow(BaseModel):
    """The Exam Office's view of one invitation; names never reach anyone else."""

    id: uuid.UUID
    name: str
    email: str
    institution: str
    deadline: date
    allow_download: bool
    status: ReviewStatus
    decline_reason: str | None
    submitted_at: datetime | None


class InvitationView(BaseModel):
    """What a link shows before accepting: this and nothing else (PRD M3)."""

    university: str
    reviewer_name: str
    thesis_title: str
    abstract: str
    deadline: date


class InvitationAccept(BaseModel):
    no_conflict: Literal[True]
    confidential: Literal[True]


class InvitationAccepted(BaseModel):
    has_password: bool
    email_sent: bool


class InvitationDecline(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""


class ReviewComment(BaseModel):
    id: uuid.UUID
    page: int
    body: str


class ReviewCommentIn(BaseModel):
    page: int = Field(ge=1, le=100_000)
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class ReviewSubmitIn(BaseModel):
    recommendation: Recommendation


class ReviewSummary(BaseModel):
    id: uuid.UUID
    thesis_title: str
    deadline: date
    status: ReviewStatus
    is_open: bool


class ReviewDetail(ReviewSummary):
    abstract: str
    allow_download: bool
    comments: list[ReviewComment]


class ReviewCopyView(BaseModel):
    """For the export service, which stamps `code` on the file behind `file_url`."""

    code: str
    file_url: str
    file_name: str
    download: bool


class ReviewCopyTrace(BaseModel):
    code: str
    kind: CopyKind
    issued_at: datetime
    reviewer_name: str
    reviewer_email: str
    institution: str
    thesis_title: str


class VivaView(BaseModel):
    id: uuid.UUID
    held_on: date
    venue: str
    panel: str
    outcome: VivaOutcome
    notes: str


class DepositView(BaseModel):
    id: uuid.UUID
    deposited_on: date
    handle_url: str


class CertificateView(BaseModel):
    id: uuid.UUID
    serial: str
    issued_on: date
    verify_path: str
    revoked_at: datetime | None
    revoked_reason: str | None


class CertificateRevokeIn(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class CertificateVerification(BaseModel):
    """The public page: this and nothing else (PRD M3)."""

    name: str
    thesis_title: str
    unit: str
    viva_date: date
    issued_on: date
    status: Literal["valid", "revoked"]


class EvaluationView(BaseModel):
    thesis_id: uuid.UUID
    names_hidden: bool
    reports: list[ExaminerReportView]
    unreleased_count: int
    vivas: list[VivaView]
    deposit: DepositView | None
    certificates: list[CertificateView]
    can_issue_certificate: bool
    can_revoke_certificate: bool
    can_record_reports: bool
    reviews: list[ReviewRow]
    can_invite_reviewers: bool
    can_record_viva: bool
    viva_block: str | None
    can_record_deposit: bool
