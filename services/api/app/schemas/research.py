"""Boundary models of the research-record modules: publications, conferences, documents and
thesis (PRD M1-M3). Literals come from app/enums.py, mirroring the DB CHECKs."""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.enums import (
    ConferenceType,
    DocKind,
    Indexing,
    ItemState,
    PubStatus,
    PubType,
    Recommendation,
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


class ThesisIn(BaseModel):
    title: LongTitle


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


class ExaminerReportView(BaseModel):
    id: uuid.UUID
    examiner_name: str | None
    institution: str | None
    received_on: date
    recommendation: Recommendation
    notes: str
    released: bool


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


class EvaluationView(BaseModel):
    thesis_id: uuid.UUID
    names_hidden: bool
    reports: list[ExaminerReportView]
    unreleased_count: int
    vivas: list[VivaView]
    deposit: DepositView | None
    can_record_reports: bool
    can_record_viva: bool
    can_record_deposit: bool
