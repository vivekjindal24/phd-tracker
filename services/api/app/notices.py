"""The notices of seminars and vivas (PRD F17b): Anveshan's wording, who signs, and the
department admin's changes — for every seminar or viva of the department, or for one (owner,
2026-11-21). The forms themselves are drawn in phd_forms.py."""

import uuid
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import committee
from app.auth.principal import Principal
from app.crud import update
from app.enums import LOCAL_TZ, NOTICE_SIGNER_LABELS, OFFICE_ROLES, SEMINAR_KIND_LABELS
from app.models import (
    CommitteeFormation,
    OrgUnit,
    RoleAssignment,
    Scholar,
    Seminar,
    Settings,
    User,
    VivaArrangement,
)

Kind = Literal["seminar", "viva"]
Record = Seminar | VivaArrangement

DEFAULT_SIGNERS: dict[Kind, tuple[str, ...]] = {
    "seminar": ("admin", "unit_head", "dean"),
    "viva": ("exam_office", "unit_head", "dean"),
}
# Who a notice is copied to, until the university's own list is a setting (F17, part 4).
COPY_TO: dict[Kind, list[str]] = {
    "seminar": [
        "The Vice Chancellor",
        "The Dean of the Faculty",
        "The Research Office",
        "The supervisor and the members of the Research Advisory Committee",
        "The scholar",
    ],
    "viva": [
        "The Vice Chancellor",
        "The Dean of the Faculty",
        "The Head of the Department",
        "The Research Office",
        "The members of the Examination Board",
        "The scholar",
    ],
}
UNIT_COLUMN = {"seminar": OrgUnit.notice_signers, "viva": OrgUnit.viva_notice_signers}


def signer(name: str | None, role: str, signature: str | None = None) -> dict[str, Any]:
    return {"name": name or "", "role": role, "signature": signature}


async def holder(session: AsyncSession, unit_id: uuid.UUID | None, role: str) -> str | None:
    """Who holds a role — a unit's head or admin, or an office (the Exam Office) — the first by
    name when several do."""
    if role in OFFICE_ROLES:
        where = RoleAssignment.unit_id.is_(None)
    elif unit_id is None:
        return None
    else:
        where = RoleAssignment.unit_id == unit_id
    return await session.scalar(
        select(User.full_name)
        .join(RoleAssignment, RoleAssignment.user_id == User.id)
        .where(where, RoleAssignment.role == role, RoleAssignment.deleted_at.is_(None))
        .order_by(User.full_name)
        .limit(1)
    )


def kind_of(record: Record) -> Kind:
    return "seminar" if isinstance(record, Seminar) else "viva"


def name(record: Record) -> str:
    if isinstance(record, VivaArrangement):
        return "Viva-Voce Examination"
    label = SEMINAR_KIND_LABELS[record.kind].replace(" seminar", " Seminar")
    return label.replace("Pre-synopsis", "Pre-Thesis Synopsis")


async def standard(session: AsyncSession, record: Record) -> dict[str, Any]:
    """The standard wording, before the department admin's changes: Anveshan's, with the
    university's "copy to" list for this kind of notice (settings.phd_forms)."""
    names = await session.scalar(select(Settings.phd_forms)) or {}
    key = f"{record.kind}_notice" if isinstance(record, Seminar) else "viva_notice"
    seminar = isinstance(record, Seminar)
    when = (record.starts_at if seminar else record.scheduled_at).astimezone(LOCAL_TZ)
    at = f"{when:%I:%M %p}".lstrip("0")  # 4:30 PM, as the paper notices read
    link = None if seminar else record.online_link
    return {
        "announcement": (
            f"This is for your kind information that the {name(record)} of the following "
            f"research scholar has been scheduled on {when:%d %B %Y} ({when:%A}) at {at}"
            + (f" in {record.venue}." if record.venue else ".")
            + (f" It may also be joined online at {link}." if link else "")
        ),
        "closing": f"All are cordially invited to attend the {name(record)}.",
        "copy_to": (names.get(key) or {}).get("copy_to") or COPY_TO[kind_of(record)],
    }


async def printed(session: AsyncSession, record: Record) -> dict[str, Any]:
    """The wording as printed: the standard one, with the department admin's changes."""
    custom = {k: v for k, v in (record.notice or {}).items() if v}
    return {**await standard(session, record), **custom}


async def unit_of(session: AsyncSession, record: Record) -> uuid.UUID:
    """The department whose notices these are: the seminar's, or the scholar's for a viva."""
    if isinstance(record, Seminar):
        return record.unit_id
    return await session.scalar(select(Scholar.unit_id).where(Scholar.id == record.scholar_id))


async def department_signers(session: AsyncSession, record: Record) -> list[str]:
    kind = kind_of(record)
    unit = await session.scalar(
        select(UNIT_COLUMN[kind]).where(OrgUnit.id == await unit_of(session, record))
    )
    return list(unit or DEFAULT_SIGNERS[kind])


async def signer_keys(session: AsyncSession, record: Record) -> list[str]:
    """Who signs: as set for this seminar or viva, else for its department, else the default."""
    custom = (record.notice or {}).get("signers")
    return list(custom) if custom else await department_signers(session, record)


async def signers(session: AsyncSession, record: Record) -> list[dict[str, Any]]:
    """Each signer named from the records; one person holding two of the roles signs once, with
    both ("Head of Department & Chairperson, DRC", as the paper notices read)."""
    keys = await signer_keys(session, record)
    unit = await unit_of(session, record)
    drc: list[dict[str, Any]] = []
    if {"drc_chair", "drc_secretary"} & set(keys):
        current = await committee.current(session, CommitteeFormation.unit_id == unit)
        drc = await committee.members(session, current.id) if current else []
    parent = await session.scalar(select(OrgUnit.parent_id).where(OrgUnit.id == unit))

    async def named(key: str) -> str | None:
        if key in ("drc_chair", "drc_secretary"):
            role = "chairperson" if key == "drc_chair" else "secretary"
            return next((m["name"] for m in drc if m["role"] == role), None)
        if key == "dean":
            return await holder(session, parent, "unit_head")
        return await holder(session, unit, key)

    out: list[dict[str, Any]] = []
    for key in keys:
        who, role = await named(key), NOTICE_SIGNER_LABELS[key]
        same = next((o for o in out if who and o["name"] == who), None)
        if same:
            same["role"] += f" & {role}"
        else:
            out.append(signer(who, role))
    return out


async def view(session: AsyncSession, record: Record, can_edit: bool) -> dict[str, Any]:
    """The Notice card: who signs, the department's signers, this record's changes, and
    Anveshan's wording beneath them."""
    return {
        "can_edit": can_edit,
        "choices": [{"key": k, "label": v} for k, v in NOTICE_SIGNER_LABELS.items()],
        "signers": await signer_keys(session, record),
        "department_signers": await department_signers(session, record),
        "custom": record.notice or {},
        "standard": await standard(session, record),
    }


async def change(
    session: AsyncSession, principal: Principal, record: Record, changes: dict[str, Any]
) -> None:
    """This seminar's or viva's notice only; what is left empty follows the department."""
    custom = {k: v for k, v in changes.items() if v}
    await update(session, principal, record, {"notice": custom or None})


async def change_department(
    session: AsyncSession, principal: Principal, record: Record, keys: list[str] | None
) -> None:
    """Who signs every notice of this kind in the department, unless one says otherwise."""
    unit = await session.get(OrgUnit, await unit_of(session, record))
    column = UNIT_COLUMN[kind_of(record)].key
    await update(session, principal, unit, {column: keys})
