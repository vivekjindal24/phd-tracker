"""Idempotent seed: `DATABASE_URL=... SEED_PASSWORD=... python -m app.seed`.

Creates the demo dataset — admin, Dr. Meera Krishnan + one more supervisor, three
scholars (Arun Bhatt PHD-CS-2024-001 among them) with user accounts, and records
covering every workflow state. Re-running adds nothing that already exists.

Pass `--reset-passwords` (or set `RESET_PASSWORDS=1`) to reset passwords for existing seeded accounts.
"""

import asyncio
import os
import sys
from datetime import date

from sqlalchemy import func, select, update

from .auth.service import hash_password
from .db import SessionLocal
from .models import Meeting, Milestone, ProgressReport, RefreshToken, Scholar, Supervisor, User

DEMO_DATA = {
	"admin": ("admin@university.edu", "Research Office"),
	"supervisors": [
		("meera@university.edu", "Dr. Meera Krishnan", "Professor", "Computer Science"),
		("rajesh@university.edu", "Dr. Rajesh Nair", "Associate Professor", "Computer Science"),
	],
	"scholars": [
		("arun@university.edu", "Arun Bhatt", "PHD-CS-2024-001", "Dr. Meera Krishnan", "Research Phase"),
		("priya@university.edu", "Priya Sharma", "PHD-CS-2024-002", "Dr. Meera Krishnan", "Coursework"),
		("vikram@university.edu", "Vikram Rao", "PHD-CS-2023-007", "Dr. Rajesh Nair", "Proposal Approved"),
	],
}


async def seed(reset_passwords: bool = False) -> None:
	password = os.environ.get("SEED_PASSWORD")
	if not password:  # loud failure, config-by-env only
		sys.exit("SEED_PASSWORD is not set — refusing to seed (would create unknown credentials)")
	pw_hash = hash_password(password)

	async with SessionLocal() as db:
		async def get_user(email: str) -> User | None:
			return await db.scalar(select(User).where(User.email == email))

		admin_email, admin_name = DEMO_DATA["admin"]
		admin = await get_user(admin_email)
		if admin is None:
			admin = User(email=admin_email, password_hash=pw_hash, full_name=admin_name, role="admin")
			db.add(admin)
		elif reset_passwords:
			admin.password_hash = pw_hash

		supervisors: dict[str, Supervisor] = {}
		for email, name, designation, department in DEMO_DATA["supervisors"]:
			user = await get_user(email)
			if user is None:
				user = User(email=email, password_hash=pw_hash, full_name=name, role="supervisor")
				db.add(user)
				await db.flush()
			elif reset_passwords:
				user.password_hash = pw_hash
			sup = await db.scalar(select(Supervisor).where(Supervisor.email == email))
			if sup is None:
				sup = Supervisor(
					user_id=user.id, full_name=name, email=email, department=department,
					designation=designation, max_scholars=8,
				)
				db.add(sup)
			supervisors[name] = sup

		scholars: dict[str, Scholar] = {}
		for email, name, roll, sup_name, stage in DEMO_DATA["scholars"]:
			user = await get_user(email)
			if user is None:
				user = User(email=email, password_hash=pw_hash, full_name=name, role="scholar")
				db.add(user)
				await db.flush()
			elif reset_passwords:
				user.password_hash = pw_hash
			scholar = await db.scalar(select(Scholar).where(Scholar.roll_number == roll))
			if scholar is None:
				scholar = Scholar(
					user_id=user.id, scholar_name=name, roll_number=roll, scholar_email=email,
					department="Computer Science", admission_date=date(2024, 7, 1),
					stage=stage, supervisor_id=supervisors[sup_name].id,
				)
				db.add(scholar)
			scholars[name] = scholar
		await db.flush()

		arun = scholars["Arun Bhatt"]
		priya = scholars["Priya Sharma"]
		meera = supervisors["Dr. Meera Krishnan"]

		if not await db.scalar(select(Meeting).where(Meeting.scholar_id == arun.id)):
			db.add(Meeting(
				scholar_id=arun.id, supervisor_id=meera.id, meeting_date=date(2026, 9, 30),
				agenda="Literature review of transformer architectures",
				minutes="Discussed the survey draft; two chapters to be condensed.",
				action_items="Arun: restructure chapter 2 by Oct 15",
				next_meeting_date=date(2026, 10, 28),
			))

		reports = [
			(arun, 2026, "January-June", "draft", None),
			(arun, 2025, "July-December", "approved", date(2026, 1, 10)),
			(priya, 2026, "January-June", "submitted", None),
			(priya, 2025, "July-December", "rejected", None),
		]
		for scholar, year, period, state, approved_on in reports:
			if not await db.scalar(
				select(ProgressReport).where(
					ProgressReport.scholar_id == scholar.id,
					ProgressReport.report_year == year,
					ProgressReport.period == period,
					ProgressReport.deleted_at.is_(None),
				)
			):
				db.add(ProgressReport(
					scholar_id=scholar.id, report_year=year, period=period,
					summary="Completed the planned reading and experiments for the period; "
					"draft chapters revised following supervisor feedback.",
					supervisor_comment="Good progress." if state in ("approved", "rejected") else None,
					state=state, approved_on=approved_on,
				))

		if not await db.scalar(select(Milestone).where(Milestone.scholar_id == arun.id)):
			db.add(Milestone(
				scholar_id=arun.id, milestone_type="Proposal Approval (RDC)", status="Approved",
				approval_body="RDC", resolution_number="RDC/2024/031", resolution_date=date(2024, 11, 22),
				notes="Approved unanimously",
			))

		if reset_passwords:
			all_seed_emails = (
				[admin_email]
				+ [s[0] for s in DEMO_DATA["supervisors"]]
				+ [s[0] for s in DEMO_DATA["scholars"]]
			)
			await db.execute(
				update(RefreshToken)
				.where(
					RefreshToken.user_id.in_(
						select(User.id).where(User.email.in_(all_seed_emails))
					),
					RefreshToken.revoked_at.is_(None),
				)
				.values(revoked_at=func.now())
			)

		await db.commit()
	msg = (
		"Seed complete (seeded passwords reset)."
		if reset_passwords
		else "Seed complete (idempotent — existing rows untouched)."
	)
	print(msg)


if __name__ == "__main__":
	reset = (
		"--reset-passwords" in sys.argv
		or "--reset" in sys.argv
		or os.environ.get("RESET_PASSWORDS", "").lower() in ("1", "true", "yes")
	)
	asyncio.run(seed(reset_passwords=reset))