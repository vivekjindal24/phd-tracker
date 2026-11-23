"""University-wide settings, module switches and approval chains (DATABASE.md §3.2)."""

import json
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import (
    APPEALS_TO,
    CO_SUPERVISION,
    DATE_FORMATS,
    DEFAULT_APR_SECTIONS,
    DEFAULT_DATE_FORMAT,
    DEFAULT_DEPARTMENT_COMMITTEE,
    DEFAULT_RUBRIC,
    DEFAULT_SEMINAR_FORMS,
    ITEM_TYPES,
    MODULE_KEYS,
    SEMINAR_GRADERS,
    sql_in,
)
from app.models.base import Base, DomainRow, Timestamps


class Settings(Timestamps, Base):
    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_settings_single_row"),
        CheckConstraint(
            f"co_supervision IN ({sql_in(CO_SUPERVISION)})", name="ck_settings_co_supervision"
        ),
        CheckConstraint(
            f"seminar_graders IN ({sql_in(SEMINAR_GRADERS)})", name="ck_settings_seminar_graders"
        ),
        CheckConstraint(
            "jsonb_typeof(seminar_rubric) = 'array' AND jsonb_array_length(seminar_rubric) > 0",
            name="ck_settings_seminar_rubric",
        ),
        CheckConstraint(
            "jsonb_typeof(apr_sections) = 'array' AND jsonb_array_length(apr_sections) > 0",
            name="ck_settings_apr_sections",
        ),
        CheckConstraint("jsonb_typeof(seminar_forms) = 'object'", name="ck_settings_seminar_forms"),
        CheckConstraint("jsonb_typeof(phd_forms) = 'object'", name="ck_settings_phd_forms"),
        CheckConstraint("jsonb_typeof(phd_index) = 'array'", name="ck_settings_phd_index"),
        CheckConstraint(f"date_format IN ({sql_in(DATE_FORMATS)})", name="ck_settings_date_format"),
        CheckConstraint("min_coursework_credits BETWEEN 0 AND 40", name="ck_settings_min_credits"),
        CheckConstraint("min_coursework_cgpa BETWEEN 0 AND 10", name="ck_settings_min_cgpa"),
        CheckConstraint("max_duration_years BETWEEN 3 AND 12", name="ck_settings_max_years"),
        CheckConstraint(
            "min_duration_years BETWEEN 0 AND 6 AND min_publications BETWEEN 0 AND 10 "
            "AND max_plagiarism_percent BETWEEN 0 AND 100",
            name="ck_settings_thesis_gates",
        ),
        CheckConstraint(
            f"grievance_appeals_to IN ({sql_in(APPEALS_TO)})", name="ck_settings_appeals_to"
        ),
        CheckConstraint(
            "max_extension_days BETWEEN 0 AND 1825 AND max_relaxation_days BETWEEN 0 AND 1825 "
            "AND max_maternity_leave_days BETWEEN 0 AND 1825",
            name="ck_settings_time_limits",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    university_address: Mapped[str] = mapped_column(Text, server_default=text("''"))
    # What this university calls a department's research committee (DRC, DPGC ...).
    department_committee_name: Mapped[str] = mapped_column(
        Text, server_default=text(f"'{DEFAULT_DEPARTMENT_COMMITTEE}'")
    )
    co_supervision: Mapped[str] = mapped_column(Text, server_default=text("'off'"))
    require_hardcopy: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    require_no_dues: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    require_ethics: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    require_two_factor: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    require_signing: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    seminar_graders: Mapped[str] = mapped_column(Text, server_default=text("'panel'"))
    seminar_rubric: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text(f"'{json.dumps(list(DEFAULT_RUBRIC))}'::jsonb")
    )
    # Per seminar kind: rubric scores or the university's form questions (enums.SeminarKind).
    seminar_forms: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text(f"'{json.dumps(DEFAULT_SEMINAR_FORMS)}'::jsonb")
    )
    # The PhD file's forms as this university names them (enums.PHD_FORMS): per form, any of
    # title, number ("Form VII-A") and copy_to; what is missing is Anveshan's (PRD F17, part 4).
    phd_forms: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # How the university writes a date on every screen, PDF, notice and email (dates.py).
    date_format: Mapped[str] = mapped_column(Text, server_default=text(f"'{DEFAULT_DATE_FORMAT}'"))
    # Who signs notices as the Controller of Examinations when several hold the Exam Office role;
    # set by the Exam Office or the root admin, for the whole university (notices.py).
    exam_controller_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    # The university's own index of the PhD file: rows of {title, sources} (phd_index.py);
    # empty: Anveshan's annexures.
    phd_index: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    # Progress report sections: the university's own list, used while the toggle is on.
    apr_custom_template: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    apr_sections: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text(f"'{json.dumps(list(DEFAULT_APR_SECTIONS))}'::jsonb")
    )
    # UGC 2022: coursework of 12-16 credits, passed with 55% or its grade equivalent.
    min_coursework_credits: Mapped[float] = mapped_column(
        Numeric(3, 1, asdecimal=False), server_default=text("12")
    )
    min_coursework_cgpa: Mapped[float] = mapped_column(
        Numeric(4, 2, asdecimal=False), server_default=text("5.5")
    )
    # UGC 2022 reg. 10: 6 years from admission; re-registration up to 2 more; women and
    # persons with disabilities a further 2-year relaxation; maternity / child-care leave
    # up to 240 days once.
    max_duration_years: Mapped[int] = mapped_column(Integer, server_default=text("6"))
    max_extension_days: Mapped[int] = mapped_column(Integer, server_default=text("730"))
    max_relaxation_days: Mapped[int] = mapped_column(Integer, server_default=text("730"))
    max_maternity_leave_days: Mapped[int] = mapped_column(Integer, server_default=text("240"))
    # Thesis submission gates (thesis_gates.py; owner, 2026-11-22). UGC 2022 reg. 10: not
    # before 3 years from admission (0: no minimum). UGC 2018 plagiarism regulations: up to 10%
    # similarity is Level 0. UGC 2022 asks for no publications; many ordinances still do.
    min_duration_years: Mapped[int] = mapped_column(Integer, server_default=text("3"))
    max_plagiarism_percent: Mapped[float] = mapped_column(
        Numeric(5, 2, asdecimal=False), server_default=text("10")
    )
    min_publications: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    publications_indexed_only: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # The paper itself must be attached: before a scholar submits a publication, and before the
    # Library verifies a faculty one (items.py, faculty_papers.py). Off: the file is optional.
    publication_file_required: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Who decides a scholar's appeal against the grievance cell (grievances.py; owner,
    # 2026-11-23): the Ombudsperson UGC 2023 asks for, or the Vice Chancellor where chosen.
    grievance_appeals_to: Mapped[str] = mapped_column(Text, server_default=text("'ombudsperson'"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class Module(Timestamps, Base):
    __tablename__ = "modules"
    __table_args__ = (CheckConstraint(f"key IN ({sql_in(MODULE_KEYS)})", name="ck_modules_key"),)

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class ApprovalChain(Timestamps, Base):
    __tablename__ = "approval_chains"
    __table_args__ = (
        CheckConstraint(f"item_type IN ({sql_in(ITEM_TYPES)})", name="ck_chains_item_type"),
        CheckConstraint(
            "jsonb_typeof(steps) = 'array' AND jsonb_array_length(steps) > 0",
            name="ck_chains_steps",
        ),
    )

    item_type: Mapped[str] = mapped_column(Text, primary_key=True)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class UniversityLogo(DomainRow, Base):
    """The install's logo; the newest live row is the one in use. Its own table so reading
    settings, which most requests do, never pulls image bytes."""

    __tablename__ = "university_logos"

    content: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(Text)
