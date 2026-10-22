"""Seed data (DATABASE.md §8). Idempotent: an existing root unit means "already seeded".

    SEED_PASSWORD=... python -m app.seed                 # demo university, every role
    SEED_PASSWORD=... python -m app.seed --reset-passwords
    SEED_PASSWORD=... python -m app.seed --bootstrap --university "Name" --code CODE \
        --admin-email admin@uni.edu --admin-name "Full Name"   # production: root + admin only
"""

import argparse
import asyncio
import os
import sys

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import hash_password
from app.crud import insert
from app.db import SessionLocal, engine
from app.enums import UGC_CAP
from app.models import Faculty, Module, OrgUnit, RoleAssignment, Scholar, User
from app.org import create_unit

DOMAIN = "demo.edu"
MIN_PASSWORD = 10

# (code, name, kind, parent code)
DEMO_UNITS = [
    ("ENG", "School of Engineering", "School", "ADU"),
    ("SCI", "School of Sciences", "School", "ADU"),
    ("CSE", "Computer Science & Engineering", "Department", "ENG"),
    ("ECE", "Electronics & Communication", "Department", "ENG"),
    ("PHY", "Physics", "Department", "SCI"),
    ("CHE", "Chemistry", "Department", "SCI"),
]
# (login, full name, roles: [(role, unit code | None)])
DEMO_STAFF = [
    ("admin", "Anita Desai", [("admin", "ADU")]),
    ("research", "Dr. Kavita Rao", [("research_office", None)]),
    ("exams", "Suresh Pillai", [("exam_office", None)]),
    ("library", "Fatima Sheikh", [("library", None)]),
    ("dean.eng", "Prof. Arvind Menon", [("unit_head", "ENG")]),
    ("dean.sci", "Prof. Leela Iyer", [("unit_head", "SCI")]),
    ("drc.cse", "Rohit Verma", [("admin", "CSE")]),
]
# (login, full name, designation, unit, extra roles)
DEMO_FACULTY = [
    ("meera", "Dr. Meera Krishnan", "Professor", "CSE", [("unit_head", "CSE")]),
    ("rajesh", "Dr. Rajesh Nair", "Associate Professor", "CSE", []),
    ("sunita", "Dr. Sunita Gupta", "Assistant Professor", "ECE", [("unit_head", "ECE")]),
    ("farhan", "Dr. Farhan Ali", "Professor", "PHY", [("unit_head", "PHY")]),
    ("deepa", "Dr. Deepa Joshi", "Associate Professor", "CHE", [("unit_head", "CHE")]),
]
# (login, full name, roll, unit, supervisor login, stage)
DEMO_SCHOLARS = [
    ("arun", "Arun Bhatt", "PHD-CSE-2024-001", "CSE", "meera", "Coursework"),
    ("priya", "Priya Sharma", "PHD-CSE-2023-004", "CSE", "meera", "Proposal Approved"),
    ("vikram", "Vikram Rao", "PHD-CSE-2022-011", "CSE", "rajesh", "Pre-Synopsis"),
    ("neha", "Neha Iyer", "PHD-ECE-2024-002", "ECE", "sunita", "Registered"),
    ("kabir", "Kabir Malhotra", "PHD-PHY-2021-003", "PHY", "farhan", "Thesis Submitted"),
    ("zoya", "Zoya Khan", "PHD-CHE-2023-006", "CHE", "deepa", "Coursework"),
]


def _password() -> str:
    password = os.environ.get("SEED_PASSWORD", "")
    if len(password) < MIN_PASSWORD:
        sys.exit(f"SEED_PASSWORD must be set and at least {MIN_PASSWORD} characters")
    return password


async def _root(session: AsyncSession) -> OrgUnit | None:
    return await session.scalar(
        select(OrgUnit).where(OrgUnit.parent_id.is_(None), OrgUnit.deleted_at.is_(None))
    )


async def _user(session: AsyncSession, email: str, name: str, password_hash: str) -> User:
    return await insert(
        session, None, User(email=email, full_name=name, password_hash=password_hash)
    )


async def _role(session: AsyncSession, user: User, role: str, unit: OrgUnit | None) -> None:
    await insert(
        session, None, RoleAssignment(user_id=user.id, role=role, unit_id=unit.id if unit else None)
    )


async def bootstrap(
    session: AsyncSession, university: str, code: str, email: str, name: str
) -> None:
    if await _root(session):
        print("already seeded: a root unit exists; nothing changed")
        return
    root = await create_unit(session, None, None, university, "University", code)
    admin = await _user(session, email, name, hash_password(_password()))
    await _role(session, admin, "admin", root)
    await session.commit()
    print(f"bootstrapped {university}; root admin {email}")


async def demo(session: AsyncSession) -> None:
    if await _root(session):
        print("already seeded: a root unit exists; nothing changed")
        return
    pw = hash_password(_password())
    units = {"ADU": await create_unit(session, None, None, "Anveshan Demo University",
                                      "University", "ADU")}
    for code, name, kind, parent in DEMO_UNITS:
        units[code] = await create_unit(session, None, units[parent], name, kind, code)

    for login, name, roles in DEMO_STAFF:
        user = await _user(session, f"{login}@{DOMAIN}", name, pw)
        for role, unit in roles:
            await _role(session, user, role, units[unit] if unit else None)

    faculty: dict[str, Faculty] = {}
    for login, name, designation, unit, roles in DEMO_FACULTY:
        user = await _user(session, f"{login}@{DOMAIN}", name, pw)
        faculty[login] = await insert(session, None, Faculty(
            user_id=user.id, unit_id=units[unit].id, designation=designation,
            max_scholars=UGC_CAP[designation],
        ))
        for role, role_unit in roles:
            await _role(session, user, role, units[role_unit])

    for login, name, roll, unit, sup, stage in DEMO_SCHOLARS:
        user = await _user(session, f"{login}@{DOMAIN}", name, pw)
        await insert(session, None, Scholar(
            user_id=user.id, unit_id=units[unit].id, roll_number=roll, stage=stage,
            supervisor_id=faculty[sup].id,
        ))

    await session.execute(update(Module).values(enabled=True))
    await session.commit()
    print(f"seeded demo university: log in as admin@{DOMAIN} (or any login above) "
          "with SEED_PASSWORD")


async def reset_passwords(session: AsyncSession) -> None:
    result = await session.execute(
        update(User).where(User.email.like(f"%@{DOMAIN}")).values(
            password_hash=hash_password(_password())
        )
    )
    await session.commit()
    print(f"reset {result.rowcount} demo passwords")


async def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.seed")
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--reset-passwords", action="store_true")
    parser.add_argument("--university")
    parser.add_argument("--code")
    parser.add_argument("--admin-email")
    parser.add_argument("--admin-name")
    args = parser.parse_args(argv)
    async with SessionLocal() as session:
        if args.bootstrap:
            missing = [f for f in ("university", "code", "admin_email", "admin_name")
                       if not getattr(args, f)]
            if missing:
                parser.error("--bootstrap needs " + ", ".join(f"--{m.replace('_', '-')}"
                                                           for m in missing))
            await bootstrap(session, args.university, args.code, args.admin_email,
                            args.admin_name)
        elif args.reset_passwords:
            await reset_passwords(session)
        else:
            await demo(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
